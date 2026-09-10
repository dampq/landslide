"""Train a portable logistic classifier from the user's labelled CSV, without pickle."""
import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

from risk_engine import FEATURES, SCALES, features, sigmoid


def train(path, output, epochs=1500):
    rows = list(csv.DictReader(Path(path).read_text(encoding='utf-8-sig').splitlines()))
    samples = []
    for row in rows:
        values = features({key: float(row[key]) for key in FEATURES})
        label = int(row['landslideOccurred'])
        if label not in {0, 1}:
            raise ValueError('landslideOccurred must be 0 or 1')
        samples.append(([v / s for v, s in zip(values, SCALES)], label))
    groups = [[s for s in samples if s[1] == label] for label in [0, 1]]
    if min(map(len, groups)) < 10:
        raise ValueError('Need at least 10 positive and 10 negative labelled observations')
    rng = random.Random(42)
    training, heldout = [], []
    for group in groups:
        rng.shuffle(group)
        split = max(2, len(group) // 5)
        heldout.extend(group[:split])
        training.extend(group[split:])
    weights, bias = [0.0] * 6, 0.0
    for _ in range(epochs):
        dw, db = [0.0] * 6, 0.0
        for values, label in training:
            error = sigmoid(bias + sum(w * x for w, x in zip(weights, values))) - label
            db += error
            for j, value in enumerate(values):
                dw[j] += error * value
        bias -= .1 * db / len(training)
        weights = [w - .1 * (g / len(training) + .001 * w) for w, g in zip(weights, dw)]
    probabilities = [(sigmoid(bias + sum(w * x for w, x in zip(weights, values))), label) for values, label in heldout]
    tp = sum(p >= .5 and label == 1 for p, label in probabilities)
    fn = sum(p < .5 and label == 1 for p, label in probabilities)
    fp = sum(p >= .5 and label == 0 for p, label in probabilities)
    metrics = {'heldoutCount': len(heldout), 'trainingCount': len(training),
               'accuracy': sum((p >= .5) == bool(label) for p, label in probabilities) / len(heldout),
               'recall': tp / (tp + fn) if tp + fn else None,
               'precision': tp / (tp + fp) if tp + fp else None,
               'brierScore': sum((p - label)**2 for p, label in probabilities) / len(heldout)}
    artifact = {'format': 'ashtaraksha-logistic-v1', 'features': FEATURES, 'scales': SCALES,
                'weights': weights, 'bias': bias, 'evaluation': metrics,
                'datasetSha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                'operationallyValidated': False,
                'limitations': 'Random stratified holdout only. Spatial/temporal leakage, calibration, representativeness and independent field validation must be assessed before operational use.'}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(artifact, indent=2), encoding='utf-8')
    return metrics


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('csv')
    parser.add_argument('--output', default='models/landslide.json')
    parser.add_argument('--epochs', type=int, default=1500)
    args = parser.parse_args()
    if not 1 <= args.epochs <= 10000:
        parser.error('epochs must be 1-10000')
    print(json.dumps(train(args.csv, args.output, args.epochs), indent=2))
