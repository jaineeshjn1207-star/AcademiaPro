"""
Logic evaluation engine for coding submissions.

This is a static, sandbox-free analyzer: it never executes student code.
It combines three signals to decide whether a student's *logic* is correct:

  1. Structural validity  - does the code parse / is it non-trivial?
  2. Construct coverage    - does it use the constructs the reference
                             solutions rely on (loops, dicts, recursion, ...)?
  3. Token similarity      - normalized token-sequence similarity against each
                             faculty reference solution.

Returns a verdict of 'correct' | 'partial' | 'incorrect' plus a score ratio
in [0, 1] and human-readable feedback.
"""

import ast
import io
import re
import tokenize
import difflib

# --------------------------------------------------------------------------
# Trivial / stub detection
# --------------------------------------------------------------------------

STUB_PATTERNS = [
    r'^\s*pass\s*$',
    r'#\s*TODO',
    r'#\s*write your (solution|code)',
    r'#\s*your code here',
]

PLACEHOLDER_LINE = re.compile(r'^\s*(#|//|/\*|\*)')


def _strip_comments_and_blanks(code, language='python'):
    lines = []
    for raw in code.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if PLACEHOLDER_LINE.match(line):
            continue
        lines.append(line)
    return lines


def _is_stub(code, language='python'):
    """True when the submission is effectively empty / untouched boilerplate."""
    body = _strip_comments_and_blanks(code, language)
    if not body:
        return True, "Empty submission - no executable logic was written."

    joined = "\n".join(body)
    if len(joined.strip()) < 25:
        return True, "Submission is too short to contain a working algorithm."

    # Every remaining line is just a def + pass
    meaningful = [l for l in body if not re.match(r'^\s*(pass|\.\.\.)\s*$', l)]
    if len(meaningful) <= 1:
        return True, "Only a function stub was submitted - the body is empty."

    for pat in STUB_PATTERNS:
        if re.search(pat, joined, re.IGNORECASE | re.MULTILINE):
            if len(meaningful) <= 3:
                return True, "Boilerplate template submitted without an implementation."

    return False, ""


# --------------------------------------------------------------------------
# Tokenisation / normalisation
# --------------------------------------------------------------------------

PY_KEYWORDS = {
    'def', 'return', 'for', 'while', 'if', 'elif', 'else', 'in', 'not', 'and',
    'or', 'import', 'from', 'class', 'try', 'except', 'with', 'as', 'lambda',
    'yield', 'break', 'continue', 'range', 'len', 'print', 'sorted', 'sum',
    'min', 'max', 'abs', 'set', 'dict', 'list', 'tuple', 'enumerate', 'zip',
    'append', 'map', 'filter', 'int', 'str', 'float',
}

GENERIC_KEYWORDS = PY_KEYWORDS | {
    'function', 'var', 'let', 'const', 'console', 'log', 'push', 'std', 'cout',
    'cin', 'vector', 'unordered_map', 'map', 'public', 'static', 'void', 'main',
    'System', 'out', 'println', 'new', 'HashMap', 'ArrayList',
}


def _normalize_tokens(code, language='python'):
    """
    Turn source into a canonical token stream where identifiers become 'ID'
    and numbers become 'NUM', so that variable naming does not affect
    similarity, but structure does.
    """
    tokens = []
    if language == 'python':
        try:
            for tok in tokenize.generate_tokens(io.StringIO(code).readline):
                ttype, tstr = tok.type, tok.string
                if ttype in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                             tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING,
                             tokenize.ENDMARKER):
                    continue
                if not tstr.strip():
                    continue
                if ttype == tokenize.NAME:
                    tokens.append(tstr if tstr in PY_KEYWORDS else 'ID')
                elif ttype == tokenize.NUMBER:
                    tokens.append('NUM')
                elif ttype == tokenize.STRING:
                    tokens.append('STR')
                else:
                    tokens.append(tstr)
            return tokens
        except Exception:
            pass  # fall through to regex tokenizer

    for raw in re.findall(r"[A-Za-z_]\w*|\d+\.?\d*|[^\sA-Za-z0-9_]", code):
        if raw.isdigit():
            tokens.append('NUM')
        elif re.match(r'^[A-Za-z_]\w*$', raw):
            tokens.append(raw if raw in GENERIC_KEYWORDS else 'ID')
        else:
            tokens.append(raw)
    return tokens


