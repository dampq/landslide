# Supplied-model and incident-response demonstration

This milestone uses the unchanged supplied models. Automatic map-based feature extraction remains pending; neither demonstration scores nor response planning claim imminent-landslide prediction.

## Model examples and evaluation

1. Sign in as an official or administrator and open **Model integration**. V1 is the default.
2. Select **Load supplied example**. Inspect the exact supplied inputs and units before running. The V1 example is event_id=467 from `FINAL_MODEL_HANDOFF_REPORT.md`; expected reference score is `0.7506392613449581`.
3. Select **Run supplied example**. The backend uses V1's supplied estimator and fitted preprocessing pipeline. The displayed score rounds to `0.75063926`. No monitoring location is required, no example is associated with a real location, and no example result is persisted as a real assessment or warning.
4. Select V2. The previous example/result clears. Load the exact V2 request documented in `TEAMMATE_INSTRUCTIONS.md` and run it using the V2 estimator/pipeline. The supplied instructions do **not** provide an expected score for that request; the UI says **Not provided**. The report's separate V2 event_id=467 reference result cannot be claimed for this different example. Do not fabricate its missing original feature row.
5. Inspect reported evaluation: precision, recall, F1, score threshold 0.5, 358 out-of-fold evaluated rows, 179 fatal-event records and 179 unknown-background samples. The model metadata includes matched spatial folds and the validation method. There is no independent test-set size supplied. These are teammate-reported results, not a new website evaluation. Precision alone does not establish suitability, and scores are not directly interchangeable or calibrated probabilities.
6. The manual environmental assessment form remains separate. V1 blocks missing required fields. V2 supports explicit null continuous values through its original fitted imputers and reports imputed fields. Never type demo inputs into a real-location assessment and present them as extracted data.

## Verified incident to completed deployment

1. A citizen submits an incident with coordinates and, optionally, media through **Reports**. Use only a safe, clearly labelled demonstration incident.
2. An official opens that report, enters a review note and selects **Verify**. The server appends reviewer identity, timestamp, status and note to its review history.
3. Select **Plan response** on the verified report. The Response page retains the report ID in its URL and retrieves its coordinates, description and review history from the backend. Unverified/rejected/resolved reports cannot enter this planning path.
4. Deliberately choose a monitoring location and an available team. No location is chosen automatically from proximity. Check **Confirm monitoring location association**; deployment is disabled until confirmation. The backend enforces confirmation and current verified status independently of the UI.
5. Select **Deploy**. The deployment retains the report ID, original coordinates, review history snapshot, monitoring location, confirmer and timestamp. The report stores the confirmed response location, and the audit log records the association and assignment. Coordinate/description fields do not need retyping.
6. Move the deployment through **On Site** to **Completed**. The report link remains visible, the team becomes available, and the server audits each transition. Existing transactional locking prevents simultaneous assignments of one team.
7. As an administrator, inspect the audit log for `report:response-association`, `deployment:create`, `deployment:On Site` and `deployment:Completed`.

Warnings remain a separate draft/review/publication workflow. Neither running a model example nor assigning a team publishes an alert.

## Extraction feasibility

The feature-to-source table and access evidence are in `FEATURE_SOURCES.md` and `evidence/source-access.json`. The runtime status was rechecked during this milestone: provider-domain additions remain unapplied (no custom hosts in the enforced running policy). The existing CONNECT 403 evidence still applies; identical unchanged requests were not repeatedly retried. No pilot rasters were downloaded or compatibility asserted. Exact SOC product/depth/statistic, training-time sampling and slope/aspect derivation remain gaps in the supplied package. The defensible current scope is a reproducible supplied-example workflow plus incident response, not real coordinate extraction. No new model training or source substitutions are proposed.

When background offline sync completes after sign-in/reconnection, the report list refreshes so a newly uploaded incident appears without manually reloading. The offline account-switching regression suite checks that queued data stays with its author.
