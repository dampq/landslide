# Requirements and acceptance map

This implementation targets a complete **student-level demonstration**. It deliberately distinguishes working features from separately supplied data/models and optional external services.

| Requirement                                         | Implementation / acceptance                                                                                                                                       |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Registration, login, citizen/official/admin portals | Real password authentication, protected routes, backend role enforcement, administrator assignment and session revocation                                         |
| Authority dashboard                                 | Database counts, source/sample notices, notifications; no invented regional totals or fake connection indicators                                                  |
| GIS                                                 | Leaflet/OpenStreetMap, PostGIS layer filtering and radius queries; bundled Natural Earth reference for all eight NE states when external tiles are blocked        |
| Environmental monitoring                            | Editable/importable monitoring locations; slope and other source metadata; explicitly simulated rainfall, soil-moisture and ground-movement readings with history |
| Weather forecasts                                   | Open-Meteo fetch/cache, past modelled rainfall and hourly forecasts, freshness and provider-error handling; separately labelled sample forecast for demonstration |
| Historical landslides                               | Attributed manual records and JSON/point GeoJSON imports; stored-data analytics. No false claim that a GSI inventory is already bundled                           |
| Satellite exploration                               | External Copernicus Sentinel browser and public imagery-reference records; optional availability, no fabricated analysis                                          |
| Citizen media/GPS reporting                         | Browser geolocation, validated reports, PNG/JPEG/WebP/MP4 uploads, private media download, stable IDs and deduplication                                           |
| Field official reporting/verification               | Officials also submit reports; author role is server-derived. Verification/rejection/resolution require notes and valid transitions                               |
| Image processing / optional classification          | OpenCV dimensions, brightness, sharpness and edge fraction. Classification is explicitly unconfigured and optional                                                |
| Warning management                                  | Draft, approval, publication, resolution, subscription-filtered in-app inbox and idempotent publication                                                           |
| Roads                                               | Stored, editable status and representative-point mapping; road-routing analysis is outside this student scope                                                     |
| Infrastructure / vulnerable areas                   | Geographic records, shelter examples, reviewed location risk levels and spatial proximity                                                                         |
| Population exposure                                 | Imported population counts with source/year/resolution/license, PostGIS radius sum and approximation notice; sample values clearly marked                         |
| Response prioritisation                             | Labelled planning heuristic, approximate population/road impact, atomic team assignments and deployment transitions                                               |
| Simulated sensors                                   | Explicit official-triggered rainfall simulator, current values/history; no physical network dependency                                                            |
| Multilingual                                        | English/Hindi/Assamese catalogs covering interface descriptions, labels, statuses, actions and persistent selection; source reports/citations remain original     |
| Offline PWA                                         | Versioned app shell and public-domain reference map cache, author-scoped report/file queue, offline reload and retry-safe reconnect sync                          |
| Analytics / downloads                               | Recharts summaries of stored data, CSV exports with provenance and formula neutralisation                                                                         |
| Administration                                      | User roles/activation, imports, audit trail and database/model status                                                                                             |
| Random Forest boundary                              | Inference-only API, explicit units/order, both supplied model/pipeline pairs, checksum/schema checks, V1 default/V2 experimental; no training or replacement     |
| Responsive web                                      | Desktop/sidebar and mobile menu layouts, browser-tested at 390px; no Android/iOS app required                                                                     |

## Demonstration walkthrough

1. Start the database/API/frontend and seed synthetic records.
2. Register a citizen. Bootstrap a separate administrator locally and assign a field official.
3. Submit a GPS report with an image. Verify it from the official portal and check the citizen sees its status.
4. Explore the GIS layers and select a location to estimate nearby population. All seeded counts must show their synthetic source.
5. Show the synthetic forecast; try live refresh. A blocked provider must produce an error while preserving cache.
6. Run the sensor simulator. Explain that it produces no real sensor observations or model predictions.
7. Create/approve/publish a synthetic warning. Check a citizen's subscribed inbox. Assign a sample team and complete its deployment.
8. Disconnect the browser after loading the production PWA. Submit a report with an image, reload, inspect the queue, reconnect and verify one stored report with its media.
9. Switch Hindi and Assamese; inspect mobile navigation and reporting controls.
10. Download CSV, inspect source/simulated columns, import the sample JSON and inspect the audit trail.
11. Open the model portal. Select V1 or V2 and supply the documented environmental features; inspect the experimental relative score and imputed fields. Do not present any sample risk level as an ML result.

## Separate handovers / honest limitations

Both separately supplied Random Forest versions are integrated for inference with checksum verification and their original fitted pipelines. V1 is default; V2 is experimental and performed worse in matched spatial evaluation. Neither has independent validation or calibrated probability outputs. Real public datasets are not fabricated or represented as already downloaded: lawful imports, attribution and domain review are required when replacing samples. Live weather and online street tiles require network access; explicit sample weather and a bundled geographic reference remain available without those services. External satellite exploration and advanced classification remain optional. This student platform does not claim operational government warning capability, calibrated predictions or a proven population-at-risk footprint.

## Completed website acceptance

The browser suite exercises all three portals, reporting/verification/media/GPS, alert review/publication, team deployment/completion, role assignment, attributed import/CSV download, failed uploads/retries, author-scoped offline sync, map-provider denial with real reference boundaries, offline reference-map reload, explicit weather samples and failures, and Hindi/Assamese navigation through all portal pages. Source-derived geographic boundaries are approximate and are not operational risk predictions. See `VALIDATION.md` for the executed checks.