def _similarity(a_tokens, b_tokens):
    if not a_tokens or not b_tokens:
        return 0.0
    sm = difflib.SequenceMatcher(None, a_tokens, b_tokens, autojunk=False)
    return sm.ratio()


# --------------------------------------------------------------------------
# Construct extraction
# --------------------------------------------------------------------------

def _constructs(code, language='python'):
    """Set of algorithmic constructs present in the code."""
    found = set()
    lowered = code.lower()

    if language == 'python':
        try:
            tree = ast.parse(code)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, (ast.For, ast.While, ast.comprehension)):
                    found.add('loop')
                if isinstance(node, ast.FunctionDef):
                    found.add('function')
                if isinstance(node, ast.If):
                    found.add('branch')
                if isinstance(node, ast.Return):
                    found.add('return')
                if isinstance(node, (ast.Dict, ast.DictComp)):
                    found.add('hashmap')
                if isinstance(node, (ast.Set, ast.SetComp)):
                    found.add('set')
                if isinstance(node, (ast.List, ast.ListComp)):
                    found.add('array')
                if isinstance(node, ast.Call):
                    fn = node.func
                    name = getattr(fn, 'id', None) or getattr(fn, 'attr', None) or ''
                    if name in ('dict', 'defaultdict', 'Counter', 'get'):
                        found.add('hashmap')
                    if name in ('set', 'frozenset'):
                        found.add('set')
                    if name in ('sorted', 'sort'):
                        found.add('sorting')
                    if name in ('print',):
                        found.add('output')
                if isinstance(node, ast.Try):
                    found.add('exception')
            # naive recursion detection
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Call) and getattr(sub.func, 'id', None) == node.name:
                            found.add('recursion')
            return found

    # Non-python (or unparsable python) fallback: keyword scan
    if re.search(r'\b(for|while|forEach)\b', lowered):
        found.add('loop')
    if re.search(r'\b(def|function|void|int\s+\w+\s*\()', lowered):
        found.add('function')
    if re.search(r'\bif\b', lowered):
        found.add('branch')
    if re.search(r'\breturn\b', lowered):
        found.add('return')
    if re.search(r'(hashmap|unordered_map|dict\(|\{\s*\}|map<)', lowered):
        found.add('hashmap')
    if re.search(r'(set\(|hashset|unordered_set)', lowered):
        found.add('set')
    if re.search(r'(\[\]|vector<|arraylist)', lowered):
        found.add('array')
    if re.search(r'\bsort\b', lowered):
        found.add('sorting')
    if re.search(r'(print|console\.log|cout|println)', lowered):
        found.add('output')
    return found


def _syntax_error(code, language='python'):
    if language != 'python':
        return None
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return f"Line {e.lineno}: {e.msg}"


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

CORRECT_THRESHOLD = 0.62
PARTIAL_THRESHOLD = 0.34


