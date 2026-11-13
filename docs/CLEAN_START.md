# Run with your own data

From the repository root, after installing dependencies with `bash scripts/setup.sh` (without `--demo`):

```bash
npm run dev:clean
```

Stop another development server first if it uses 8000/5173. The command starts local Compose PostgreSQL, waits for authenticated readiness, creates `ashtaraksha_clean` only if missing, applies migrations and starts FastAPI/Vite against it. Rerunning keeps your new records and accounts. It does not copy, delete or overwrite the original `ashtaraksha` database. The clean command is intentionally limited to a localhost development database, not a remote deployment.

The dashboard starts empty. Register your own account through the website and submit your own reports with GPS/photos. Registration creates a citizen account. For official workflows, promote your account locally against **the clean database**. With the default local Compose credentials:

```bash
cd backend
DATABASE_URL='postgresql+psycopg://ashtaraksha:local-development@127.0.0.1:5433/ashtaraksha_clean' .venv/bin/python manage.py set-role YOUR_EMAIL official
```

Use `admin` instead of `official` if you need Administration and data imports. Sign out and back in after promotion. If you configured a different local database password/URL, supply the matching DATABASE_URL privately rather than copying credentials into tracked files. The default `manage.py` database is the original database, so keep the clean override when administering clean-mode accounts.

Officials can enter real monitoring locations, teams, roads and other records through the portals; administrators can import attributed records using the documented import format. Keep actual sources and dates. Report verification, response planning and warnings require their normal official actions; empty pages are expected until records are entered. Do not run `seed-demo`, use `setup.sh --demo`, or trigger sensor/sample-weather actions if you want only your own data.

Both supplied models remain installed. Their explicitly labelled **Load supplied example** panel is optional, runs only on request, and never saves an example as a real assessment. For your own assessments enter genuinely sourced environmental inputs. Automatic extraction from map coordinates remains pending. Live weather/online tiles still require provider access; empty or unavailable information must not be presented as live data. The bundled geographic reference map is actual attributed cartographic context and is retained.

Development tests deliberately use separate `_test` and `_e2e_test` databases with fixtures; these do not populate `ashtaraksha_clean`.

To inspect the previous demonstration environment, stop clean mode and run `npm run dev:all` with the original database configuration. The old database is retained as a recoverable backup, not permanently erased. To continue your own-data environment, always use `npm run dev:clean`.

Validation on 13 November 2026: clean database had 0 accounts/0 records, original database remained at 0 accounts/56 records, API health confirmed PostgreSQL/PostGIS and the frontend login shell responded. Clean startup performs no seeding.
