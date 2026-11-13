# Supplied model integration

The backend runs both unchanged Random Forests and their fitted preprocessing pipelines from `model-handoff/Ashtaraksha_Teammate_Handoff.zip`. No training, refitting, conversion or substitute estimator is used. V1 is the default; V2 is an explicitly experimental comparison. The reviewed instructions, feature lists, metadata, prediction scripts and reports remain in the archive. `model-handoff/manifest.json` pins every supplied version file by SHA-256; V1 model/pipeline fingerprints also match the handoff report. Files are verified before deserialization and before cached inference. Only these backend-local artifacts are accepted, with no upload or arbitrary path/URL loading. Joblib is executable serialization: this exception is limited to the supplied, reviewed handoff, not general untrusted artifacts.

Install with the repository's Python 3.12 setup (`bash scripts/setup.sh --demo`). Inference additionally uses pandas 3.1.1, joblib 1.6.0, NumPy 2.5.4 and scikit-learn 1.6.1. Geospatial/raster/training packages from the handoff's broader requirements are unnecessary for inference. The existing application's compatible FastAPI version is retained.

`GET /api/model?version=1` (authenticated) returns availability, exact required feature names, units, ranges, null policy and reported spatial evaluation. Omit `version` for V1; use `2` for V2. `POST /api/predictions` remains official/admin-only and persists the selected version, environmental inputs, collection timestamp, dataset source, relative score, notices and imputed field names. Citizen requests are forbidden. Missing/tampered artifacts return 503 and create no result. Unknown versions and invalid feature payloads return 422. Models never publish alerts.

Example request:

```json
{
  "locationId": "demo-location-0",
  "modelVersion": "1",
  "observedAt": 1793534400,
  "source": "Documented extraction from WorldCover/SoilGrids at the selected location",
  "inputs": {
    "worldcover_class": 10,
    "clay_fraction": 0.199,
    "sand_fraction": 0.367,
    "soil_ph": 5.5,
    "soc_stock_t_ha": 170.0
  }
}
```

This supplied V1 example returns `experimental_presence_background_score: 0.7506392613449581`. It is an example row, not a current observation for the demo location. Responses have no `probability`, safe/unsafe class, or warning level. The UI displays the raw relative score on 0–1, interpretation and imputation details. `observedAt` records feature collection time; static environmental layers do not need a fictitious last-24-hours observation. Future timestamps are rejected. The source is retained separately from model provenance (`modelSource`).

V1 requires exactly five finite numeric fields. WorldCover must be an integer in 10, 30, 40, 50, 60, 70, 80, 90, 100. Clay/sand are fractions 0–1 (SoilGrids per-mille divided by 1000), pH is greater than 0 through 14, SOC is nonnegative tonnes/hectare. Booleans, strings, nulls, missing/extra keys, NaN and infinity are rejected.

V2 requires all 14 keys: the five V1 fields plus `bio12_annual_precipitation_mm`, `bio13_wettest_month_precip_mm`, `bio15_precipitation_seasonality_pct`, `bio16_wettest_quarter_precip_mm`, `bio17_driest_quarter_precip_mm`, `elevation_m`, `slope_degrees`, `aspect_sin` and `aspect_cos`. BIO/SOC values are nonnegative, elevation −500–9000 metres, slope 0–90 degrees, aspect components −1–1, pH 0–14, fractions 0–1. All continuous fields may explicitly be null; the supplied fitted pipeline imputes them and the response names them. The example V2 FastAPI schema is stricter about null soil/terrain values than TEAMMATE_INSTRUCTIONS, the feature list and `predict_v2.py`; this integration follows the latter documented helper contract. WorldCover remains required and cannot be null. Blank V2 UI fields submit explicit null, never zero. Inputs are ordered using the version's feature list; transformed names/width and estimator classes are checked against the supplied schema.

Environmental extraction is manual/imported. The archive contains no source rasters or training CSVs, and neither model extracts inputs from coordinates. Live weather, sensor simulations, synthetic records and V1 inputs must never be renamed into missing V2 features. No fabricated feature extraction or regional risk map is provided.

Both versions distinguish 179 reported fatal GFLD occurrences from 179 sampled locations of unknown outcome. Backgrounds are not confirmed safe. Both lack independent validation and calibrated probability estimates. Matched spatial ROC-AUC/AP: V1 0.638/0.698; V2 0.568/0.595. V2 rainfall describes WorldClim 1970–2000 climate normals (~4.6 km), terrain is approximately 1 km, and neither represents current event rainfall or local hillside measurements. V2 performed worse; it is not promoted to default. Display: “Experimental relative susceptibility score for research demonstration. It is not a calibrated probability or an official warning. Local conditions and independent validation are not represented.”

Provenance: GFLD, University of Sheffield, OGL v2.0, Froude & Petley (2018), DOI 10.5194/nhess-18-2161-2018; ESA WorldCover 2021 v200, CC BY 4.0, Zanaga et al., DOI 10.5281/zenodo.7254221; ISRIC SoilGrids 2.0, CC BY 4.0, Poggio et al., DOI 10.5194/soil-7-217-2021; WorldClim 2.1, Fick & Hijmans (2017), DOI 10.1002/joc.5086. WorldClim is academic/non-commercial only; redistribution/commercial use requires permission. Raw WorldClim rasters are not bundled.

Validation: `backend/.venv/bin/python -m pytest tests/test_api.py -q` exercises authenticated HTTP health, both inference routes, parity with the supplied helpers, the V1 reported golden score, key reordering, null imputation, permissions, persistence, missing files and tamper rejection before deserialization. `npm run test:e2e` checks both version forms and score display; `npm run build` and `npm run check:i18n` validate the UI. These are inference integration checks, not new scientific validation or reproduction of training metrics.

Before implementing coordinate extraction, follow the feature-to-source table and unresolved compatibility gates in [FEATURE_SOURCES.md](FEATURE_SOURCES.md). Actual integration evidence, checksums and logs are indexed in [evidence/README.md](evidence/README.md). Neither manual-input tests nor synthetic raster tests would establish extraction from real source layers.

## Supplied-example demonstration and evaluation context

`GET /api/model/examples/{version}` returns canonical documented input values and units. `POST /api/model/examples/{version}/run` runs those fixed inputs through the selected unchanged estimator/preprocessor. Both routes require official/admin access. Example responses are marked `simulated: true` / `assessmentMode: supplied-example`, have no location ID, and never create a real assessment record or publish an alert. The V1 report's event_id=467 example has expected score 0.7506392613449581. V2 uses the complete request in TEAMMATE_INSTRUCTIONS.md, whose expected score is not provided; the different V2 event_id=467 result cannot be used as that example's reference.

`GET /api/model/comparison` exposes supplied out-of-fold precision/recall/F1, threshold, evaluated sample count, confusion matrices and validation methodology, with null for an unprovided independent test size. It does not substitute training-fit metrics or imply that model scores are directly comparable probabilities. See `MILESTONE_DEMO.md` for the incident-response walkthrough and the separation from location-based extraction.

## Coordinate extraction integration

The uploaded extraction handoff now supports a separate inspect-then-score path with local source inventory and provenance. See `AUTOMATIC_ASSESSMENT.md` for preparation, geographic/missing-data rules and the distinction between synthetic test evidence and real-raster reference checks. This supersedes earlier statements that extraction code is entirely pending; dataset readiness still requires successful local verification on the API host.
