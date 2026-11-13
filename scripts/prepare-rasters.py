"""Verify/extract the local raster archive, then test real-data model reproduction. Never trains."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from api import environmental as env
from api.prediction import predict, load_model
import numpy as np
import pandas as pd


def prepare(archive):
    root = env.data_root()
    root.mkdir(parents=True, exist_ok=True)
    required = set(env.required_paths('2'))
    prefixes = ('Ashtaraksha_Datasets/Land_Cover/WorldCover_2021_v200_tiles/',
                'Ashtaraksha_Datasets/Soil_Geology/SoilGrids_2.0_NER/',
                'Ashtaraksha_Model/Version_2/data/worldclim21_ner/')
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate paths in archive')
        for m in members:
            p = PurePosixPath(m.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in m.filename or not m.filename.startswith(prefixes) or stat.S_ISLNK(m.external_attr >> 16):
                raise ValueError('Unexpected or unsafe archive path: ' + m.filename)
        absent = required - set(names)
        if absent: raise ValueError('Missing required raster files: ' + ', '.join(sorted(absent)))
        total = sum(m.file_size for m in members if not m.is_dir())
        if total > 10 * 1024**3: raise ValueError('Archive exceeds the 10 GiB preparation limit')
        needed = sum(m.file_size for m in members if not m.is_dir() and not (root / m.filename).exists())
        if shutil.disk_usage(root).free < needed + 512 * 1024**2:
            raise ValueError('Insufficient free space for local rasters')
        files = {}
        for m in members:
            if m.is_dir(): continue
            print("Checking/extracting " + m.filename, flush=True)
            target = (root / m.filename).resolve()
            if not target.is_relative_to(root): raise ValueError('Raster path escapes data directory')
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as out:
                temp = Path(out.name)
                try:
                    h = hashlib.sha256()
                    with z.open(m) as source:
                        for block in iter(lambda: source.read(1024 * 1024), b''):
                            h.update(block); out.write(block)
                    out.flush()
                    if target.exists():
                        if env.digest(target) != h.hexdigest():
                            raise ValueError('Existing data differs; preserved file: ' + m.filename)
                        temp.unlink()
                    else: os.replace(temp, target)
                    files[m.filename] = {'sha256': h.hexdigest(), 'size': m.file_size}
                finally:
                    if temp.exists(): temp.unlink()
        doc = {'archiveSha256': env.digest(archive), 'files': files, 'method': env.METHOD}
        text = json.dumps(doc, indent=2, sort_keys=True) + '\n'
        (root / 'inventory.json.tmp').write_text(text)
        os.replace(root / 'inventory.json.tmp', root / 'inventory.json')
    return doc


def verify_grids():
    import rasterio
    report = []
    doc, _ = env.inventory()
    for relative in env.required_paths('2'):
        path = env.checked_file(relative, doc)
        with rasterio.open(path) as ds:
            assert ds.crs and ds.crs.to_epsg() == 4326 and ds.count == 1, path.name
            if relative.endswith('_Map.tif'):
                expected = (1 / 12000, 1 / 12000)
                assert ds.nodata == 0, path.name
            elif 'SoilGrids' in relative:
                expected = (.00226039783, .00238997377)
                assert (ds.width, ds.height) == (4424, 3431) and ds.nodata is None, path.name
            else:
                expected = (1 / 24, 1 / 24) if '_bio' in relative else (1 / 120, 1 / 120)
                assert ds.nodata == -9999, path.name
            np.testing.assert_allclose(ds.res, expected, rtol=0, atol=1e-9, err_msg=path.name)
            report.append({'file': relative, 'crs': ds.crs.to_string(), 'resolution': list(ds.res), 'width': ds.width, 'height': ds.height})
    return report


def verify_examples():
    results = []
    with zipfile.ZipFile(env.HANDOFF) as z:
        for version in ['1', '2']:
            print('Verifying real reference pixels and model V' + version, flush=True)
            example = json.loads(z.read(env.PREFIX + f'reproducible_examples/event_id_467_v{version}.json'))
            actual = env.extract(example['latitude'], example['longitude'], version, require_ready=False)
            assert actual['canScore'], actual['invalidFields']
            for name, value in example['raw_features'].items():
                np.testing.assert_allclose(actual['inputs'][name], value, rtol=0, atol=1e-10, err_msg=name)
            model, pipeline, _ = load_model(version)
            assert list(pipeline.get_feature_names_out()) == example['transformed_feature_order']
            transformed = pipeline.transform(pd.DataFrame([actual['inputs']], columns=list(pipeline.feature_names_in_)))
            np.testing.assert_allclose(np.asarray(transformed)[0], example['transformed_model_inputs'], rtol=0, atol=1e-10)
            score = predict(actual['inputs'], version)['experimental_presence_background_score']
            np.testing.assert_allclose(score, example['expected_score_verified'], rtol=0, atol=1e-12)
            results.append({'version': version, 'score': score, 'matched': True})
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, default=ROOT / 'model-handoff/frnd_raster_data.zip')
    args = p.parse_args()
    prepare(args.archive)
    # Real reference parity is mandatory before marking a bundle ready for the app.
    ready = env.data_root() / 'ready.json'
    if ready.exists(): ready.unlink()
    grids = verify_grids()
    results = verify_examples()
    _, inventory_id = env.inventory()
    ready.write_text(json.dumps({'inventoryId': inventory_id, 'referenceChecks': results, 'gridChecks': grids}, indent=2) + '\n')
    print(json.dumps({'status': 'verified', 'referenceChecks': results,
                      'note': 'Real-raster reference parity, not independent scientific validation.'}, indent=2))


if __name__ == '__main__':
    main()
