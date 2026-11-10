#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npm ci --cache "$PWD/.cache/npm" --no-audit --no-fund
bash scripts/setup-python.sh
backend/.venv/bin/python -m pip install --no-cache-dir -r backend/requirements.lock
docker compose up -d db
(cd backend && .venv/bin/python manage.py wait-db)
(cd backend && .venv/bin/python manage.py migrate)
if [ "${1:-}" = '--demo' ]; then (cd backend && .venv/bin/python manage.py seed-demo); fi
