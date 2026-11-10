"""Inference only. This project never trains or downloads a prediction model."""

import hashlib
import json
import os
from pathlib import Path
import numpy as np
from fastapi import HTTPException

FEATURES = [
    {"name": "rainfall24h", "unit": "mm", "min": 0, "max": 3000},
    {"name": "rainfall72h", "unit": "mm", "min": 0, "max": 9000},
    {"name": "soilMoisture", "unit": "percent saturation", "min": 0, "max": 100},
    {"name": "slope", "unit": "degrees", "min": 0, "max": 90},
    {"name": "groundMovement", "unit": "mm/hour", "min": 0, "max": 1000},
    {"name": "historicalEvents", "unit": "count", "min": 0, "max": 10000},
]
_cached = None


def load_model():
    global _cached
    path = os.environ.get("RF_MODEL_PATH", "")
    expected = os.environ.get("RF_MODEL_SHA256", "")
    if not path:
        raise HTTPException(
            503, "Random Forest model has not been supplied by the model team"
        )
    if not expected or len(expected) != 64:
        raise HTTPException(503, "Configure the supplied model SHA-256 before loading")
    try:
        raw = Path(path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected:
            raise ValueError("Model checksum mismatch")
        if _cached and _cached[0] == digest:
            return _cached[1:]
        import skops.io as sio
        from sklearn.ensemble import RandomForestClassifier

        unknown = sio.get_untrusted_types(data=raw)
        if unknown:
            raise ValueError("Model contains unsupported custom types")
        model = sio.loads(raw, trusted=[])
        if not isinstance(model, RandomForestClassifier):
            raise ValueError("Expected RandomForestClassifier")
        metadata = json.loads(Path(path + ".json").read_text())
        if metadata.get("features") != FEATURES:
            raise ValueError("Feature order/units do not match API contract")
        if model.n_features_in_ != len(FEATURES):
            raise ValueError("Feature count mismatch")
        if list(model.classes_) != [0, 1]:
            raise ValueError("Expected classes 0 (no landslide), 1 (landslide)")
        if hasattr(model, "feature_names_in_") and list(model.feature_names_in_) != [
            f["name"] for f in FEATURES
        ]:
            raise ValueError("Feature names mismatch")
        if not metadata.get("version"):
            raise ValueError("Model version metadata required")
        _cached = (digest, model, metadata)
        return model, metadata
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"Model unavailable: {exc}") from exc


def predict(inputs):
    if set(inputs) != {f["name"] for f in FEATURES}:
        raise HTTPException(422, "Supply exactly the features in /api/model")
    for f in FEATURES:
        v = inputs[f["name"]]
        if (
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not np.isfinite(v)
            or not f["min"] <= v <= f["max"]
        ):
            raise HTTPException(422, f"Invalid {f['name']} ({f['unit']})")
    model, metadata = load_model()
    row = np.array([[inputs[f["name"]] for f in FEATURES]])
    probability = float(model.predict_proba(row)[0][1])
    return {
        "probability": probability,
        "label": int(model.predict(row)[0]),
        "modelVersion": metadata["version"],
        "source": "separately supplied Random Forest",
        "operationallyValidated": False,
        "notice": "Student decision support; requires official review. This is not an operational public warning.",
    }
