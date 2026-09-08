"""Deprecated compatibility module.

External Gemini evaluation has been removed. The project now uses
portal.ai_code_evaluator with optional local trained model support.
"""


def evaluate_submission_with_llm(*args, **kwargs):
    return None


def generate_ai_debug_feedback(*args, **kwargs):
    return None
