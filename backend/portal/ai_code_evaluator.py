"""Gemini-only coding evaluator.

Per product decision, local/static/custom-model grading has been removed
from the active evaluation path. Coding submissions are evaluated only by
Gemini through portal.gemini_code_evaluator.

If Gemini is not configured or returns invalid output, the submission is marked
for faculty review with zero automatic coding marks. Faculty override remains
available.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

from .gemini_code_evaluator import evaluate_with_gemini


def evaluate_code_ai_first(code: str, language: str, problem: Any, refs: Iterable[Any]) -> Dict[str, Any]:
    max_marks = float(getattr(problem, 'marks', 0) or 0)
    code = (code or '').strip()
    language = (language or 'python').lower()
    refs = list(refs or [])

    if not code:
        return {
            'logic_status': 'incorrect',
            'marks_awarded': 0.0,
            'matched_reference': None,
            'feedback': 'No code was submitted.',
            'missing_constructs': [],
            'source': 'gemini-unavailable',
            'test_passed_count': 0,
            'test_total_count': 0,
            'hidden_failed_count': 0,
            'failed_visible_tests': [],
            'ai_debug': {
                'detected_approach': 'empty submission',
                'logic_summary': 'The student did not submit code for this problem.',
                'mistake_explanation': 'Write a complete solution before submitting.',
                'corrected_code': '',
                'predicted_output': '',
                'source': 'gemini-unavailable',
            },
        }

    gemini = evaluate_with_gemini(code, language, problem, refs, max_marks)
    if gemini:
        return gemini

    return {
        'logic_status': 'pending',
        'marks_awarded': 0.0,
        'matched_reference': None,
        'feedback': (
            'Gemini evaluator is unavailable or returned an invalid response. '
            'No local/static/custom-model fallback was used; faculty review is required.'
        ),
        'missing_constructs': [],
        'source': 'gemini-unavailable',
        'test_passed_count': 0,
        'test_total_count': 0,
        'hidden_failed_count': 0,
        'failed_visible_tests': [],
        'ai_debug': {
            'detected_approach': 'Pending faculty review',
            'logic_summary': 'The Gemini evaluator did not produce a usable evaluation, so this submission is pending faculty review.',
            'mistake_explanation': 'Configure GEMINI_API_KEY/GEMINI_MODEL correctly or let faculty review this submission manually.',
            'corrected_code': '',
            'predicted_output': '',
            'source': 'gemini-unavailable',
        },
    }

