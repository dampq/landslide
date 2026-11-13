"""Inference from the reviewed teammate archive only; never fit or substitute models."""
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / 'model-handoff/Ashtaraksha_Teammate_Handoff.zip'
MANIFEST = json.loads((ROOT / 'model-handoff/manifest.json').read_text())
CODES = [10, 30, 40, 50, 60, 70, 80, 90, 100]
NOTICE = ('Experimental relative susceptibility score for research demonstration. '
          'It is not a calibrated probability or an official warning. '
          'Local conditions and independent validation are not represented.')
V2_NOTICE = ('V2 performed worse than V1 on matched spatial evaluation. '
             'Rainfall inputs are WorldClim 1970–2000 climate normals; terrain is approximately 1 km. '
             'WorldClim is for academic/non-commercial use; redistribution or commercial use requires permission.')
_cached = {}


def bundle(version='1'):
    if version not in MANIFEST:
        raise HTTPException(422, 'Unknown model version; choose 1 or 2')
    spec = MANIFEST[version]
    try:
        with zipfile.ZipFile(ARCHIVE) as archive:
            files = {}
            for name, expected in spec['sha256'].items():
                raw = archive.read('Ashtaraksha_Teammate_Handoff/' + spec['folder'] + '/' + name)
                if hashlib.sha256(raw).hexdigest() != expected:
                    raise ValueError('Artifact checksum mismatch: ' + name)
                files[name] = raw
        return files
    except Exception as exc:
        raise HTTPException(503, f'Model unavailable: {exc}') from exc


def contract(version='1'):
    files = bundle(version)
    suffix = MANIFEST[version]['suffix']
    schema = json.loads(files[f'feature_list{suffix}.json'])
    features = []
    for name in schema['raw_features']:
        bounds = {'clay_fraction': (0, 1), 'sand_fraction': (0, 1),
                  'soil_ph': (0, 14),
                  'elevation_m': (-500, 9000), 'slope_degrees': (0, 90),
                  'aspect_sin': (-1, 1), 'aspect_cos': (-1, 1)}
        low, high = bounds.get(name, (0, None))
        features.append(dict(name=name, unit=schema['units'][name], min=low, max=high,
                             nullable=version == '2' and name != 'worldcover_class',
                             **({'choices': CODES} if name == 'worldcover_class' else {})))
    return features, schema


def load_model(version='1'):
    files = bundle(version)  # Verify even cached artifacts before use.
    suffix = MANIFEST[version]['suffix']
    if version not in _cached:
        try:
            import joblib
            from sklearn.ensemble import RandomForestClassifier
            model = joblib.load(io.BytesIO(files[f'ashtaraksha_random_forest{suffix}.joblib']))
            pipeline = joblib.load(io.BytesIO(files[f'preprocessing_pipeline{suffix}.joblib']))
            _, schema = contract(version)
            if not isinstance(model, RandomForestClassifier) or list(model.classes_) != [0, 1]:
                raise ValueError('Expected supplied presence/background RandomForestClassifier')
            if list(pipeline.feature_names_in_) != schema['raw_features']:
                raise ValueError('Raw feature order mismatch')
            names = list(pipeline.get_feature_names_out())
            if names != schema['transformed_features'] or model.n_features_in_ != len(names):
                raise ValueError('Transformed feature schema mismatch')
            metadata = json.loads(files[f'model_metadata{suffix}.json'])
            _cached[version] = (model, pipeline, metadata)
        except Exception as exc:
            raise HTTPException(503, f'Model unavailable: {exc}') from exc
    return _cached[version]


def model_status(version='1'):
    if version not in MANIFEST:
        raise HTTPException(422, 'Unknown model version; choose 1 or 2')
    result = dict(version=version, defaultVersion='1', experimental=version == '2',
                  features=[], notice=NOTICE, comparisonNotice=V2_NOTICE if version == '2' else '',
                  versions=[{'version': '1', 'name': 'V1 — default'},
                            {'version': '2', 'name': 'V2 — experimental comparison'}])
    try:
        result['features'], _ = contract(version)
        _, _, metadata = load_model(version)
        result.update(available=True, validation={k: v for k, v in metadata['validation'].items()
                                                 if k.startswith('oof_')})
    except HTTPException as exc:
        result.update(available=False, message=exc.detail)
    return result


