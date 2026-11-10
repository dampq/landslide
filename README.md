# Ashtaraksha

A responsive, web-based landslide monitoring and reporting platform for North East India. Built with **React, Vite, Tailwind, FastAPI, PostgreSQL/PostGIS, Leaflet/OpenStreetMap, Recharts and OpenCV**, with an installable PWA shell and a persistent offline reporting queue.

This is a student demonstration and decision-support project, not an operational disaster warning service. All seeded geographic, weather, population and sensor data is explicitly synthetic. No restricted government data, paid satellite service or physical sensor is required. The platform does **not** train or substitute a prediction model.

## Quick start

Requirements: Node.js 22.12+ (24 tested), Python 3.10+ (3.12 tested), Docker with Compose, and ports 5433, 8000 and 5173 available. Commands below run from the repository root unless stated otherwise.

```bash
npm ci
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.lock
docker compose up -d db
# Wait for database readiness; repeat until the health check succeeds.
docker compose exec -T db pg_isready -U ashtaraksha -d ashtaraksha
cd backend
.venv/bin/python manage.py migrate
# Optional, repeatable, clearly labelled demonstration records for all 8 NE states:
.venv/bin/python manage.py seed-demo
cd ..
npm run dev:all
```

The frontend uses port 5173; the FastAPI server uses 8000. Vite proxies `/api` and `/health` to the backend, keeping authentication on the same origin. `Ctrl+C` stops both services. The database volume survives container restarts. No default application accounts or passwords are created.

Register through the website to create a **citizen** account. To bootstrap an administrator, either promote your registered account locally or create an account through the interactive management command:

```bash
cd backend
.venv/bin/python manage.py set-role your-email@example.com admin
# Alternative: prompts privately for a password, never puts it in command history:
.venv/bin/python manage.py create-user your-email@example.com --name 'Your Name' --role admin
```

Administrators can assign field-official and administrator roles in the Administration portal. Public registration cannot select an elevated role. Account changes revoke existing sessions. Citizens see only their own reports and attachments; officials and administrators review reports.

The previous demo-only frontend and SQLite/Waitress backend have been replaced. Any ignored local SQLite files in the retired backend directory are retained for recovery; they are **not** silently migrated into PostgreSQL.

For repeatable Linux/cloud setup, `bash scripts/setup.sh --demo` installs dependencies, starts PostgreSQL, applies the migration and seeds labelled samples. Omit `--demo` to preserve an empty dataset.

## Use the platform

1. A citizen registers, captures GPS (browser permission required), enters an incident, attaches photographs or MP4 video, and submits it.
2. A field official reads the verification queue, downloads media, reviews OpenCV image-quality measurements and records a verification/rejection note. Verified reports may be resolved.
3. Officials manage locations, roads, infrastructure, historical events and population records. Map layer switches filter actual PostGIS records. Selecting a monitoring point opens a geodesic-radius exposure estimate.
4. Weather refresh retrieves Open-Meteo modelled past rainfall and forecasts. Provider errors preserve the last cache and return an explicit error. Samples never masquerade as provider responses.
5. Sensor simulation creates clearly marked synthetic rainfall, soil-moisture and ground-movement readings and bounded reading history. It never generates ML probabilities or automatically publishes alerts.
6. Officials create alert drafts, approve with a review note and then publish to subscribers' in-app inboxes. Published warnings cannot be edited. Resolving a warning closes it. No external SMS is sent.
7. Response priorities use a documented planning heuristic, not ML. Team assignment is transactional: one team cannot receive two concurrent active deployments. Deployments advance from En Route to On Site to Completed, or are cancelled.
8. Administrators manage roles/access, import attributed JSON/point GeoJSON datasets and review audit records. Analytics and CSV downloads use stored records and retain provenance/simulation labels.

See [requirements and acceptance](docs/REQUIREMENTS.md), [model handover](docs/MODEL_INTEGRATION.md), [data sources and import](docs/DATA_SOURCES.md), and [deployment](docs/DEPLOYMENT.md).

## Offline and PWA

```bash
npm run build
npm run preview -- --host 127.0.0.1 --port 4173
```

Keep the API running on 8000. The production build generates a versioned service worker and manifest. Open the website online once and allow the worker to activate before testing offline reload. HTTPS is required outside localhost.

The worker caches **only the application shell and bundled assets**. It never caches private API responses or bulk-downloads OpenStreetMap tiles. Report text and actual attachment files are written to IndexedDB before submission, scoped to the current account, and survive reloads. Reconnection attempts sync only after confirming the same account with the server. Stable client IDs and media hashes make network retries idempotent. Errors remain visible in the queue; successfully uploaded files are removed individually before the final queue entry is deleted. Other accounts cannot accidentally sync someone else's pending reports.

Existing submitted data, fresh alerts and external map tiles require connectivity. Offline login is limited to resuming the last locally remembered account view; server authorization is always enforced when online. Local pending files are not encrypted: use trusted devices and delete pending entries before sharing a device. Browser storage may be evicted; sync promptly.

Core navigation, reporting and action labels support English, Hindi and Assamese. User-generated text, source attribution, scientific feature names, detailed diagnostics and some secondary descriptions remain in their original language. Obtain native-speaker review before a public rollout.

## Tests

Backend integration tests use a **separate PostgreSQL/PostGIS database**, never a SQLite substitute. The database name must end in `_test` because tests truncate its application tables.

```bash
docker compose exec -T db createdb -U ashtaraksha ashtaraksha_test
backend/.venv/bin/python -m pytest tests/test_api.py -q
npm run build
# Separate browser database, seeded only with test accounts:
docker compose exec -T db createdb -U ashtaraksha ashtaraksha_e2e_test
npm run test:e2e
```

`createdb` is needed only once per database. Stop development servers before running browser tests: Playwright starts an isolated API database on port 8000 and the built frontend on 4173. Chromium is required; configure `CHROMIUM_PATH` if it is not `/usr/bin/chromium`. Alternatively install the official Playwright browser and adapt the executable setting. Test-account credentials exist only in the test database and test source.

API tests cover authentication/permissions, CSRF origin checks, report privacy and review, concurrent retries, attachment validation/deduplication, OpenCV, partial sync, PostGIS queries, alert lifecycle and subscriptions, atomic deployment, missing-model and checksum behaviour, weather failures, simulation, imports, role-session revocation, CSV escaping and analytics. Browser tests exercise connected citizen/official/admin workflows, GPS/media, actual offline reload with attachment sync, map layers, mobile layout and language switching.

## Configuration

Export environment variables before starting the backend; see `backend/.env.example`. No automatic `.env` loading is performed. The local database password in Compose is a development default, bound to loopback; set a private password and matching `DATABASE_URL` for any shared deployment. The database URL must use `postgresql+psycopg://`.

Live forecast requests require `api.open-meteo.com`; map tiles require `tile.openstreetmap.org`. Optional external source portals have their own access terms. In restricted cloud environments, allow those exact domains in environment settings. If they are blocked, the application remains demonstrable using labelled synthetic weather/geographic records; live refresh reports the failure.
