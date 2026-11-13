"""Synthetic raster mechanics + authenticated API tests, NOT real-dataset validation."""
from test_api import actors, clean
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from fastapi import HTTPException
from api import environmental as env


def write_raster(path, value, *, crs='EPSG:4326', transform=None, nodata=-9999, array=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.full((20, 20), value, dtype='float32') if array is None else np.array(array, dtype='float32')
    with rasterio.open(path, 'w', driver='GTiff', width=data.shape[1], height=data.shape[0],
                       count=1, dtype='float32', crs=crs, transform=transform or from_origin(91, 27, .1, .1), nodata=nodata) as ds:
        ds.write(data, 1)


def register(root):
    doc = {'archiveSha256':'synthetic-test-fixture-only', 'files': {str(p.relative_to(root)): {'sha256':env.digest(p), 'size':p.stat().st_size}
             for p in root.rglob('*.tif')}}
    (root / 'inventory.json').write_text(json.dumps(doc,sort_keys=True))
    _, identity = env.inventory()
    (root / 'ready.json').write_text(json.dumps({'inventoryId':identity,'referenceChecks':'synthetic test fixture, not real raster verification'}))
    env.checked_hash.cache_clear()
    return doc


@pytest.fixture
def rasters(tmp_path,monkeypatch):
    monkeypatch.setenv('RASTER_DATA_ROOT',str(tmp_path))
    c,_,_,_=env.handoff()
    with zipfile.ZipFile(env.HANDOFF) as z:
        example=json.loads(z.read(env.PREFIX+'reproducible_examples/event_id_467_v2.json'))['raw_features']
    for path in env.required_paths('2'):
        name=Path(path).name
        if name.endswith('_Map.tif'): value=10;nodata=0
        elif 'SoilGrids' in name:
            key=next(k for k,v in c['soil_rasters'].items() if v==name)
            scale=1000 if key in ['clay_fraction','sand_fraction'] else 10 if key=='soil_ph' else 1
            value=example[key]*scale;nodata=None
        else:
            key=next(k for k,v in c['worldclim_rasters'].items() if v==name)
            value=example[key];nodata=-9999
        write_raster(tmp_path/path,value,nodata=nodata)
    register(tmp_path)
    return tmp_path


def test_reference_values_from_synthetic_grids_and_provenance(rasters):
    for v in ['1','2']:
        result=env.extract(26.19,91.71,v)
        assert result['canScore'] and not result['missingFields']
        assert result['inputs']['clay_fraction']==pytest.approx(.199)
        assert len(result['inputs'])==(5 if v=='1' else 14)
        p=result['provenance'][0]
        assert p['row']==8 and p['column']==7 and p['sha256'] and p['crs']=='EPSG:4326'
        assert 'archiveSha256' in result


def test_missing_pixel_policies_and_original_fraction_rule(rasters):
    c,_,_,_=env.handoff()
    clay=rasters/c['soilgrids_dir']/c['soil_rasters']['clay_fraction']
    write_raster(clay,1001,nodata=None);register(rasters)
    r=env.extract(26.19,91.71,'2')
    assert r['inputs']['clay_fraction'] is None and r['inputs']['sand_fraction'] is None
    ph=rasters/c['soilgrids_dir']/c['soil_rasters']['soil_ph']
    write_raster(ph,0,nodata=None);register(rasters)
    r=env.extract(26.19,91.71,'1');assert not r['canScore'] and len(r['missingFields'])==4
    r=env.extract(26.19,91.71,'2');assert r['canScore'] and len(r['missingFields'])==4
    tile=rasters/next(p for p in env.required_paths('1') if p.endswith('_Map.tif'))
    write_raster(tile,20,nodata=0);register(rasters)
    assert 'worldcover_class' in env.extract(26.19,91.71,'2')['invalidFields']
    write_raster(tile,0,nodata=0);register(rasters)
    assert not env.extract(26.19,91.71,'2')['canScore']


def test_missing_files_are_not_imputed_and_v1_does_not_require_v2(rasters):
    c,_,_,_=env.handoff()
    (rasters/c['worldclim_dir']/next(iter(c['worldclim_rasters'].values()))).unlink()
    assert env.extract(26.19,91.71,'1')['canScore']
    with pytest.raises(HTTPException) as e: env.extract(26.19,91.71,'2')
    assert e.value.status_code==503


def test_pixels_edges_mask_crs_and_tamper_detection(rasters):
    relative=next(p for p in env.required_paths('1') if p.endswith('_Map.tif'))
    path=rasters/relative
    write_raster(path,0,array=[[10,30],[40,-9999]],transform=from_origin(0,2,1,1))
    doc=register(rasters);sources=env.handoff()[2]
    assert env.sample(relative,0,2,doc,sources)[0]==10
    assert env.sample(relative,1.1,1.9,doc,sources)[0]==30
    assert env.sample(relative,1,1,doc,sources)[0] is None
    assert env.sample(relative,2,1,doc,sources)[1]['status']=='OUTSIDE_RASTER'
    assert env.sample(relative,0,0,doc,sources)[1]['status']=='OUTSIDE_RASTER'
    from pyproj import Transformer
    x,y=Transformer.from_crs(4326,3857,always_xy=True).transform(91.71,26.19)
    write_raster(path,50,crs='EPSG:3857',transform=from_origin(x-1000,y+1000,100,100));doc=register(rasters)
    assert env.sample(relative,91.71,26.19,doc,sources)[0]==50
    path.write_bytes(path.read_bytes()+b'altered')
    with pytest.raises(HTTPException) as e: env.checked_file(relative,doc)
    assert e.value.status_code==503


def test_stale_unverified_and_unsupported_locations(rasters):
    old=env.extract(26.19,91.71,'1')
    doc,_=env.inventory();doc['extra']='new revision';(rasters/'inventory.json').write_text(json.dumps(doc))
    with pytest.raises(HTTPException) as e:env.verify_snapshot(old)
    assert e.value.status_code==409
    with pytest.raises(HTTPException) as e:env.extract(26.19,91.71,'1')
    assert e.value.status_code==503
    with pytest.raises(HTTPException) as e:env.extract(12.98,77.67,'1')
    assert e.value.status_code==422


def test_coordinate_api_inspect_then_score_and_permissions(actors,rasters):
    c=actors['official'];payload={'lat':26.19,'lng':91.71,'modelVersion':'2'}
    assert actors['citizen'].post('/api/assessment/features',json=payload).status_code==403
    preview=c.post('/api/assessment/features',json=payload)
    assert preview.status_code==201,preview.text
    p=preview.json()
    assert c.get('/api/records/predictions').json()['total']==0
    assert c.post('/api/assessment/run',json={'extractionId':p['id'],'inputs':{}}).status_code==422
    result=c.post('/api/assessment/run',json={'extractionId':p['id']})
    assert result.status_code==201,result.text
    r=result.json();assert r['experimental_presence_background_score']==pytest.approx(.9369784686315531,abs=1e-12)
    assert not r['simulated'] and r['assessmentMode']=='coordinate-extraction' and r['provenance']==p['provenance']
    assert c.post('/api/assessment/run',json={'extractionId':p['id']}).json()['id']==r['id']
    assert c.get('/api/records/predictions').json()['total']==1
    assert actors['citizen'].post('/api/assessment/run',json={'extractionId':p['id']}).status_code==403
    for bad in [dict(payload,lat=True),dict(payload,lat='26.19'),dict(payload,lat=91),dict(payload,modelVersion='3')]:
        assert c.post('/api/assessment/features',json=bad).status_code==422


def test_unprepared_server_returns_unavailable_without_predictions(actors,tmp_path,monkeypatch):
    monkeypatch.setenv('RASTER_DATA_ROOT',str(tmp_path))
    r=actors['official'].post('/api/assessment/features',json={'lat':26.19,'lng':91.71})
    assert r.status_code==503 and actors['official'].get('/api/records/predictions').json()['total']==0


def test_archive_validation_preserves_existing_files(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('prepare_rasters',env.ROOT/'scripts/prepare-rasters.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setenv('RASTER_DATA_ROOT',str(tmp_path/'data'))
    bad=tmp_path/'bad.zip'
    with zipfile.ZipFile(bad,'w') as z:z.writestr('../escape.txt','bad')
    with pytest.raises(ValueError,match='unsafe'):module.prepare(bad)
    assert not (tmp_path/'escape.txt').exists()
    good=tmp_path/'toy.zip'
    with zipfile.ZipFile(good,'w') as z:
        for path in env.required_paths('2'):z.writestr(path,b'explicitly synthetic fixture bytes')
    first=module.prepare(good);assert len(first['files'])==23
    assert module.prepare(good)==first
    f=env.data_root()/env.required_paths('1')[0];f.write_bytes(b'user data to preserve')
    with pytest.raises(ValueError,match='preserved'):module.prepare(good)
    assert f.read_bytes()==b'user data to preserve'
