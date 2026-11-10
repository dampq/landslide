# External Random Forest handover

The website team supplies inference integration only. There is no training route, training script, bundled pretrained model or heuristic probability substitute. Training and evaluation belong to the separate model team.

## Contract

`GET /api/model` returns the authoritative feature contract and model availability. `POST /api/predictions` is restricted to officials/administrators. It accepts:

```json
{
  "locationId": "demo-location-0",
  "observedAt": 1794290400,
  "source": "Your observation/dataset source",
  "inputs": {
    "rainfall24h": 100,
    "rainfall72h": 200,
    "soilMoisture": 65,
    "slope": 30,
    "groundMovement": 1.5,
    "historicalEvents": 3
  }
}
```

Use the actual UTC observation timestamp, within the previous 24 hours. Units and order are:

| Feature          | Unit               | Range   |
| ---------------- | ------------------ | ------- |
| rainfall24h      | mm                 | 0–3000  |
| rainfall72h      | mm                 | 0–9000  |
| soilMoisture     | percent saturation | 0–100   |
| slope            | degrees            | 0–90    |
| groundMovement   | mm/hour            | 0–1000  |
| historicalEvents | count              | 0–10000 |

Agree these units and preprocessing with the model team **before their final export**. Volumetric soil moisture from SMAP/Open-Meteo is not equivalent to saturation percentage. Missing inputs cannot be silently replaced with zeros. If the team's model uses different features/units, revise the explicit contract together; do not rename columns to hide a mismatch. Environmental input collection is manual or imported in this student release; no physical network is assumed.

## Accepted artifact

The model team supplies a fitted scikit-learn **RandomForestClassifier**, exported by them to a `.skops` file using `skops.io.dump`. The server does not accept model uploads through a public endpoint, arbitrary pickle/joblib files, custom Python classes, model-download URLs or executable preprocessing code. The supported artifact consumes the six raw numerical features in the stated order and has classes `[0, 1]`, where 1 means landslide. Scikit-learn 1.6.1 / skops 0.11.0 are pinned; coordinate any version change explicitly.

Alongside `/private/path/model.skops`, supply `/private/path/model.skops.json`:

```json
{
  "version": "team-version-1",
  "features": [
    { "name": "rainfall24h", "unit": "mm", "min": 0, "max": 3000 },
    { "name": "rainfall72h", "unit": "mm", "min": 0, "max": 9000 },
    {
      "name": "soilMoisture",
      "unit": "percent saturation",
      "min": 0,
      "max": 100
    },
    { "name": "slope", "unit": "degrees", "min": 0, "max": 90 },
    { "name": "groundMovement", "unit": "mm/hour", "min": 0, "max": 1000 },
    { "name": "historicalEvents", "unit": "count", "min": 0, "max": 10000 }
  ]
}
```

Store the artifact outside public static directories. Set `RF_MODEL_PATH` and `RF_MODEL_SHA256` to the trusted artifact's absolute path and its independently checked SHA-256, then restart the API. Unknown serialization types, mismatched checksum, wrong estimator/features/classes and missing metadata are rejected. No model is supplied in this repository. The successful inference path must be acceptance-tested with the actual artifact when the team delivers it; it is intentionally not claimed as validated now.

Without a model, prediction requests return HTTP **503** and no prediction is persisted. With an accepted model, responses include its probability, predicted class, version, source and `operationallyValidated: false`. Results are stored for review. A prediction **never automatically publishes a warning**. Domain validation, calibration, spatial/temporal evaluation and operational approval remain separate responsibilities.
