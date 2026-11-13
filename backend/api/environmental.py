"""Local, versioned raster sampling. No training, network fetching or example substitution."""
import csv
from functools import lru_cache
import hashlib
import io
import json
import math
import os
from pathlib import Path
import zipfile

import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import Point, shape
from fastapi import HTTPException
from .prediction import ROOT, CODES, contract

HANDOFF = ROOT / 'model-handoff/Feature_Extraction_Handoff.zip'
PREFIX = 'Ashtaraksha_Feature_Extraction_Handoff/'
METHOD = 'training-pixel-sampling-v1'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


@lru_cache(maxsize=1)
def handoff():
    expected = (ROOT / 'model-handoff/extraction-sha256.txt').read_text().strip()
    if digest(HANDOFF) != expected:
        raise HTTPException(503, 'Extraction handoff checksum mismatch')
    with zipfile.ZipFile(HANDOFF) as z:
        config = json.loads(z.read(PREFIX + 'feature_extraction/config.json'))
        boundary = json.loads(z.read(PREFIX + 'feature_extraction/data/NER_8_states.geojson'))
        rows = list(csv.DictReader(io.StringIO(z.read(PREFIX + 'dataset_source_manifest.csv').decode('utf-8-sig'))))
    return config, boundary, {r['local_filename']: r for r in rows}, expected


def data_root():
    return Path(os.environ.get('RASTER_DATA_ROOT', ROOT / '.cache/environmental-data')).resolve()


def required_paths(version):
    c, _, sources, _ = handoff()
    paths = [str(Path(c['worldcover_dir']) / n) for n in sources if n.endswith('_Map.tif')]
    paths += [str(Path(c['soilgrids_dir']) / n) for n in c['soil_rasters'].values()]
    if version == '2':
        paths += [str(Path(c['worldclim_dir']) / n) for n in c['worldclim_rasters'].values()]
    return paths


def inventory():
    try:
        raw = (data_root() / 'inventory.json').read_bytes()
        doc = json.loads(raw)
        return doc, hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError):
        raise HTTPException(503, 'Raster data are not prepared. Run npm run prepare:rasters on this server.') from None


@lru_cache(maxsize=128)
def checked_hash(path, size, modified, changed):
    return digest(path)


def checked_file(relative, doc):
    root = data_root()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(503, 'A required local raster is unavailable')
    expected = doc.get('files', {}).get(relative, {}).get('sha256')
    stat = path.stat()
    if not expected or checked_hash(str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) != expected:
        raise HTTPException(503, 'Raster data changed or failed their recorded checksum; prepare the data again')
    return path


def verify_snapshot(snapshot):
    doc, identity = inventory()
    try:
        ready = json.loads((data_root() / 'ready.json').read_text())
    except (OSError, ValueError):
        raise HTTPException(503, 'Raster data are not currently verified') from None
    if ready.get('inventoryId') != identity or snapshot['inventoryId'] != identity or snapshot.get('method') != METHOD:
        raise HTTPException(409, 'Environmental data changed; extract and inspect the inputs again')
    for source in snapshot['provenance']:
        if source.get('file'):
            checked_file(source['file'], doc)


def sample(relative, lon, lat, doc, sources):
    path = checked_file(relative, doc)
    try:
        with rasterio.open(path) as ds:
            if ds.crs is None or ds.count != 1:
                raise HTTPException(503, 'Raster grid metadata is incompatible')
            x, y = Transformer.from_crs('EPSG:4326', ds.crs, always_xy=True).transform(lon, lat)
            row, col = ds.index(x, y)
            info = dict(file=relative, sha256=doc['files'][relative]['sha256'], crs=ds.crs.to_string(),
                        resolution=list(ds.res), row=int(row), column=int(col), nodata=ds.nodata if ds.nodata is None or math.isfinite(ds.nodata) else None)
            source = sources.get(path.name, {})
            info.update({k: source.get(k) or None for k in ['dataset_name', 'publisher', 'product_version', 'official_source_url', 'temporal_coverage', 'licence', 'attribution', 'depth_interval', 'original_resolution', 'category']})
            if not (0 <= row < ds.height and 0 <= col < ds.width):
                return None, {**info, 'status': 'OUTSIDE_RASTER', 'rawValue': None}
            value = next(ds.sample([(x, y)], indexes=1, masked=True))[0]
            value = None if np.ma.is_masked(value) or not math.isfinite(float(value)) else float(value)
            return value, {**info, 'status': 'OK' if value is not None else 'SOURCE_NODATA', 'rawValue': value}
    except rasterio.errors.RasterioError:
        raise HTTPException(503, 'A local environmental raster cannot be read') from None


