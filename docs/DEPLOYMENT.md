# Development and deployment

## Runtime architecture

Browser → same-origin Vite development/preview proxy (or production reverse proxy) → FastAPI/Uvicorn → PostgreSQL 17 + PostGIS 3.5. Uploaded media is stored in PostgreSQL bytea columns with per-file, per-report and per-account limits. Pending offline reports/media live in the submitting browser's IndexedDB until synchronised.

FastAPI interactive API documentation is available on the backend at `/docs` and the generated contract at `/openapi.json`. Health checks execute a PostGIS query; an open port alone does not establish readiness. Migrations are explicit and idempotent (`cd backend && .venv/bin/python manage.py migrate`). Version 1 is recorded in `schema_migrations`; schema evolution needs new numbered migrations rather than editing already-published schema assumptions.

The repository's Compose file provisions the database only. Start the API and frontend with `npm run dev:all`. For a production-style local PWA demonstration, keep the API on port 8000, build, and use Vite preview on port 4173. Vite preview is for local validation, not a hardened public application server.

## Before public deployment

Use a maintained HTTPS reverse proxy to serve `dist/`, provide SPA fallback to `index.html`, proxy `/api` and `/health` to Uvicorn, and set an upload limit consistent with the API (11 MB per request, 10 MB per attachment). Keep PostgreSQL and Uvicorn private. Set `COOKIE_SECURE=true` and `APP_ORIGINS` to exact trusted website origins. If exposing FastAPI docs, treat them as public API documentation; business endpoints still enforce authentication.

Replace the development database password with a private secret and update `DATABASE_URL` securely. Do not put secrets in Git, browser configuration, URLs printed in logs or public artifacts. There are no built-in production accounts. Bootstrap an admin locally using the management command, then assign roles through the portal.

Sessions use random 256-bit tokens in HttpOnly SameSite=Strict cookies; only token hashes are stored. Passwords use salted scrypt. State-changing requests with an untrusted browser Origin are rejected. API responses are not cached. Set CSP/HSTS and rate/connection limits at the HTTPS reverse proxy appropriate to your deployment. Login attempts have a persistent account-keyed rate limit; use proxy-level limits for registration, uploads and overall public traffic. Handle account recovery through a separately approved administrator workflow; no unconfigured email-reset service is implied.

This release does not provide district-scoped authority access, public SMS, push messaging, a worker for automatic official alerts, antivirus scanning or a nationwide production deployment. In-app notifications require users to visit/refresh the site. Images undergo OpenCV quality measurement, not landslide classification. MP4 uploads are signature-checked and served as downloads; they are not transcoded or deeply decoded. Plan media scanning and stronger quotas before accepting anonymous high-volume public uploads.

## Backup and recovery

PostgreSQL's Docker named volume persists data between restarts; `docker compose down -v` deletes it and must not be used as a routine restart command. Stop services only when necessary. A snapshot/backup contains accounts, sessions and private incident media; keep it private.

```bash
mkdir -p /private/backup-location
# Use a private writable location outside the public frontend.
docker compose exec -T db pg_dump -U ashtaraksha -Fc ashtaraksha > /private/backup-location/ashtaraksha.dump
# Restore into a separately prepared database and validate before switching DATABASE_URL:
# docker compose exec -T db pg_restore -U ashtaraksha -d restored_database < /private/backup-location/ashtaraksha.dump
```

Check the command exit status, backup size, and a test restore. Never claim a backup is usable just because a file exists. Backups and real datasets are not committed in this repository.

## Cloud environment

Use the existing `/workspace/landslide` checkout; each cloud task is already isolated. Do not create a Git worktree unless explicitly requested. Retained dependencies may survive environment snapshots, but processes and containers must be checked/restarted. Run `docker compose up -d db`, verify `pg_isready`, run the migration, then `npm run dev:all`. Confirm `/health` returns PostgreSQL and PostGIS details and the frontend returns the app shell.

Restricted networking must permit `api.open-meteo.com` for weather and `tile.openstreetmap.org` for basemap tiles. Optional reference portals open in the user's browser; their data is not automatically downloaded. Never disable TLS verification to fix provider access. Existing labelled sample weather remains available if a live provider is blocked. Public map tiles cannot be promised offline.
