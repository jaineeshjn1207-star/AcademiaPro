"""Academia Pro AI Coding Tutor API.

Implements the user's LangChain-style Gemini tutoring agent with optional search,
Wikipedia and save-to-file tools. This is separate from exam grading. It is for
learning help and refuses cheating/security-bypass requests.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from django.conf import settings
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

SYSTEM_PROMPT = """
You are the Academia Pro AI Coding Tutor — a patient, encouraging learning
assistant for students studying programming and computer science.

SCOPE
You help with: programming and coding, computer science fundamentals,
software development, algorithms and data structures, databases, web
development, AI/ML, networking, operating systems, and preparing for
technical examinations. If a question falls outside this scope, say so
briefly and steer the conversation back — don't lecture about the refusal.

HOW YOU TEACH
- Teach the underlying idea, not just the answer. Walk through *why* something
  works before showing *how*.
- When a student's question is ambiguous or you're missing key context (their
  current level, what they've already tried, the exact error message), ask a
  short clarifying question rather than guessing.
- For debugging help: ask to see the actual error/traceback and what they've
  already tried, if they haven't shared it. Guide them toward finding the bug
  themselves before just handing over a fix.
- For conceptual questions: use a small concrete example or analogy, then
  generalize. Mention time/space complexity when it's relevant to the topic.
- Match your depth to the question. A quick syntax question deserves a short,
  direct answer; a "why does this work" question deserves a fuller
  explanation. Don't pad simple answers or rush complex ones.
- Reply in plain text. Do not use markdown headings, **bold**, ##, tables, or decorative formatting.
- Keep answers concise unless the student asks for detail.

INTEGRITY BOUNDARIES
Never help a student bypass proctoring, monitoring, access controls, or other
exam-security mechanisms, and never write or complete answers for a live,
in-progress exam or graded assignment on the student's behalf. If a request
looks like it's asking you to solve a current assessment rather than learn a
concept, say you can't do that specific thing, then offer to explain the
underlying concept instead — briefly, without moralizing.

TONE
Be warm, direct, and technically precise. Treat the student as capable.
Never be condescending, and never pretend to know something you don't —
say so and suggest how they could verify it (including using your search
tool for anything time-sensitive or version-specific).
"""

MAX_TOOL_ROUNDS = 0
MAX_HISTORY_MESSAGES = 8


def extract_text(content):
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get('type') == 'text':
                parts.append(block.get('text', ''))
        return ''.join(parts).strip()
    return str(content or '').strip()


def clean_plain_text(text):
    text = str(text or '')
    text = re.sub(r'```[a-zA-Z0-9_-]*\n?', '', text).replace('```', '')
    text = re.sub(r'^[#>*_`\-]{1,6}\s*', '', text, flags=re.MULTILINE)
    text = text.replace('**', '').replace('__', '').replace('##', '')
    return '\n'.join(line.rstrip() for line in text.splitlines()).strip()


def _safe_tutor_save(data: str, filename: str = 'research_output.txt'):
    safe_name = Path(filename or 'research_output.txt').name
    if not safe_name.endswith('.txt'):
        safe_name += '.txt'
    out_dir = Path(settings.MEDIA_ROOT) / 'ai_tutor_outputs'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / safe_name
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    out_path.open('a', encoding='utf-8').write(
        f"--- AI Tutor Output ---\nTimestamp: {timestamp}\n\n{data}\n\n"
    )
    return f'Data successfully saved to {safe_name}'


def _build_tools():
    from langchain_community.tools import DuckDuckGoSearchRun, WikipediaQueryRun
    from langchain_community.utilities import WikipediaAPIWrapper
    from langchain_core.tools import StructuredTool

    search_tool = DuckDuckGoSearchRun()
    search_tool.name = 'search'
    search_tool.description = (
        'Search the web for current programming, computer science, software, '
        'technology or technical education information. Input: a search query string.'
    )

    wiki_tool = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(
        top_k_results=3,
        doc_content_chars_max=1000,
        lang='en',
    ))

    save_tool = StructuredTool.from_function(
        func=_safe_tutor_save,
        name='save_text_to_file',
        description='Save the given text to a server-side text file. Parameters: data, optional filename.',
    )
    return [search_tool, wiki_tool, save_tool]


def run_tool_call(tool_call, tools_by_name):
    name = tool_call.get('name', '?')
    args = tool_call.get('args', {}) or {}
    tool = tools_by_name.get(name)
    if tool is None:
        return f"Unknown tool '{name}' - nothing was executed."
    try:
        return tool.run(args)
    except Exception as exc:
        return f"Tool '{name}' failed: {type(exc).__name__}: {exc}"


def _history_to_messages(history):
    from langchain_core.messages import AIMessage, HumanMessage

    messages = []
    for item in (history or [])[-MAX_HISTORY_MESSAGES:]:
        role = (item.get('role') or '').lower() if isinstance(item, dict) else ''
        content = item.get('content', '') if isinstance(item, dict) else ''
        if not content:
            continue
        if role in ('assistant', 'ai'):
            messages.append(AIMessage(content=str(content)))
        elif role in ('user', 'human'):
            messages.append(HumanMessage(content=str(content)))
    return messages


class AITutorChatView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = str(request.data.get('message') or request.data.get('query') or '').strip()
        if not query:
            return Response({'error': 'message is required.'}, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response(
                {'error': 'AI Tutor is unavailable because GEMINI_API_KEY is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_google_genai import ChatGoogleGenerativeAI

            model_name = os.environ.get('GEMINI_TUTOR_MODEL') or os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash-lite')
            llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=0.1)

            messages = [SystemMessage(content=SYSTEM_PROMPT)]
            messages.extend(_history_to_messages(request.data.get('history') or []))
            messages.append(HumanMessage(content=query))

            response = llm.invoke(messages)
            reply = clean_plain_text(extract_text(response.content))
            if not reply:
                reply = 'No text reply produced. Please try again.'
            return Response({'reply': reply, 'tool_rounds': 0, 'model': model_name})
        except Exception as exc:
            return Response(
                {'error': f'AI Tutor failed: {type(exc).__name__}: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


