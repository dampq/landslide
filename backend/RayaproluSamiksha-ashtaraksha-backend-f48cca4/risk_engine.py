"""Transparent screening index and optional portable, trained logistic model.

The default index is NOT a calibrated probability or an operational warning model.
"""
import hashlib
import json
import math
import os
from pathlib import Path

FEATURES = ['rainfall24h', 'rainfall72h', 'soilMoisture', 'slope', 'groundMovement', 'historicalEvents']
SCALES = [200, 500, 100, 60, 10, 20]
BOUNDS = [2000, 5000, 100, 90, 1000, 10000]
WEIGHTS = [0.25, 0.20, 0.20, 0.15, 0.15, 0.05]


def features(data):
    values = []
    for name, high in zip(FEATURES, BOUNDS):
        value = data.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= high:
            raise ValueError(f'{name} must be a finite number between 0 and {high}')
        values.append(float(value))
    if values[1] < values[0]:
        raise ValueError('rainfall72h must include and be at least rainfall24h')
    return values


def sigmoid(value):
    return 1 / (1 + math.exp(-max(-40, min(40, value))))


def assess(data):
    values = features(data)
    normalized = [min(value / scale, 1) for value, scale in zip(values, SCALES)]
    factors = [{'name': key, 'value': value, 'contribution': round(n * weight * 100, 2)}
               for key, value, n, weight in zip(FEATURES, values, normalized, WEIGHTS)]
    score = round(sum(n * w for n, w in zip(normalized, WEIGHTS)) * 100, 2)
    result = {'method': 'screening-index-v1', 'probability': None, 'confidence': None,
              'operationallyValidated': False, 'modelVersion': None,
              'notice': 'Unvalidated screening index; requires expert review. Not a landslide probability.'}
    path = os.environ.get('MODEL_PATH')
    if path:
        path = Path(path)
        if not path.is_absolute():
            path = Path(__file__).parent / path
        content = path.read_bytes()
        model = json.loads(content)
        if model.get('features') != FEATURES or model.get('format') != 'ashtaraksha-logistic-v1':
            raise ValueError('Incompatible model artifact')
        weights, scales, bias = model['weights'], model['scales'], model['bias']
        if len(weights) != 6 or len(scales) != 6 or any(not math.isfinite(x) for x in weights + scales + [bias]) or any(x <= 0 for x in scales):
            raise ValueError('Invalid model coefficients')
        probability = sigmoid(bias + sum(w * v / s for w, v, s in zip(weights, values, scales)))
        score = round(probability * 100, 2)
        result.update(method='trained-logistic', probability=probability,
                      modelVersion=hashlib.sha256(content).hexdigest()[:16],
                      notice='Model estimate from supplied training data; calibration and field validation are not established.')
        factors = [{'name': key, 'value': v, 'logOddsContribution': w * v / s}
                   for key, v, w, s in zip(FEATURES, values, weights, scales)]
    level = 'Critical' if score >= 85 else 'High' if score >= 65 else 'Moderate' if score >= 40 else 'Low'
    return dict(result, score=score, level=level, factors=factors, inputs=data)
