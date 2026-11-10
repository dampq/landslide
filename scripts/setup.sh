#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
npm ci --cache /workspace/.npm-cache --no-audit --no-fund
if [ ! -x backend/.venv/bin/python ]; then python3 -m venv backend/.venv; fi
backend/.venv/bin/python -m pip install --no-cache-dir -r backend/requirements.lock
docker compose up -d db
ready=0
for attempt in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U ashtaraksha -d ashtaraksha >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [ "$ready" != 1 ]; then echo 'PostgreSQL failed to become ready; inspect docker compose logs db.' >&2; exit 1; fi
(cd backend && .venv/bin/python manage.py migrate)
if [ "${1:-}" = '--demo' ]; then (cd backend && .venv/bin/python manage.py seed-demo); fi
