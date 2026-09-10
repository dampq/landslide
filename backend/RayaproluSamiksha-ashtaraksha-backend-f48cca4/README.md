# Ashtaraksha standalone backend

A separate Python + SQLite backend for the NER-SURAKSHA / Ashtaraksha project. All code, dependencies, configuration and tests are contained in this folder. The existing frontend and GitHub repository have not been edited. You can copy this folder into its own repository or add it to your project yourself.

## Start on this computer

Open a terminal inside `ashtaraksha-backend`, then run:

```powershell
python run.py
```

Waitress has already been downloaded into the ignored `.deps` directory on this computer. If `python` is not on PATH, use the available bundled interpreter:

```powershell
& 'C:\Users\Rayaprolu Samiksha\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' run.py
```

API: http://127.0.0.1:8000
Health: http://127.0.0.1:8000/health
OpenAPI contract: http://127.0.0.1:8000/openapi.json

Stop with Ctrl+C. `python run.py --port 8001` selects another port. `python run.py --dev` starts the dependency-free development server. Running the API does not connect or alter your frontend.

## Set up on another computer

Requires Python 3.10 or later. These commands do not require virtual-environment activation:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run.py
```

Use that virtual environment's Python for the commands below. The optional `.env` is loaded from this backend folder; existing shell environment variables take precedence. Relative database and model paths resolve inside this folder.

## Create accounts and optional demo data

Public registration creates citizens. Authority accounts are created locally, not through an unrestricted public API:

```powershell
python manage.py create-authority official@example.com
```

Enter a password of at least 12 characters at the hidden prompt. Citizens submit and read their own reports. Authorities verify reports, manage monitoring records, review alerts and coordinate teams. Authorities currently have project-wide access, not separate district scopes.

The database starts empty. Optional, clearly marked synthetic demonstration records:

```powershell
python manage.py seed-demo
```

This is repeatable and creates a demo location, road, sensor, village and team. It creates no accounts, notifications, fake model or claimed live predictions.

## Implemented modules

| Module | Behavior |
| --- | --- |
| Accounts | Salted scrypt passwords, hashed session tokens, 24-hour expiry, logout, password change revoking all sessions, authority permissions |
| Reports | Geo-tagged reports, authority verification, private report access, stable client IDs and concurrent retry deduplication |
| Media | PNG/JPEG/WebP/MP4 storage, authenticated retrieval, SHA-256 deduplication, upload size and account quotas |
| Monitoring | Locations, roads, villages, infrastructure, historical events and satellite metadata; individual and batch ingestion |
| Sensors | Rotatable per-device credentials, timestamped history, units, configurable thresholds, stale-device status |
| Weather | Open-Meteo hourly ingestion, persistent cache, stale flags, rolling rainfall totals, scheduled refresh |
| Risk | Reproducible screening index, optional trained logistic model, persisted assessments and weather-linked scenarios |
| Alerts | Threshold-triggered review records, approval, acknowledgement, resolution and publication |
| Notifications | In-app inbox, subscriptions, reviewed translations, dry-run SMS, Twilio adapter, durable outbox and delivery polling |
| Response | Impact-based priority index, atomic team assignments, deployment transitions and release of teams |
| GIS and analytics | GeoJSON point layers, bounding-box filtering, state risk summaries and historical event counts |
| Offline API | Partial-success batch report sync and cursor-based change feed with report privacy |
| Operations | WSGI/Waitress entry point, worker, audit/change log, rate limits, SQLite backup command, Docker configuration and tests |

## API conventions

Use JSON request bodies and `Authorization: Bearer TOKEN`, except public health, OpenAPI, registration and login. Telemetry uses a device key in the same Bearer header instead of a user session. Errors return `{ "error": "message" }` with an appropriate HTTP status.

IDs are server-generated UUIDs. Times such as `observedAt`, `updatedAt` and reading `at` are UTC Unix seconds. Coordinates are numeric, not strings. Lists of records return `{items, total, limit, offset}`. Default limit is 100, maximum 500. Record lists support `state`, `district`, `level`, `severity`, `status` and `locationId` exact filters.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register`, `/api/auth/login` | Email and password |
| GET | `/api/auth/me` | Current account |
| POST | `/api/auth/logout` | Revoke session |
| POST | `/api/auth/password` | `currentPassword`, `newPassword`; revokes all sessions |
| GET/POST | `/api/reports` | List accessible reports / submit |
| GET/PATCH | `/api/reports/{id}` | Read / authority verification |
| GET/POST | `/api/{collection}` | List / authority create |
| GET/PATCH | `/api/{collection}/{id}` | Read / authority update |
| POST | `/api/import` | Authority batch: `{collection, items}`; per-item results, not all-or-nothing |
| POST | `/api/reports/{id}/media` | `{filename, base64}` |
| GET | `/api/reports/{id}/media` | Attachment metadata |
| GET | `/api/media/{id}` | Authenticated JSON including base64 content |
| POST | `/api/media/{id}/analyze` | Authority calls configured image classifier |
| POST | `/api/sensors/{id}/key` | Authority rotates device key; returned only once |
| POST | `/api/telemetry` | Device submits a reading |
| GET | `/api/sensors/{id}/readings` | Paginated sensor history |
| POST | `/api/weather/{locationId}/refresh` | Authority refreshes provider cache |
| GET | `/api/weather/{locationId}` | Read cached weather and stale flag |
| POST | `/api/predictions` | Authority evaluates current risk |
| POST | `/api/forecast/{locationId}` | Authority evaluates 6/12/24/48-hour rainfall scenarios |
| GET | `/api/predictions`, `/api/forecasts` | Assessment history; supports locationId filter |
| POST | `/api/alerts/{id}/approve` | Authority records a review `note` |
| POST | `/api/alerts/{id}/acknowledge` | Acknowledge |
| POST | `/api/alerts/{id}/resolve` | Resolve |
| POST | `/api/alerts/{id}/publish` | Create notifications for subscribed accounts |
| GET/PATCH | `/api/settings` | Language, SMS/in-app preferences and state subscriptions |
| GET | `/api/notifications` | Own notification inbox and status |
| POST | `/api/notifications/{id}/read` | Mark own notification read |
| POST | `/api/notifications/{id}/retry` | Authority requeues uncertain SMS after `providerChecked: true` |
| GET | `/api/response/priorities` | Authority planning priorities |
| POST | `/api/deployments` | Authority assignment: `{teamId, locationId, notes}` |
| POST | `/api/deployments/{id}/status` | Authority changes deployment status |
| GET | `/api/deployments` | Authority deployment history |
| GET | `/api/gis?bbox=91,25,92,26` | GeoJSON point layers; bbox is west,south,east,north |
| GET | `/api/dashboard`, `/api/analytics` | Stored-data aggregates |
| POST | `/api/sync` | `{reports: [...]}`; up to 100 reports with independent results |
| GET | `/api/sync?cursor=0&limit=100` | Change feed; persist nextCursor and continue while hasMore |
| GET | `/api/audit`, `/api/system` | Authority audit feed and worker/provider configuration status |

