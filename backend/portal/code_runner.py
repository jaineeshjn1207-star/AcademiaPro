"""
Executes a student's coding-exam submission against sample or custom input
and returns stdout/stderr — this powers the "Run Code" button during an exam.
Running code never affects marks by itself; grading still happens separately
at submission time via ai_code_evaluator.py (Gemini-only, or pending faculty review if Gemini is unavailable).

Scope note: this is a lightweight, single-tenant sandbox suitable for a
trusted campus deployment — each run is isolated in its own subprocess, temp
directory, and CPU/memory/process-count limits, with no shell interpolation
(argv lists only, never shell=True). It is NOT a hardened multi-tenant
sandbox: there is no network-namespace isolation, no seccomp filter, and no
container/VM boundary (gVisor, Firecracker, Docker, or a judge service like
Judge0). For a public-facing deployment or one with adversarial students,
put a real sandboxing layer in front of this instead of trusting the OS
process boundary alone.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

RUN_TIMEOUT_SECONDS = 8
MAX_OUTPUT_CHARS = 8000
MAX_CODE_CHARS = 20000
MAX_STDIN_CHARS = 5000
MEMORY_LIMIT_BYTES = 256 * 1024 * 1024  # 256MB
# NumPy/Pandas import OpenBLAS, which otherwise tries to create one worker per
# CPU. A code-run subprocess is intentionally small (and has a process limit),
# so that default can fail before the student's first statement runs.
NUMERICAL_LIBRARY_ENV = {
    'OPENBLAS_NUM_THREADS': '1',
    'OMP_NUM_THREADS': '1',
    'MKL_NUM_THREADS': '1',
    'NUMEXPR_NUM_THREADS': '1',
    'VECLIB_MAXIMUM_THREADS': '1',
    'BLIS_NUM_THREADS': '1',
}


def _limit_resources(memory_limit_bytes=MEMORY_LIMIT_BYTES, nproc_limit=64):
    """
    Runs in the child process right after fork(), before exec().
    memory_limit_bytes=None skips the virtual-memory cap entirely — needed for
    runtimes (V8, the JVM) that reserve a large virtual address range up front
    regardless of how little memory the program actually uses; RLIMIT_AS would
    make them abort before running a single line. Those runtimes are capped
    via their own heap-size flags instead (see run_code below).

    RLIMIT_NPROC is a per-*uid* limit on Linux, not per-process — it's shared
    with every other subprocess (and thread) this server user currently has
    running, across every concurrent code run. Node's own startup alone opens
    several libuv/V8 background threads, so a low shared cap here made
    `uv_thread_create` fail and crash the runner under any real concurrency.
    Callers pass a roomier nproc_limit for thread-heavy runtimes like Node.
    """
    try:
        import resource
        cpu = RUN_TIMEOUT_SECONDS + 1
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        if memory_limit_bytes:
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
        resource.setrlimit(resource.RLIMIT_NPROC, (nproc_limit, nproc_limit))
        resource.setrlimit(resource.RLIMIT_FSIZE, (5 * 1024 * 1024, 5 * 1024 * 1024))
    except Exception:
        pass  # best-effort — the `resource` module isn't available on every platform


def _truncate(text):
    text = text or ''
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + '\n... [output truncated]'
    return text


def _run(cmd, cwd, stdin_text, memory_limit_bytes=MEMORY_LIMIT_BYTES, nproc_limit=64):
    try:
        child_env = os.environ.copy()
        # Override host values too: a deployment may have OPENBLAS configured
        # globally with a value that is unsafe inside the limited runner.
        child_env.update(NUMERICAL_LIBRARY_ENV)
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            input=stdin_text or '',
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
            env=child_env,
            preexec_fn=(lambda: _limit_resources(memory_limit_bytes, nproc_limit)) if os.name == 'posix' else None,
        )
        return {
            'stdout': _truncate(proc.stdout),
            'stderr': _truncate(proc.stderr),
            'exit_code': proc.returncode,
            'timed_out': False,
        }
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or '')
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or '')
        return {
            'stdout': _truncate(out),
            'stderr': _truncate(err) + f'\n[Execution timed out after {RUN_TIMEOUT_SECONDS}s]',
            'exit_code': None,
            'timed_out': True,
        }


def _detect_java_class_name(code):
    m = re.search(r'public\s+class\s+(\w+)', code)
    return m.group(1) if m else 'Main'


def _install_hint(linux_pkg, mac_pkg, windows_hint):
    """Give an actionable, platform-appropriate install command rather than
    just saying 'not installed' — this is a one-time server setup step, and
    the error message is what the faculty/admin actually sees when it's missing."""
    plat = sys.platform
    if plat.startswith('linux'):
        return f'On the server, run: sudo apt-get update && sudo apt-get install -y {linux_pkg}'
    if plat == 'darwin':
        return f'On the server, run: brew install {mac_pkg}'
    if plat.startswith('win'):
        return windows_hint
    return f'Install {linux_pkg} for this platform and ensure it is on PATH.'


