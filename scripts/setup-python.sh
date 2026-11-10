#!/usr/bin/env bash
# Use uv to seed pip, even when the system Python omits ensurepip.
set -euo pipefail
cd "$(dirname "$0")/.."

is_python312() {
  "$1" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' >/dev/null 2>&1
}

if [ -x backend/.venv/bin/python ] && is_python312 backend/.venv/bin/python && backend/.venv/bin/python -m pip --version >/dev/null 2>&1; then
  echo 'Using existing Python 3.12 virtual environment with pip.'
  exit 0
fi

ashtaraksha_python=''
for candidate in python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && is_python312 "$candidate"; then
    ashtaraksha_python="$(command -v "$candidate")"
    break
  fi
done

if command -v uv >/dev/null 2>&1; then
  ashtaraksha_uv="$(command -v uv)"
else
  echo 'Preparing a verified project-local uv executable (pip/ensurepip is not needed).'
  ashtaraksha_uv="$(python3 scripts/bootstrap-uv.py)"
fi
export UV_CACHE_DIR="$PWD/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PWD/.cache/python"
export UV_PYTHON_BIN_DIR="$PWD/.cache/python-bin"

if [ -z "$ashtaraksha_python" ]; then
  echo 'Python 3.12 is required; preparing a project-local runtime with uv.'
  "$ashtaraksha_uv" --native-tls python install 3.12
  ashtaraksha_python="$("$ashtaraksha_uv" --native-tls python find --managed-python 3.12)"
fi

if ! is_python312 "$ashtaraksha_python"; then
  echo 'Could not prepare Python 3.12; the existing environment has been preserved.' >&2
  exit 1
fi

if [ -e backend/.venv ]; then
  ashtaraksha_backup="backend/.venv-backup-$(date +%s)-$$"
  mv backend/.venv "$ashtaraksha_backup"
  echo "Preserved the incompatible or incomplete environment at $ashtaraksha_backup"
fi
"$ashtaraksha_uv" --native-tls venv --python "$ashtaraksha_python" --seed backend/.venv
backend/.venv/bin/python --version
backend/.venv/bin/python -m pip --version
