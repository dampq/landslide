#!/usr/bin/env bash
# Keep the dependency lock on its validated Python minor version.
set -euo pipefail
cd "$(dirname "$0")/.."

is_python312() {
  "$1" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' >/dev/null 2>&1
}

if [ -x backend/.venv/bin/python ] && is_python312 backend/.venv/bin/python; then
  echo 'Using existing Python 3.12 virtual environment.'
  exit 0
fi

ashtaraksha_python=''
ashtaraksha_uv=''
for candidate in python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && is_python312 "$candidate"; then
    ashtaraksha_python="$(command -v "$candidate")"
    break
  fi
done

if [ -z "$ashtaraksha_python" ]; then
  echo 'Python 3.12 is required; preparing a project-local runtime with uv.'
  if command -v uv >/dev/null 2>&1; then
    ashtaraksha_uv="$(command -v uv)"
  else
    python3 -m venv .cache/python-tools
    .cache/python-tools/bin/python -m pip install --no-cache-dir uv==0.9.5
    ashtaraksha_uv="$PWD/.cache/python-tools/bin/uv"
  fi
  export UV_CACHE_DIR="$PWD/.cache/uv"
  export UV_PYTHON_INSTALL_DIR="$PWD/.cache/python"
  export UV_PYTHON_BIN_DIR="$PWD/.cache/python-bin"
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
  echo "Preserved the incompatible environment at $ashtaraksha_backup"
fi
if [ -n "$ashtaraksha_uv" ]; then
  "$ashtaraksha_uv" --native-tls venv --python "$ashtaraksha_python" --seed backend/.venv
else
  "$ashtaraksha_python" -m venv backend/.venv
fi
backend/.venv/bin/python --version