def _python_binary():
    # Some servers (notably Windows, and some minimal distros) only expose
    # `python`, not `python3` — Django itself may be running under either.
    return shutil.which('python3') or shutil.which('python') or shutil.which('py')


def run_code(code, language, stdin_text=''):
    """
    Returns a dict: {stdout, stderr, exit_code, timed_out} on a normal run,
    or {error} (and nothing else) if the required toolchain isn't installed
    on this server — that fails soft with a clear, actionable message rather
    than 500ing.
    """
    language = (language or 'python').lower()
    code = code or ''
    stdin_text = stdin_text or ''
    if len(code) > MAX_CODE_CHARS:
        return {'error': 'Code is too long to run.'}
    if len(stdin_text) > MAX_STDIN_CHARS:
        return {'error': 'Custom input is too long.'}

    tmp_dir = tempfile.mkdtemp(prefix='coderun_')
    try:
        if language == 'python':
            python_bin = _python_binary()
            if not python_bin:
                return {'error': 'Python runtime was not found on this server. '
                                  + _install_hint('python3', 'python3', 'Install Python from https://www.python.org/downloads/ and make sure "Add python.exe to PATH" is checked during setup.')}
            path = os.path.join(tmp_dir, 'solution.py')
            with open(path, 'w') as f:
                f.write(code)
            return _run([python_bin, path], tmp_dir, stdin_text)

        if language == 'javascript':
            if not shutil.which('node'):
                return {'error': 'Node.js runtime was not found on this server. '
                                  + _install_hint('nodejs', 'node', 'Install Node.js from https://nodejs.org and restart the server.')}
            path = os.path.join(tmp_dir, 'solution.js')
            with open(path, 'w') as f:
                f.write(code)
            # V8 reserves a large virtual address range on startup regardless of
            # actual usage — RLIMIT_AS would abort it before it runs anything.
            # Cap the heap with Node's own flag and skip the OS-level AS limit.
            # Node also needs headroom in the shared per-uid thread count (see
            # _limit_resources) or it crashes on startup with
            # "Assertion failed: (0) == (uv_thread_create(...))".
            return _run(['node', '--max-old-space-size=192', path], tmp_dir, stdin_text,
                         memory_limit_bytes=None, nproc_limit=256)

        if language == 'cpp':
            if not shutil.which('g++'):
                return {'error': 'A C++ compiler (g++) was not found on this server. '
                                  + _install_hint('g++', 'gcc', 'Install MinGW-w64 or the "Desktop development with C++" workload in Visual Studio Build Tools, then ensure g++ is on PATH.')}
            src = os.path.join(tmp_dir, 'solution.cpp')
            binary = os.path.join(tmp_dir, 'solution.out')
            with open(src, 'w') as f:
                f.write(code)
            compiled = subprocess.run(
                ['g++', '-O2', '-std=c++17', src, '-o', binary],
                cwd=tmp_dir, capture_output=True, text=True, timeout=RUN_TIMEOUT_SECONDS,
            )
            if compiled.returncode != 0:
                return {
                    'stdout': '', 'stderr': _truncate(compiled.stderr),
                    'exit_code': compiled.returncode, 'timed_out': False, 'compile_error': True,
                }
            return _run([binary], tmp_dir, stdin_text)


        if language == 'java':
            if not shutil.which('javac') or not shutil.which('java'):
                return {'error': 'A Java JDK (javac) was not found on this server — a JRE alone is not enough, '
                                  'compiling needs the full JDK. '
                                  + _install_hint('default-jdk', 'openjdk', 'Install a JDK (e.g. Temurin) from https://adoptium.net and ensure javac is on PATH.')}
            class_name = _detect_java_class_name(code)
            src = os.path.join(tmp_dir, f'{class_name}.java')
            with open(src, 'w') as f:
                f.write(code)
            compiled = subprocess.run(
                ['javac', src], cwd=tmp_dir, capture_output=True, text=True, timeout=RUN_TIMEOUT_SECONDS,
            )
            if compiled.returncode != 0:
                return {
                    'stdout': '', 'stderr': _truncate(compiled.stderr),
                    'exit_code': compiled.returncode, 'timed_out': False, 'compile_error': True,
                }
            return _run(['java', '-Xmx192m', '-cp', tmp_dir, class_name], tmp_dir, stdin_text, memory_limit_bytes=None)

        return {'error': f'Unsupported language: {language}'}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