Writable collections: `locations`, `sensors`, `roads`, `alerts`, `teams`, `villages`, `infrastructure`, `history`, `satellite`. `predictions`, `forecasts`, `deployments` and `imageAnalyses` are read through collection routes and created through their dedicated workflows. Historical records are retained; there are no destructive delete routes.

Required fields for monitoring records:

| Collection | Fields |
| --- | --- |
| reports | clientId, incident, location, lat, lng, severity, description |
| locations | name, district, state, lat, lng, level; optional score, population, hospitalDistanceKm, slope, historicalEvents |
| sensors | location, type, value (display string), status, battery; locationId, feature and unit for automatic monitoring |
| roads | name, route, district, status; locationId links road disruption to response prioritisation |
| alerts | type, location, description, action, severity; optional state, locationId, translations |
| teams | name, status |
| villages | name, lat, lng; optional population, locationId |
| infrastructure | name, type, lat, lng; optional locationId |
| history / satellite | name, lat, lng, observedAt, source; optional locationId and source metadata |

Levels: `Low`, `Moderate`, `High`, `Critical`.
Report status: `Awaiting Verification`, `Verified`, `Rejected`, `Resolved`.
Road status: `Open`, `Partially Blocked`, `Blocked`, `Under Verification`.
Team status: `Available`, `En Route`, `Deployed`.
Deployment transitions: `En Route -> On Site -> Completed`, or cancellation from either active state. Concurrent assignments to one team return a conflict; completing/cancelling releases the team.