def extract(lat, lng, version, require_ready=True):
    if version not in ['1', '2'] or isinstance(lat, bool) or isinstance(lng, bool):
        raise HTTPException(422, 'Invalid coordinates or model version')
    if not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
        raise HTTPException(422, 'Invalid coordinates')
    c, boundary, sources, handoff_hash = handoff()
    feature = next((f for f in boundary['features'] if shape(f['geometry']).covers(Point(lng, lat))), None)
    if feature is None:
        raise HTTPException(422, 'Location is outside the eight-state North East India study area')
    doc, identity = inventory()
    if require_ready:
        try:
            ready = json.loads((data_root() / 'ready.json').read_text())
            if ready['inventoryId'] != identity:
                raise ValueError('stale verification')
        except (OSError, ValueError, KeyError):
            raise HTTPException(503, 'Raster reference verification has not passed; run npm run prepare:rasters') from None
    required = required_paths(version)
    if any(not (data_root() / p).is_file() for p in required):
        raise HTTPException(503, 'Required environmental raster files are missing; no example values were substituted')
    values, provenance = {}, []
    wc_info = {'name': 'worldcover_class', 'status': 'OUTSIDE_COLLECTED_TILES', 'file': None}
    # Training selection: first matching tile, half-open bounds, then a containing pixel.
    for relative in sorted(p for p in required if p.endswith('_Map.tif')):
        path = checked_file(relative, doc)
        with rasterio.open(path) as ds:
            if ds.crs is None:
                raise HTTPException(503, 'WorldCover grid has no CRS')
            x, y = Transformer.from_crs('EPSG:4326', ds.crs, always_xy=True).transform(lng, lat)
            if ds.bounds.left <= x < ds.bounds.right and ds.bounds.bottom < y <= ds.bounds.top:
                raw, info = sample(relative, lng, lat, doc, sources)
                values['worldcover_class'] = int(raw) if raw is not None and raw > 0 else None
                wc_info = {**info, 'name': 'worldcover_class', 'evidenceType': 'Classified land cover'}
                break
    values.setdefault('worldcover_class', None)
    provenance.append(wc_info)
    soil, soil_info = {}, {}
    for name, filename in c['soil_rasters'].items():
        soil[name], soil_info[name] = sample(str(Path(c['soilgrids_dir']) / filename), lng, lat, doc, sources)
    ph = soil['soil_ph']
    invalid_soil = ph is not None and (ph <= 0 or ph > 140)
    if invalid_soil:
        soil = {k: None for k in soil}
    # Preserve the ORIGINAL V1 script: either fraction >1000 invalidates BOTH fractions.
    invalid_fractions = any(soil[k] is not None and soil[k] > 1000 for k in ['clay_fraction', 'sand_fraction'])
    if invalid_fractions:
        soil['clay_fraction'] = soil['sand_fraction'] = None
    for name, raw in soil.items():
        scale = .001 if name in ['clay_fraction', 'sand_fraction'] else .1 if name == 'soil_ph' else 1
        values[name] = None if raw is None else raw * scale
        provenance.append({**soil_info[name], 'name': name, 'scale': scale, 'evidenceType': 'Modelled soil property',
                           'status': 'TRAINING_PH_SENTINEL' if invalid_soil else 'TRAINING_FRACTION_SENTINEL' if invalid_fractions and name in ['clay_fraction', 'sand_fraction'] else soil_info[name]['status']})
    if version == '2':
        for name, filename in c['worldclim_rasters'].items():
            values[name], info = sample(str(Path(c['worldclim_dir']) / filename), lng, lat, doc, sources)
            provenance.append({**info, 'name': name, 'scale': 1, 'evidenceType': 'Climate normal' if name.startswith('bio') else 'Elevation reference surface' if name == 'elevation_m' else 'Derived terrain'})
    features, schema = contract(version)
    missing = [n for n in schema['raw_features'] if values[n] is None]
    invalid = []
    for f in features:
        value = values[f['name']]
        if value is None:
            if not f['nullable']: invalid.append(f['name'])
        elif f['name'] == 'worldcover_class':
            if value not in CODES: invalid.append(f['name'])
        elif value < f['min'] or (f['max'] is not None and value > f['max']) or (version == '1' and f['name'] == 'soil_ph' and value == 0):
            invalid.append(f['name'])
    return dict(lat=lat, lng=lng, modelVersion=version, state=feature.get('properties', {}).get('shapeName'),
                inputs={n: values[n] for n in schema['raw_features']}, features=features, provenance=provenance,
                missingFields=missing, invalidFields=invalid, canScore=not invalid,
                inventoryId=identity, handoffSha256=handoff_hash, archiveSha256=doc.get('archiveSha256'),
                method=METHOD, simulated=False,
                interpretation='Static environmental layers; climate inputs are 1970–2000 normals. Not live measurements or imminent-landslide prediction.',
                sourceUnitCaveat='Source units follow the supplied training convention. SOC is passed unchanged; independently verify its physical stock/concentration interpretation before scientific use.')
