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
- **Random Forest:** no artifact has been supplied, trained, replaced or downloaded. Missing-model and checksum rejection paths pass. Actual model inference remains the separate team's handover acceptance step, as required.
- **Optional extensions:** advanced image classification, satellite processing, physical sensors and paid/public SMS are not prerequisites. Public source portals and satellite exploration remain subject to their own availability/terms.
- **Cloud publication:** repository setup/start instructions are saved in Git. The separate cloud configuration draft service previously returned `INVALID_ARGUMENT`; no persisted cloud draft, published snapshot or public deployment is claimed.

The website is validated for the permitted student demonstration using labelled data. This is not evidence of operational warning accuracy, disaster outcomes, universal browser compatibility or a production security audit.

## Authentication repair

The reported “nothing happens” behaviour was reproduced: the original browser-native minimum-password check stopped submission before the submit handler, producing zero sign-in requests and no in-page error. The form now validates explicitly and accessibly inside the page. Registration maintains the 12-character minimum; sign-in accepts a nonempty attempt and relies on password verification/rate limits. Registration and login have separate validated schemas. The browser session is confirmed before opening the dashboard; cookie/origin protections remain in place. No claim is made that every external Codespaces browser/session configuration has been tested.