## Test requests without frontend changes

With the backend running, use another PowerShell terminal:

```powershell
$credentials = @{email='citizen@example.com'; password='local-demo-password-123'} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/auth/register -Method Post -ContentType 'application/json' -Body $credentials
$session = Invoke-RestMethod http://127.0.0.1:8000/api/auth/login -Method Post -ContentType 'application/json' -Body $credentials
$headers = @{Authorization="Bearer $($session.token)"}
$report = @{clientId='device1-report1'; incident='Road Blockage'; location='Test location'; lat=25.297; lng=91.582; severity='High'; description='Development test only'} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/reports -Method Post -Headers $headers -ContentType 'application/json' -Body $report
Invoke-RestMethod http://127.0.0.1:8000/api/reports -Headers $headers
```

Retry the same report using the same clientId. A new report needs a new clientId. Reusing an ID with different content returns the original submission. Media retries deduplicate identical bytes on the same report. Uploads accept up to 10 MB per file, 10 files per report and 100 MB per account by default. Supported file signatures are checked; files are not antivirus-scanned or fully decoded. Downloads return base64 JSON so files are never executed or served as HTML.

## Sensor and automatic monitoring setup

1. An authority creates a location with supplied `slope` (degrees) and `historicalEvents` (count).
2. Create sensors linked by locationId. Set `feature` to a supported feature below and configure its unit.
3. Rotate each sensor key and securely provision the returned deviceKey to that device.
4. Devices post `{sensorId, clientId, observedAt, value, unit}` to `/api/telemetry`. Optional battery is 0-100. Out-of-order observations remain in history without replacing newer state.
5. Run `python worker.py` in another terminal. It refreshes weather at most hourly, evaluates locations with complete fresh inputs, marks stale sensors offline, and processes notifications. `python worker.py --once` performs one cycle.

| Risk feature | Unit | Source for worker |
| --- | --- | --- |
| rainfall24h | mm | Fresh sensor or cached weather model total |
| rainfall72h | mm | Fresh sensor or cached weather model total |
| soilMoisture | % | Fresh sensor reporting the project's saturation-percent convention |
| groundMovement | mm/h | Fresh sensor |
| slope | deg | Supplied location value or fresh sensor |
| historicalEvents | count | Supplied location value or fresh sensor |

The worker uses observations less than one hour old. Missing inputs skip prediction; they never become invented zeroes. Open-Meteo volumetric soil moisture is preserved in its original units and is not silently treated as saturation percentage. Sensor `warningAbove` and `criticalAbove` can set thresholds; otherwise fresh readings are Online. The worker marks sensors Offline after an hour without a current observation.

## Risk model and forecast behavior

Current assessment body:

```json
{
  "locationId": "LOCATION_UUID",
  "observedAt": 1788960000,
  "source": "Your sensor or validated dataset source",
  "inputs": {
    "rainfall24h": 180,
    "rainfall72h": 450,
    "soilMoisture": 90,
    "slope": 55,
    "groundMovement": 8,
    "historicalEvents": 15
  }
}
```

Replace observedAt with the actual observation timestamp; current prediction inputs older than 24 hours are rejected. Without MODEL_PATH the backend returns a transparent weighted screening index, with `probability: null`, `confidence: null` and `operationallyValidated: false`. Level boundaries are 40/65/85. A high/critical score creates a deduplicated review alert, not an automatic public warning.

The forecast endpoint accepts `{inputs, observedAt}`, requires a weather cache under one hour old, and recomputes rolling rainfall windows at 6, 12, 24 and 48 hours. Other inputs are held constant and this assumption is included in the result.

To train a real model, supply your labelled CSV containing the six feature columns and `landslideOccurred` (0 or 1):

