"""Optional geographic suggestions; never infer incident severity from coordinates."""
from pathlib import Path
import httpx
from fastapi import HTTPException
from shapely.geometry import Point, shape
from sqlalchemy import text
from . import environmental
from .db import Record, now

PROVIDER = 'https://nominatim.openstreetmap.org/reverse'
ATTRIBUTION = '© OpenStreetMap contributors, ODbL; Nominatim reverse geocoding'


def lookup(lat, lng, db):
    fields, provenance, unavailable = {}, {}, {}
    config, boundary, sources, _ = environmental.handoff()
    state = next((f['properties'].get('shapeName') for f in boundary['features']
                  if shape(f['geometry']).covers(Point(lng, lat))), None)
    if state:
        fields['state'] = state
        provenance['state'] = {'source': 'Supplied North East India state boundary', 'type': 'Boundary lookup'}
    # Sample only the terrain layer; no model prediction or fabricated fallback.
    try:
        doc, identity = environmental.inventory()
        relative = str(Path(config['worldclim_dir']) / config['worldclim_rasters']['slope_degrees'])
        environmental.verify_snapshot({'inventoryId': identity, 'method': environmental.METHOD, 'provenance': [{'file': relative}]})
        slope, info = environmental.sample(relative, lng, lat, doc, sources)
        if slope is not None and 0 <= slope <= 90:
            fields['slope'] = slope
            provenance['slope'] = {**info, 'source': 'Supplied WorldClim-derived terrain raster', 'unit': 'degrees', 'type': 'Derived terrain'}
        else:
            unavailable['slope'] = 'No valid terrain pixel at these coordinates'
    except HTTPException as exc:
        unavailable['slope'] = exc.detail

    # Database lock and timestamp enforce the public provider's one request/second
    # limit across workers. Cache coordinates across users; no account data sent.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('reverse-geocoding'))"))
    cache_id = f'place:{lat:.6f}:{lng:.6f}'
    cached = db.get(Record, cache_id)
    payload = cached.data if cached and now() - cached.updated < 2592000 else None
    error = None
    if payload is None:
        clock = db.get(Record, 'place-provider-clock')
        if clock and now() - clock.data['requestedAt'] < 2:
            error = 'Place lookup is busy; try again in a few seconds'
        else:
            if clock is None:
                clock = Record(id='place-provider-clock', kind='place-cache', data={})
                db.add(clock)
            clock.data = {'requestedAt': now()}
            try:
                with httpx.Client(timeout=8, follow_redirects=False) as client:
                    response = client.get(PROVIDER, params={'lat': lat, 'lon': lng, 'format': 'jsonv2', 'addressdetails': 1, 'accept-language': 'en'},
                        headers={'User-Agent': 'Ashtaraksha/1.0 (https://github.com/dampq/landslide)'})
                    response.raise_for_status()
                    raw = response.json()
                address = raw.get('address', {})
                if not isinstance(address, dict):
                    raise ValueError('Invalid provider response')
                payload = {'name': next((address[k] for k in ['village', 'town', 'city', 'hamlet', 'suburb', 'neighbourhood'] if address.get(k)), None),
                           'district': address.get('state_district'), 'state': address.get('state')}
                payload = {k: v[:2000] for k, v in payload.items() if isinstance(v, str) and v.strip()}
                if cached is None:
                    cached = Record(id=cache_id, kind='place-cache', data=payload)
                    db.add(cached)
                else:
                    cached.data, cached.updated = payload, now()
            except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                error = 'Online place lookup unavailable; check network access to nominatim.openstreetmap.org or enter details manually'
    db.flush()
    for key in ['name', 'district', 'state']:
        if payload and payload.get(key) and key not in fields:
            fields[key] = payload[key]
            provenance[key] = {'source': ATTRIBUTION, 'url': 'https://www.openstreetmap.org/copyright', 'type': 'Nearby mapped address suggestion', 'retrievedAt': cached.updated}
        if key not in fields:
            unavailable[key] = error or 'Not supplied by the map provider; enter manually'
    return {'lat': lat, 'lng': lng, 'fields': fields, 'provenance': provenance, 'unavailable': unavailable,
            'notice': 'Suggestions may describe a nearby mapped feature. Confirm against the selected pin. Severity is not inferred.'}
