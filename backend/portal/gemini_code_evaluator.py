"""Gemini-powered coding evaluator for Academia Pro.

Uses LangChain's ChatGoogleGenerativeAI wrapper so the app can evaluate coding
answers with Gemini while preserving all existing portal features and fallbacks.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, Optional


def _content_text(content) -> str:
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


def _extract_json(text: str | None) -> Optional[dict]:
    raw = (text or '').strip()
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.I)
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def _refs_text(refs: Iterable[Any]) -> str:
    parts = []
    for i, ref in enumerate(refs or [], start=1):
        parts.append(
            f"Reference {i}: {getattr(ref, 'title', 'Reference')}\n"
            f"Explanation: {getattr(ref, 'logic_explanation', '')}\n"
            f"Code:\n{getattr(ref, 'code', '')}"
        )
    return '\n\n'.join(parts) or 'No faculty reference solution was provided.'


def _language_rubric(language: str) -> str:
    lang = (language or '').lower()
    common = """
GENERAL RULES
- Evaluate the entire submitted answer: imports, functions/classes, top-level
  code, input/output, library/API calls, data transformations, UI/API behavior,
  side effects, final output, and correctness against the prompt.
- Do not require the student to match faculty reference code. Any correct
  approach is valid.
- Do not over-credit unrelated code, stubs, hardcoded fixed outputs with no
  logic, wrong operations, hallucinated APIs, missing required pieces, or code
  that would not plausibly run.
- If the idea is correct but implementation has a small bug, mark partial and
  explain exactly what to fix.
- corrected_code must be based on the student's code: preserve variable names,
  imports, filenames, route names, components, schemas, and architecture where
  possible. Do not return one generic solution for all students.
- predicted_output must describe what the student's submitted code currently
  prints/displays/renders/returns according to its own logic.
"""
    if lang == 'python':
        return common + """
PYTHON-SPECIFIC RUBRIC
- Check syntax, imports, functions/classes, stdin/file input, print/display
  output, exception handling, data transformations, and final result.
- For pandas/numpy/seaborn/matplotlib/sklearn tasks, grade required API
  operations and logical order. Loops/branches are not required when vectorized
  or library code solves the task.
- Beginner hardcoded variables can demonstrate correct logic if the problem is
  conceptual; explain how to adapt to input/files when needed.
"""
    if lang == 'javascript':
        return common + """
JAVASCRIPT-SPECIFIC RUBRIC
- Check browser JS and Node.js semantics, functions, arrays/objects, modules,
  promises/async-await, DOM updates, fetch/axios calls, event handlers,
  validation, error handling, React-style code if present, and Express-style
  route logic if present.
"""
    if lang == 'cpp':
        return common + """
C++17 RUBRIC
- Check includes, main/function signatures, STL containers, loops/recursion,
  memory safety, integer overflow, input parsing, output formatting,
  complexity, and edge cases. Corrected code should compile as C++17.
"""
    if lang == 'java':
        return common + """
JAVA RUBRIC
- Check public Main compatibility, class/method structure, Scanner or
  BufferedReader input, collections, exceptions, type correctness, output
  format, and edge cases. Corrected code should be complete and compilable.
"""
    return common


SYSTEM_PROMPT = """
You are Academia Pro's AI Coding Evaluator and Coding Tutor.

You are strictly limited to programming, coding, computer science, software
engineering, technology, and technical education.

You must not help with cheating, bypassing monitoring, evading platform
security, or exploiting Academia Pro.

For grading, be strict but fair. You assign marks based on logic correctness,
problem requirements, completeness, and code quality. You also provide helpful
learning feedback and corrected code based on the student's own approach.
"""


def _build_prompt(code: str, language: str, problem: Any, refs: Iterable[Any], max_marks: float) -> str:
    return f"""Evaluate this coding-exam submission.

{_language_rubric(language)}

PROBLEM TITLE: {getattr(problem, 'title', '')}
PROBLEM STATEMENT:
{getattr(problem, 'problem_statement', '')}

INPUT FORMAT:
{getattr(problem, 'input_format', '')}

OUTPUT FORMAT:
{getattr(problem, 'output_format', '')}

SAMPLE INPUT:
{getattr(problem, 'sample_input', '')}

SAMPLE OUTPUT:
{getattr(problem, 'sample_output', '')}

FACULTY REFERENCE SOLUTIONS (context only, not mandatory):
{_refs_text(refs)}

LANGUAGE: {language}
MAX MARKS: {max_marks}

STUDENT CODE:
{code}

Return strict JSON only with this exact shape:
{{
  "verdict": "correct" | "partial" | "incorrect",
  "score_ratio": <float 0.0 to 1.0>,
  "detected_approach": "short approach name",
  "logic_summary": "what the student tried to do",
  "mistake_explanation": "what is wrong or what can improve",
  "corrected_code": "complete corrected code based on student's approach",
  "predicted_output": "what the submitted code would output/render/return according to current logic",
  "feedback": "short student-facing grading feedback"
}}
"""


def evaluate_with_gemini(code: str, language: str, problem: Any, refs: Iterable[Any], max_marks: float) -> Optional[Dict[str, Any]]:
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key or not (code or '').strip():
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_google_genai import ChatGoogleGenerativeAI

        model_name = os.environ.get('GEMINI_MODEL', 'gemini-3.6-flash')
        llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=0.05)
        resp = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=_build_prompt(code, language, problem, refs, max_marks)),
        ])
        data = _extract_json(_content_text(resp.content))
        if not isinstance(data, dict):
            return None
        verdict = str(data.get('verdict', '')).strip().lower()
        if verdict not in {'correct', 'partial', 'incorrect'}:
            return None
        ratio = max(0.0, min(1.0, float(data.get('score_ratio', 0) or 0)))
        if verdict == 'incorrect':
            ratio = min(ratio, 0.2)
        elif verdict == 'partial':
            ratio = min(max(ratio, 0.25), 0.85)
        elif verdict == 'correct':
            ratio = max(ratio, 0.8)
        return {
            'logic_status': verdict,
            'marks_awarded': round(float(max_marks or 0) * ratio, 2),
            'matched_reference': None,
            'feedback': str(data.get('feedback', '') or 'Gemini evaluation completed.'),
            'missing_constructs': [],
            'source': f'gemini:{os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")}',
            'test_passed_count': 0,
            'test_total_count': 0,
            'hidden_failed_count': 0,
            'failed_visible_tests': [],
            'ai_debug': {
                'detected_approach': str(data.get('detected_approach', '') or '')[:255],
                'logic_summary': str(data.get('logic_summary', '') or ''),
                'mistake_explanation': str(data.get('mistake_explanation', '') or ''),
                'corrected_code': str(data.get('corrected_code', '') or ''),
                'predicted_output': str(data.get('predicted_output', '') or ''),
                'source': 'gemini-feedback',
            },
        }
    except Exception:
        return None