```powershell
python train_model.py your-labelled-data.csv --output models/landslide.json
```

At least 10 observations per class are required to exercise the training pipeline; that is not a claim of statistical sufficiency. It writes a portable JSON logistic model, dataset hash and held-out accuracy, precision, recall and Brier score. Set MODEL_PATH in .env and restart. The split is a reproducible stratified random holdout. Spatial/temporal leakage, representativeness, calibration and independent field validation still require domain evaluation. No trained or validated model is supplied because no real labelled dataset was provided. The synthetic data in tests exists only to test the training code and is deleted afterwards.

## Notifications and image analysis

Default `NOTIFICATION_MODE=dry-run` writes SMS outbox entries without contacting a messaging provider. In-app notifications work locally. An authority explicitly publishes an alert; screening alerts first require approval. Editing approved screening text invalidates approval. Publication is idempotent for each alert/user/channel. Resolved/unapproved alerts and withdrawn SMS subscriptions cancel messages that have not begun sending.

For real SMS, configure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM, change NOTIFICATION_MODE to live, and run the worker. Users must enable SMS and provide an international phone number. Provider acceptance is recorded as accepted, not delivered; subsequent polling records confirmed delivery or failure. An uncertain send is not automatically retried, because the provider might already have accepted it. An authority can check the provider and explicitly requeue it, up to three attempts.

Settings example: `{language: "hi", inApp: true, sms: false, phone: "", states: ["Meghalaya"]}`. Supported language codes are en, hi and as. Supply reviewed full messages on the alert's `translations` object. Without a full translation, the fallback has a localized review heading followed by the original alert text; it is not claimed to translate arbitrary content.

Image analysis is an adapter for an HTTPS classifier configured using VISION_ENDPOINT and optional VISION_API_KEY. It sends `{imageBase64, mimeType}` and expects `{labels: [...]}`. Results are stored for authority review. Unconfigured analysis returns 503 rather than fabricated findings. Satellite records likewise store supplied georeferenced metadata; no satellite subscription or trained vision service is bundled.

## Validation and maintenance

```powershell
python -m unittest -v
python manage.py check
python manage.py backup backups/backend-copy.sqlite3
```

Tests use temporary databases. They cover HTTP and WSGI, permissions, uploads, privacy, concurrent retries, device rotation, stale weather, forecasts, model training/loading, alert review, notification cancellation/uncertainty, response conflicts, sync, analytics and startup of the actual Waitress process. The Waitress test is skipped only if its dependency has not been installed.

The SQLite backup includes users, sessions, media and monitoring data. Keep backups private. Restore by stopping the API and worker, retaining the current database, and replacing it with the selected backup. Then restart both services. Do not expose this backend folder through a static file server.

## Container deployment

```powershell
Copy-Item .env.example .env
# Fill provider settings only if needed.
docker compose up --build -d
docker compose exec api python manage.py create-authority official@example.com
```

The image runs as a non-root user. API and worker share a named data volume; the port is bound to localhost. Docker configuration is supplied; local verification uses Waitress rather than a Docker daemon. Put HTTPS and trusted network/proxy configuration in front of any public deployment. This SQLite deployment is intended for one host and modest data volume; large regional deployments need storage scaling, retention, monitoring and district-level authorization appropriate to that deployment.

## Configuration and handover

See `.env.example`. Never commit .env, database files, .deps, model datasets or backups. `.gitignore` includes local dependencies and generated storage. Only `requirements.txt` is needed to install the deployment dependency on a fresh machine.

The backend workflows are implemented. External activation still needs actual sensors/data, labelled training data and model validation, messaging credentials, and an image classifier if desired. These cannot be fabricated from the frontend screens. The frontend remains unchanged: its mock imports, local storage and UI simulations will continue until you separately choose to connect it to these APIs. No GitHub push or deployment has been performed.

Provider references used for the adapters: [Open-Meteo forecast API](https://open-meteo.com/en/docs), [Twilio Message resource](https://www.twilio.com/docs/messaging/api/message-resource), and [Waitress usage](https://docs.pylonsproject.org/projects/waitress/en/latest/usage.html).
