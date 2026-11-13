# Ashtaraksha

A responsive, web-based landslide monitoring and reporting platform for North East India. Built with **React, Vite, Tailwind, FastAPI, PostgreSQL/PostGIS, Leaflet/OpenStreetMap, Recharts and OpenCV**, with an installable PWA shell and a persistent offline reporting queue.

This is a student demonstration and decision-support project, not an operational disaster warning service. All seeded geographic, weather, population and sensor data is explicitly synthetic. No restricted government data, paid satellite service or physical sensor is required. The platform does **not** train or substitute a prediction model.

## Run without demonstration data

Use `npm run dev:clean` after dependency setup. It starts a separate unseeded local database and preserves the previous database as a backup. Register your account and add your own reports, monitoring locations and teams. See [clean startup](docs/CLEAN_START.md) for setup and role promotion. Rerunning retains your data. Do not use `--demo` or sample/simulator actions when checking real records.

## Quick start

Requirements: Node.js 22.12+ (24 tested), Python 3.12, Docker with Compose, and ports 5433, 8000 and 5173 available. Commands below run from the repository root unless stated otherwise.

```bash
npm ci
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.lock
docker compose up -d db
# Wait for database readiness; repeat until the health check succeeds.
docker compose exec -T db pg_isready -h 127.0.0.1 -U ashtaraksha -d ashtaraksha
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

## Automatic environmental assessment

If `model-handoff/frnd_raster_data.zip` is present locally, run `npm run prepare:rasters` after setup. It safely prepares private local data and verifies both real-raster reference examples before enabling coordinate extraction. See [automatic assessment](docs/AUTOMATIC_ASSESSMENT.md). Real-data verification must run on the machine holding the archive; code/synthetic tests alone do not establish readiness. Both models and the clean working database are preserved.

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

The worker caches **the application shell, bundled assets and the public-domain regional reference map**. It never caches private API responses or bulk-downloads OpenStreetMap tiles. Report text and actual attachment files are written to IndexedDB before submission, scoped to the current account, and survive reloads. Reconnection attempts sync only after confirming the same account with the server. Stable client IDs and media hashes make network retries idempotent. Errors remain visible in the queue; successfully uploaded files are removed individually before the final queue entry is deleted. Other accounts cannot accidentally sync someone else's pending reports.

Existing submitted data, fresh alerts and external map tiles require connectivity. Offline login is limited to resuming the last locally remembered account view; server authorization is always enforced when online. Local pending files are not encrypted: use trusted devices and delete pending entries before sharing a device. Browser storage may be evicted; sync promptly.

The interface has complete English, Hindi and Assamese catalogs for page descriptions, form labels, navigation, status messages and actions. Source citations, user-entered reports, arbitrary imported metadata and technical identifiers retain their original content. Unknown server diagnostics are available under a translated technical-details disclosure. Native-speaker review is recommended before a public rollout. Run `npm run check:i18n` to catch untranslated JSX text, missing keys and mismatched placeholders.

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

API tests cover authentication/permissions, CSRF origin checks, report privacy and review, concurrent retries, attachment validation/deduplication, OpenCV, partial sync, PostGIS queries, alert lifecycle and subscriptions, atomic deployment, both supplied models, helper parity, imputation and checksum behaviour, weather failures, simulation, imports, role-session revocation, CSV escaping and analytics. Browser tests exercise connected citizen/official/admin workflows, GPS/media, actual offline reload with attachment sync, map layers, mobile layout and language switching.

## Configuration

Export environment variables before starting the backend; see `backend/.env.example`. No automatic `.env` loading is performed. The local database password in Compose is a development default, bound to loopback; set a private password and matching `DATABASE_URL` for any shared deployment. The database URL must use `postgresql+psycopg://`.

Live forecast requests require `api.open-meteo.com`; map tiles require `tile.openstreetmap.org`. Optional external source portals have their own access terms. In restricted cloud environments, allow those exact domains in environment settings. If they are blocked, the application remains demonstrable using labelled synthetic weather/geographic records; live refresh reports the failure.

## GitHub Codespaces

Create a Codespace from this repository, wait for its initial setup to finish, then run these commands in one terminal:

```bash
bash scripts/setup.sh --demo && npm run dev:all
```

Open port **5173** from the **Ports** panel. Keep its visibility private. Ports 8000 and 5433 do not need browser forwarding. The combined start command automatically trusts this Codespace's exact forwarded website origin, enables HTTPS cookies, binds Vite for forwarding and configures its development WebSocket. No manual `APP_ORIGINS` export is needed for standard Codespaces addresses.

The setup script keeps npm's cache in the ignored `.cache/npm` folder inside the checkout; it does not need permission to create `/workspace`. If an older failed install left partial `node_modules`, stop other installation processes and rerun the setup command. `npm ci` refreshes generated dependencies; no application data or database volume needs deleting. Wait for setup to succeed before starting the app (`&&` enforces this).

