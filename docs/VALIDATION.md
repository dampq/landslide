# Website acceptance evidence

Validated on 10 November 2026 in the provided Linux cloud environment using Node 24, Python 3.12, PostgreSQL 17/PostGIS 3.5 and headless Chromium. This report covers the student website, with the separately developed Random Forest artifact explicitly excluded.

## Executed checks

| Command                                       | Observed result                                                                                                                                   |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run build`                               | TypeScript checking, production bundling and PWA worker generation passed                                                                         |
| `backend/.venv/bin/python -m pytest tests -q` | **37 passed**, no failures/skips; one upstream TestClient/AnyIO deprecation warning                                                               |
| `npm run test:e2e`                            | **20 browser workflows passed**, no failures/skips, against the built PWA and an isolated PostgreSQL database                                     |
| `npm run check:i18n`                          | **341 interface keys in all 3 languages**; no raw English JSX text, missing keys or mismatched interpolation placeholders in the audited UI files |
| `npm run test:config`                         | **4 passed**: local/Codespaces origin and cookie configuration, custom forwarding and invalid-host rejection                                      |
| `python3 scripts/prepare-reference-map.py`    | Rebuilt **16 reference features**, including all **8 NE states**, from recorded SHA-256-verified Natural Earth source datasets                    |
| `git diff --check`                            | Passed                                                                                                                                            |

The earlier setup corrections were also exercised: writable project-local npm cache, Python 3.12 provisioning, repair of incomplete/missing-pip virtual environments, and authenticated database readiness. A brand-new isolated PostGIS container successfully completed readiness, migration and demo seeding; no existing user volume was removed.

## Browser acceptance coverage

1. Citizen account signs in, captures permitted GPS, submits a report/image; OpenCV metadata is retrieved; an official verifies it; the citizen sees the status; the administrator sees the audit entry.
2. A report and actual attachment survive offline submission and a full PWA reload, then synchronise to one server report after reconnection.
3. Simulated environmental stations, geographic layer filtering, sample weather and the complete alert draft/approval/publication flow work together.
4. Mobile layout fits a 390px viewport; Hindi/Assamese switching and the unavailable-model state render correctly.
5. An interrupted image upload retains its queue entry and retries without duplicating the report.
6. Offline sign-out/account switching prevents another account from synchronising someone else's pending submissions.
7. A simulated HTTP 403 from the tile provider produces a readable notice and a real regional reference background, retaining geographic records rather than displaying blocked images.
8. The bundled regional reference, labels and attribution survive offline reload without third-party tiles.
9. A simulated weather-provider failure retains labelled sample data; officials can explicitly regenerate a demonstration, with a clear non-live banner.
10. An official assigns a team, advances En Route → On Site → Completed and the team becomes available again.
11. An administrator assigns an official role, imports an attributed event and downloads a CSV containing its provenance/simulation fields; the new official gets appropriate portal access.
12. All portal pages are visited in Hindi and Assamese. A translated report option retains its correct API value rather than submitting the translated label.
13. Successful tile responses render the online layer with OpenStreetMap attribution; switching back restores the regional reference.
14. Cancelling replacement of a cached live forecast sends no sample request, preserves the live view and does not claim a save.

15. Empty/invalid account fields and short registration passwords produce visible in-page errors; short incorrect sign-in passwords reach authentication and return an explicit credentials error.
16. A new citizen registers through the actual page, reaches the dashboard, retains the session after reload, signs out and signs in again.
17. A blocked session cookie produces an actionable message rather than a dashboard/sign-in bounce.
18. An unavailable sign-in service returns a readable error and the same form can retry successfully.
19. A stalled sign-in request times out and restores the submit button.
20. If registration succeeds but automatic sign-in fails, account creation remains confirmed and sign-in can be retried without registering again.

External-provider success/failure browser cases use controlled responses. They validate website behaviour, not successful real third-party access.

## What is real, simulated, optional or unverified

- **Real bundled cartographic data:** Natural Earth public-domain state/country boundaries, source hashes and attribution. These are approximate reference geography, not surveyed roads, authoritative border claims or a predicted disaster footprint. No tile server, API key or government permission is required for this reference layer.
- **Simulated records:** seeded incident history, population, infrastructure, roads, weather and generated sensor values remain explicitly labelled. No real observation or warning accuracy is claimed from them. Public sourced datasets can replace them through the attributed import workflows; samples are permitted by the project requirements.
- **Live Open-Meteo:** a direct HTTPS request from this cloud machine was rejected by the egress proxy (403 CONNECT denial). `cd backend && .venv/bin/python manage.py check-services` reports PostgreSQL/PostGIS healthy and live weather unverified. A successful live weather response from this machine or the user's Codespace is **not** claimed. Deterministic provider-success, provider-failure, malformed-response and cache-protection tests pass. The explicit sample path remains usable.
- **Online street tiles:** successful delivery from the actual user's browser is **not** claimed. The user can select Automatic, Regional reference, OpenStreetMap or configured CARTO. Referrer/provider restrictions are respected; no proxy or alternate OpenStreetMap hostname is used to evade a denial. The PWA caches the independent reference dataset, never bulk downloads external tiles.
- **Translations:** application interface catalogs and navigation/form behaviour are checked. Source citations, user-generated text, imported metadata, API identifiers and explicitly disclosed technical diagnostics retain original text. Native-speaker review is recommended for public release; no machine check establishes linguistic accuracy.
- **Random Forest (updated 13 November 2026):** both supplied handoff versions are integrated without training or substitution. V1 reproduces the reported reference score; both match their supplied prediction helpers. The API suite checks inference, permissions, persistence, null imputation and artifact tampering. This does not constitute independent scientific validation. See `MODEL_INTEGRATION.md`.
- **Optional extensions:** advanced image classification, satellite processing, physical sensors and paid/public SMS are not prerequisites. Public source portals and satellite exploration remain subject to their own availability/terms.
- **Cloud publication:** repository setup/start instructions are saved in Git. The separate cloud configuration draft service previously returned `INVALID_ARGUMENT`; no persisted cloud draft, published snapshot or public deployment is claimed.

The website is validated for the permitted student demonstration using labelled data. This is not evidence of operational warning accuracy, disaster outcomes, universal browser compatibility or a production security audit.

## Authentication repair

The reported “nothing happens” behaviour was reproduced: the original browser-native minimum-password check stopped submission before the submit handler, producing zero sign-in requests and no in-page error. The form now validates explicitly and accessibly inside the page. Registration maintains the 12-character minimum; sign-in accepts a nonempty attempt and relies on password verification/rate limits. Registration and login have separate validated schemas. The browser session is confirmed before opening the dashboard; cookie/origin protections remain in place. No claim is made that every external Codespaces browser/session configuration has been tested.

## Supplied-model integration — 13 November 2026

Read the supplied teammate instructions and both versions’ feature lists, metadata, helpers, API examples and reports before deserialization. Both unchanged estimator/preprocessor pairs pass checksum and schema checks. V1 exactly reproduces the reported 0.7506392613449581 example; both versions match their own supplied helpers, including V2 null imputation.

Current checks: 34 API integration tests and 21 Chromium browser tests passed, including both version forms and actual HTTP prediction requests, admin system status, persistence and permissions. Production build and translation checks passed (352 keys across English, Hindi and Assamese); pip check found no broken requirements. One existing Starlette/AnyIO deprecation warning remains. These validate software integration, not calibration, independent NER performance or operational suitability.

## Supplied-example and incident-response milestone — 13 November 2026

Final run `docs/evidence/20261113T113333Z/`: 42 Python tests and 23 Chromium browser tests passed, with no skipped browser tests or unexpected outcomes. Build, translation checks (372 keys, three languages), four configuration tests and pip dependency checks passed. Source fingerprints were verified unchanged during the run. Prior failed runs remain in the evidence directory with their original exit statuses.

New acceptance checks cover canonical supplied examples separated from real assessments, exact V1 reference agreement, V2 missing reference information, evaluation conditions, explicit monitoring-location confirmation, report ID/coordinates/review history retained through completed deployment, role enforcement and audit records. A timing bug found during broad testing was corrected by refreshing the reports list after background queue completion. Neither model nor fitted preprocessing artifact was modified, trained or substituted. Automatic map feature extraction remains pending. See `MILESTONE_DEMO.md`.

## Report-first response — 13 November 2026

`docs/evidence/20261113T132736Z/` captures the final unchanged-source run: 50 Python checks (44 API, six setup/diagnostic checks) and 25 Chromium browser tests passed, with no browser skips/failures. Build, 412-key/three-language translation checks, four configuration tests and dependency checks passed. Artifact checksums remain unchanged.

Coverage includes no-monitoring-record dispatch, strict confirmations, corrected destinations/reasons, configured team coverage, urgent unverified investigation, clarification author permissions, concurrent reservation conflicts without verifying the losing report, rollback after injected transactional failure, movement transitions, citizen response status, audit history, and no-team/busy/outside-coverage UI states. The first development browser run passed 22 tests and failed two because an old exact-text selector did not match the new status history and left a shared fixture team reserved; stable selectors and independent test teams corrected the test isolation. The focused normal/urgent browser cases then passed before this final full run.

Duplicate detection is advisory (same incident category, 500 m, ±24 h) and is not a claim that records are duplicates. Coverage uses optional configured rectangles; unspecified coverage stays unknown. No emergency-contact integration, model training, automatic feature extraction or real emergency-service dispatch is claimed. The clean working database is not seeded by these tests.