def evaluate_submission(code, language, reference_solutions, max_marks):
    """
    Args:
        code:                 student's submitted source (str)
        language:             'python' | 'javascript' | 'cpp' | 'java'
        reference_solutions:  iterable of ReferenceSolution model instances
        max_marks:            float, full marks for the problem

    Returns dict:
        { logic_status, marks_awarded, similarity, matched_reference,
          feedback, missing_constructs }
    """
    code = (code or '').strip()
    language = (language or 'python').lower()
    max_marks = float(max_marks or 0)

    result = {
        'logic_status': 'incorrect',
        'marks_awarded': 0.0,
        'similarity': 0.0,
        'matched_reference': None,
        'feedback': '',
        'missing_constructs': [],
    }

    # --- 1. Trivial / stub ---------------------------------------------
    stub, why = _is_stub(code, language)
    if stub:
        result['feedback'] = f"Logic verification failed. {why} Study the reference solutions unlocked below."
        return result

    # --- 2. Syntax ------------------------------------------------------
    syn = _syntax_error(code, language)
    if syn:
        result['feedback'] = (
            f"Syntax error detected - the program could not be parsed ({syn}). "
            "Logic could not be verified. Reference solutions are unlocked below."
        )
        result['marks_awarded'] = 0.0
        return result

    refs = list(reference_solutions or [])
    student_tokens = _normalize_tokens(code, language)
    student_constructs = _constructs(code, language)

    # No references uploaded -> fall back to a structural sanity check only.
    if not refs:
        has_core = {'loop', 'function', 'branch'} & student_constructs
        has_out = {'return', 'output'} & student_constructs
        if has_core and has_out:
            result.update({
                'logic_status': 'correct',
                'marks_awarded': round(max_marks, 2),
                'similarity': 1.0,
                'feedback': "Structural check passed. No faculty reference solution was uploaded for automated comparison; awaiting manual review if required.",
            })
        else:
            result['feedback'] = "Submission lacks core algorithmic structure (no control flow and/or no result produced)."
        return result

    # --- 3. Compare against every reference -----------------------------
    best_sim = 0.0
    best_ref = None
    best_missing = []

    for ref in refs:
        ref_lang = (getattr(ref, 'language', 'python') or 'python').lower()
        ref_tokens = _normalize_tokens(ref.code, ref_lang)
        sim = _similarity(student_tokens, ref_tokens)

        ref_constructs = _constructs(ref.code, ref_lang)
        core = ref_constructs & {'loop', 'hashmap', 'set', 'recursion', 'sorting', 'branch'}
        missing = sorted(core - student_constructs)
        coverage = 1.0 if not core else (len(core & student_constructs) / len(core))

        # Blend token similarity with construct coverage.
        blended = (0.55 * sim) + (0.45 * coverage)

        if blended > best_sim:
            best_sim = blended
            best_ref = ref
            best_missing = missing

    produces_result = bool({'return', 'output'} & student_constructs)
    if not produces_result:
        best_sim *= 0.55

    result['similarity'] = round(best_sim, 3)
    result['matched_reference'] = best_ref.title if best_ref else None
    result['missing_constructs'] = best_missing

    if best_sim >= CORRECT_THRESHOLD:
        result['logic_status'] = 'correct'
        result['marks_awarded'] = round(max_marks, 2)
        result['feedback'] = (
            f"Logic verified. Your approach matches the reference strategy "
            f"\"{best_ref.title}\" with {round(best_sim * 100)}% structural agreement."
        )
    elif best_sim >= PARTIAL_THRESHOLD:
        ratio = 0.4 + 0.4 * ((best_sim - PARTIAL_THRESHOLD) / (CORRECT_THRESHOLD - PARTIAL_THRESHOLD))
        result['logic_status'] = 'partial'
        result['marks_awarded'] = round(max_marks * ratio, 2)
        miss = f" Missing key construct(s): {', '.join(best_missing)}." if best_missing else ""
        result['feedback'] = (
            f"Partially correct logic ({round(best_sim * 100)}% agreement with "
            f"\"{best_ref.title}\").{miss} Reference solutions are unlocked below so you can compare approaches."
        )
    else:
        result['logic_status'] = 'incorrect'
        result['marks_awarded'] = 0.0
        if not produces_result:
            reason = "Your program never returns or prints a result."
        elif best_missing:
            reason = f"Your solution does not use the required approach - missing: {', '.join(best_missing)}."
        else:
            reason = "Your algorithm diverges substantially from every accepted approach."
        result['feedback'] = (
            f"Incorrect logic ({round(best_sim * 100)}% agreement). {reason} "
            "The faculty reference solutions with explanations are unlocked below."
        )

    return result