The setup script uses **Python 3.12**, even if Codespaces defaults to Python 3.14. It reuses an installed 3.12 interpreter or downloads a project-local runtime using uv with TLS/checksum verification enabled. An incompatible `backend/.venv` is moved to an ignored `backend/.venv-backup-*` folder before creating the correct environment. No database data is removed. The old environment can be deleted later when no longer needed.

On minimal Debian/Ubuntu interpreters, `ensurepip` may be absent. Setup uses `uv venv --seed`, which installs pip without the OS `python3.12-venv` package. If uv is missing, a standard-library bootstrap downloads its official PyPI wheel over HTTPS and checks its published SHA-256 before extracting the executable. Incomplete virtual environments without pip are repaired automatically on rerun. No sudo or system-package changes are needed.

For a freshly created PostgreSQL volume, setup waits for an authenticated connection through the application's configured `DATABASE_URL` before migrating. The image's temporary initialization server may accept local socket connections before its mapped TCP port is ready; container startup alone is not sufficient. You can rerun the check directly with `cd backend && .venv/bin/python manage.py wait-db`. Do not delete the database volume to resolve a startup delay.

### Background map blocked (403)

A repeated “Access blocked” image is a response from the tile provider, not a landslide layer. OpenStreetMap's volunteer servers enforce their [tile usage policy](https://operations.osmfoundation.org/policies/tiles/), including attribution and valid browser referrers. Shared-network restrictions can also affect access. Open the forwarded website in a normal browser tab instead of an embedded editor preview. The app explicitly sends an appropriate referrer and checks one visible tile's HTTP status before rendering the basemap; a blocked layer falls back to a bundled regional reference map while geographic markers remain visible. It does not proxy or change OpenStreetMap hostnames to evade a denial.

For an alternative, CARTO provides an OpenStreetMap-derived basemap with a free tier, but its current terms require an API key. Obtain your own key from https://carto.com/basemaps/apikey/ and review its usage limits. Add the following to an ignored `.env.local` file in the repository root, then restart Vite (or rebuild for production):

```dotenv
VITE_MAP_PROVIDER=carto
VITE_CARTO_API_KEY=YOUR_CARTO_BASEMAP_KEY
```

These `VITE_` settings are public browser configuration: use a browser-appropriate key and provider-supported restrictions, never a private backend credential. CARTO requests go to `a.basemaps.cartocdn.com`; allow this host where network policy requires it. Both OpenStreetMap and CARTO attribution are displayed. Default mode is `auto`: try OpenStreetMap and retain the bundled reference if online access fails. The map selector also offers `reference` for offline use, `osm`, and configured `carto`. No paid service or API key is required for the reference map. Tiles are never bulk-cached; the offline reference is a separately licensed vector dataset, not copied street tiles.

## Website acceptance and external services

The map always has a public-domain geographic reference for the eight North Eastern states, with nearby country context, even when a tile server refuses requests. Select **Regional reference (offline)** to avoid external tile requests. This layer is cartographic context, not a street/terrain map or authoritative border survey. Natural Earth attribution and provenance are bundled in `public/reference-map-source.json`; `python3 scripts/prepare-reference-map.py` can reproduce it from checksum-pinned upstream files.

The weather page distinguishes **Sample weather — simulated** from **Open-Meteo weather — modelled**, shows timestamps/staleness, and offers officials an explicit **Load sample weather** action. It will not overwrite a cached live forecast with samples without confirmation. A live-provider failure retains the existing cache; it never silently generates data. Samples satisfy the permitted demonstration path and must not be used as current conditions or warnings.

To check actual service access on the machine where you run the website:

```bash
cd backend
.venv/bin/python manage.py check-services
```

The read-only command checks PostgreSQL/PostGIS and an actual Open-Meteo response, without printing credentials or changing records. It exits nonzero when the live provider cannot be verified; this does not disable labelled demonstrations. Tile authorization must be checked in the real browser, not inferred from a server-side probe.

See [validation evidence](docs/VALIDATION.md) for the completed website acceptance tests and the precise remaining external handovers. Both supplied Random Forest versions are integrated: V1 is the default and V2 an experimental comparison. Their scores are relative presence-background scores, not calibrated probabilities or warnings. See the model integration guide for input sources and limitations.

### Registration and sign-in feedback

New accounts require a name, valid email and a **12–128 character password**. Sign-in uses the email/password of a registered account; arbitrary demo credentials are not accepted. Validation is displayed inside the page instead of relying on a browser popup that may prevent submission invisibly. Registration creates the account first, then attempts automatic sign-in; if that second step fails, the page confirms account creation and lets the user retry sign-in without registering again.

The client confirms the authenticated session before opening the dashboard. If an embedded browser or cookie settings block the session cookie, it displays a specific message; open the forwarded website in a normal browser tab and allow that site's cookies. Requests time out rather than leaving the submit button busy indefinitely. Backend password creation policy, HttpOnly/SameSite cookie protection and exact trusted-origin checks remain enforced.
