#!/usr/bin/env bash
# Installs server-side language runtimes used by the exam Run Code feature.
# Ubuntu/Debian usage:
#   cd backend
#   sudo bash scripts/install_runtimes.sh
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo bash scripts/install_runtimes.sh" >&2
  exit 1
fi
if ! command -v apt-get >/dev/null 2>&1; then
  cat >&2 <<'EOF'
apt-get not found. Install these manually for your OS:
  python3, nodejs, g++/build-essential, default-jdk (javac + java)
EOF
  exit 1
fi
apt-get update -y
apt-get install -y python3 nodejs npm build-essential default-jdk
python3 --version || true
node --version || true
g++ --version | head -1 || true
javac -version || true
java -version 2>&1 | head -1 || true
echo "Done. Restart Django/gunicorn/runserver so PATH is refreshed."


