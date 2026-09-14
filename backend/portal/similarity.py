"""
Pairwise Code Similarity & Academic Integrity Detection Engine.

Analyzes student code submissions for a specific coding problem to detect
plagiarism and unusually high structural similarity. Uses deterministic token-level
sequence matching without external AI dependencies or student code leakage.
"""

from .evaluator import _normalize_tokens, _similarity
from .models import CodingSubmission


def compute_coding_problem_similarity(exam, problem, threshold=0.70):
    """
    Computes pairwise similarity among all submitted solutions for a given coding problem.
    
    Rules:
    - Only submissions with non-empty code are evaluated.
    - Only submissions written in the exact same programming language are compared.
    - Cross-language pairs are excluded.
    - Pairs with similarity >= threshold are flagged.
    - Results are sorted by similarity descending.
    """
    submissions = list(
        CodingSubmission.objects.filter(
            session__exam=exam,
            problem=problem,
        ).select_related('session__student').order_by('id')
    )

    # Filter out empty or whitespace-only submissions
    valid_submissions = [sub for sub in submissions if (sub.submitted_code or '').strip()]
    compared_count = len(valid_submissions)

    # Group submissions by normalized language
    grouped_by_language = {}
    for sub in valid_submissions:
        lang = (sub.language or 'python').strip().lower()
        grouped_by_language.setdefault(lang, []).append(sub)

    flagged_pairs = []

    for lang, sub_list in grouped_by_language.items():
        if len(sub_list) < 2:
            continue

        # Pre-tokenize all submissions in this language group
        tokenized_submissions = []
        for sub in sub_list:
            tokens = _normalize_tokens(sub.submitted_code, lang)
            tokenized_submissions.append((sub, tokens))

        # Pairwise comparison
        n = len(tokenized_submissions)
        for i in range(n):
            sub_a, tokens_a = tokenized_submissions[i]
            len_a = len(tokens_a)
            for j in range(i + 1, n):
                sub_b, tokens_b = tokenized_submissions[j]
                len_b = len(tokens_b)

                # Don't compare a student against their own multiple submissions if any
                if sub_a.session.student_id == sub_b.session.student_id:
                    continue

                # Mathematical upper-bound pruning:
                # SequenceMatcher.ratio() <= (2 * min(len_a, len_b)) / (len_a + len_b)
                total_len = len_a + len_b
                if total_len == 0:
                    continue
                max_possible = (2.0 * min(len_a, len_b)) / total_len
                if max_possible < threshold:
                    continue

                sim = _similarity(tokens_a, tokens_b)
                if sim >= threshold:
                    flagged_pairs.append({
                        'submission_a_id': sub_a.id,
                        'submission_b_id': sub_b.id,
                        'student_a': {
                            'id': sub_a.session.student.id,
                            'name': sub_a.session.student.name or sub_a.session.student.username,
                            'enrollment_no': sub_a.session.student.enrollment_no or sub_a.session.student.username,
                        },
                        'student_b': {
                            'id': sub_b.session.student.id,
                            'name': sub_b.session.student.name or sub_b.session.student.username,
                            'enrollment_no': sub_b.session.student.enrollment_no or sub_b.session.student.username,
                        },
                        'similarity': round(sim, 4),
                        'language': lang,
                    })

    # Sort flagged pairs by highest similarity first
    flagged_pairs.sort(key=lambda item: item['similarity'], reverse=True)

    return {
        'exam_id': exam.id,
        'problem_id': problem.id,
        'problem_title': problem.title,
        'compared_submissions': compared_count,
        'threshold': threshold,
        'flagged_pairs': flagged_pairs,
    }