def predict(inputs, version='1'):
    features, schema = contract(version)
    if set(inputs) != set(schema['raw_features']):
        raise HTTPException(422, 'Supply exactly the features in /api/model for the selected version')
    for f in features:
        value = inputs[f['name']]
        if value is None and f['nullable']:
            continue
        valid = (not isinstance(value, bool) and isinstance(value, (int, float))
                 and math.isfinite(value) and value >= f['min']
                 and (f['max'] is None or value <= f['max']))
        if f['name'] == 'worldcover_class':
            valid = type(value) is int and value in CODES
        if version == '1' and f['name'] == 'soil_ph' and value == 0:
            valid = False
        if not valid:
            raise HTTPException(422, f"Invalid {f['name']} ({f['unit']})")
    model, pipeline, _ = load_model(version)
    import pandas as pd
    frame = pd.DataFrame([[inputs[n] for n in schema['raw_features']]], columns=schema['raw_features'])
    score = float(model.predict_proba(pipeline.transform(frame))[0, 1])
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise HTTPException(503, 'Model returned an invalid relative score')
    return dict(experimental_presence_background_score=score, modelArtifactChecksums={k:v for k,v in MANIFEST[version]['sha256'].items() if k.endswith(('.joblib','.json'))}, modelVersion=version,
                model_version=version, experimental=True, operationallyValidated=False,
                interpretation=NOTICE, notice=NOTICE, comparisonNotice=V2_NOTICE if version == '2' else '',
                model_region='North Eastern Region of India; internal spatial evaluation only',
                imputed_fields=[n for n in schema['raw_features'] if inputs[n] is None],
                modelSource='Supplied teammate Random Forest and fitted preprocessing pipeline')


def supplied_example(version='1'):
    """Documented examples only; never assign these inputs to a real location."""
    bundle(version)
    if version == '1':
        return dict(inputs=dict(worldcover_class=10, clay_fraction=.199, sand_fraction=.367,
                                soil_ph=5.5, soc_stock_t_ha=170.),
                    referenceScore=0.7506392613449581,
                    reference='Version_1_Default/FINAL_MODEL_HANDOFF_REPORT.md; event_id=467')
    return dict(inputs=dict(worldcover_class=30, clay_fraction=.2, sand_fraction=.35,
                            soil_ph=5.2, soc_stock_t_ha=25.,
                            bio12_annual_precipitation_mm=2500., bio13_wettest_month_precip_mm=500.,
                            bio15_precipitation_seasonality_pct=80., bio16_wettest_quarter_precip_mm=1200.,
                            bio17_driest_quarter_precip_mm=100., elevation_m=450., slope_degrees=18.,
                            aspect_sin=.5, aspect_cos=.866), referenceScore=None,
                reference='TEAMMATE_INSTRUCTIONS.md; V2 example request (no reference score supplied)')


def evaluation(version):
    files = bundle(version)
    m = json.loads(files[f"model_metadata{MANIFEST[version]['suffix']}.json"])
    v = m['validation']
    folds = v.get('outer_fold_results', v.get('outer_folds', []))
    # Use only supplied counts; never infer an independent test set.
    return dict(method=v.get('method'),
                precision=v.get('oof_precision_at_0_5'), recall=v.get('oof_recall_at_0_5'),
                f1=v.get('oof_f1_at_0_5'), threshold=.5 if 'oof_precision_at_0_5' in v else None,
                evaluatedRows=sum(f.get('n_test', f.get('test_rows', 0)) for f in folds) or None,
                independentTestSize=None, confusionMatrix=v.get('confusion_matrix'),
                sampleEvents=m.get('positive_count_used', m.get('sample_count', {}).get('GFLD_positive_occurrences')),
                sampleBackground=m.get('background_count_used', m.get('sample_count', {}).get('unknown_background')))
