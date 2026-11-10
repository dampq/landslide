# Validation evidence

Validated in the provided Linux cloud environment on 10 November 2026, using Node 24, Python 3.12, PostgreSQL 17/PostGIS 3.5 and headless Chromium.

- `bash scripts/setup.sh --demo`: passed, including frozen dependency installs, database readiness, repeatable migration and labelled demo seeding. No application accounts or predictions are seeded.
- `npm run build`: passed TypeScript checking, Vite production bundling and versioned service-worker generation. The original CSS-import type error and CSS ordering warning are fixed; vendor chunks are split.
- `backend/.venv/bin/python -m pytest tests/test_api.py -q`: **27 passed**, no failures/skips. One upstream TestClient/AnyIO deprecation warning remains.
- `npm run test:e2e`: **6 passed**, no failures/skips, using the built PWA and a separate PostgreSQL database.
- `git diff --check`: passed.

The six browser workflows cover citizen GPS/media submission and official verification with admin audit, offline reload and attachment synchronisation, sensor simulation/map filtering/sample weather/alert publication, mobile Hindi/Assamese UI, interrupted media retry without duplicate reports, and offline sign-out/account switching with author-scoped pending data.

API tests cover authentication, role restrictions, origin protection, report privacy and validation, concurrent retries, attachment validation/deduplication/OpenCV, partial sync, spatial queries, alert states/subscriptions, atomic team deployments, unavailable-model and checksum handling, weather cache failure/success behaviour, simulated environmental values, attributed/idempotent imports, missing population data, account-session revocation, login throttling and CSV safety.

## Checks with external prerequisites

- Live Open-Meteo access was attempted and rejected by the cloud egress proxy (HTTP 403 CONNECT denial). Weather ingestion is verified with a deterministic provider response in tests; a successful live response is **not** claimed. Allow `api.open-meteo.com` to activate live refresh. Existing synthetic/cache data is retained on failure.
- Map markers and layer changes are browser-tested; successful remote OpenStreetMap tile delivery is **not** claimed in this restricted environment. Allow `tile.openstreetmap.org` for base tiles.
- The real Random Forest artifact has not been supplied. Missing-model and checksum rejection paths are tested. Successful inference with the team's eventual artifact remains a handover acceptance check; this project trains no model.
- Real GSI/NRSC/WorldPop/NASA data imports and external satellite imagery availability depend on public datasets and their terms. Bundled records are synthetic, not claimed real observations.
- Repository setup/start scripts are preserved. The cloud configuration draft service returned `INVALID_ARGUMENT` and did not confirm persistence; no saved draft or publication is claimed. See `docs/CLOUD_START.md` and `scripts/setup.sh` for the complete reusable instructions.

This validates the student demonstration workflow, not operational warning accuracy, real-world disaster outcomes, all-browser compatibility, a security audit or a public deployment.
