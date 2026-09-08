# "Run Code" feature — server runtime requirements

The exam room's **Run Code** button executes a student's code server-side
(see `portal/code_runner.py`). Each language needs its runtime/compiler
installed and on `PATH` on whichever machine runs `manage.py runserver` /
your production Django process — installing a Python package is not enough,
these are actual language toolchains:

| Language              | Needs on PATH   | Ubuntu/Debian                              | macOS (Homebrew)     | Windows                                                              |
|------------------------|-----------------|---------------------------------------------|------------------------|-----------------------------------------------------------------------|
| Python                 | `python3` (or `python`) | usually preinstalled                 | `brew install python3` | usually preinstalled; check "Add python.exe to PATH" during install   |
| JavaScript             | `node`          | `sudo apt-get install -y nodejs`             | `brew install node`    | install from https://nodejs.org                                       |
| C++                    | `g++`           | `sudo apt-get install -y g++`                | `brew install gcc`     | install MinGW-w64, or the "Desktop development with C++" workload in Visual Studio Build Tools |
| Java                   | `javac` **and** `java` | `sudo apt-get install -y default-jdk` | `brew install openjdk` | install a JDK (e.g. Temurin) from https://adoptium.net                |

A **JRE alone is not enough for Java** — compiling a submission needs the
full JDK (`javac`), not just the runtime (`java`).

If a runtime is missing, `run_code()` fails soft: the student gets a clear
"X was not found on this server" message (with the install command above)
instead of a generic 500 error, and every other language keeps working.

After installing anything, **restart the Django process** so the new PATH
is picked up — `shutil.which()` only sees what's on PATH when Python
started.

To verify what your server currently has available:

```bash
python3 --version   # or: python --version
node --version
g++ --version
javac --version && java --version
```


