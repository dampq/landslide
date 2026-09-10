"""Monitoring workflows, media, forecasts, sync, and response operations."""
import base64
import binascii
import hashlib
import json
import math
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone

import providers
import risk_engine

SCHEMA = '''
CREATE TABLE IF NOT EXISTS events (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, record_id TEXT, owner TEXT,
 actor TEXT, operation TEXT, at REAL, data TEXT);
CREATE TABLE IF NOT EXISTS media (
 id TEXT PRIMARY KEY, report_id TEXT NOT NULL REFERENCES records(id), owner TEXT NOT NULL,
 filename TEXT, mime TEXT, digest TEXT, content BLOB, at REAL,
 UNIQUE(report_id, digest));
CREATE TABLE IF NOT EXISTS device_keys (
 sensor_id TEXT PRIMARY KEY REFERENCES records(id), digest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS readings (
 id TEXT PRIMARY KEY, sensor_id TEXT REFERENCES records(id), client_id TEXT,
 at REAL, value REAL, unit TEXT, received REAL, UNIQUE(sensor_id, client_id));
CREATE INDEX IF NOT EXISTS reading_time ON readings(sensor_id, at);
CREATE TABLE IF NOT EXISTS weather_cache (location_id TEXT PRIMARY KEY REFERENCES records(id), at REAL, data TEXT);
CREATE TABLE IF NOT EXISTS settings (user_id TEXT PRIMARY KEY REFERENCES users(id), data TEXT);
CREATE TABLE IF NOT EXISTS notifications (
 id TEXT PRIMARY KEY, alert_id TEXT REFERENCES records(id), user_id TEXT REFERENCES users(id),
 channel TEXT, body TEXT, destination TEXT, status TEXT, attempts INTEGER DEFAULT 0,
 next_at REAL DEFAULT 0, provider_id TEXT, last_error TEXT, read_at REAL,
 UNIQUE(alert_id, user_id, channel));
CREATE TABLE IF NOT EXISTS limits (key TEXT PRIMARY KEY, starts REAL, count INTEGER);
CREATE TABLE IF NOT EXISTS jobs (name TEXT PRIMARY KEY, last_at REAL, error TEXT);
'''


def event(con, kind, record, owner, actor, operation):
    con.execute('INSERT INTO events(kind,record_id,owner,actor,operation,at,data) VALUES (?,?,?,?,?,?,?)',
                (kind, record['id'], owner, actor, operation, time.time(), json.dumps(record)))


def get(c, con, kind, rid):
    row = con.execute('SELECT * FROM records WHERE kind=? AND id=?', (kind, rid)).fetchone()
    if row is None:
        raise c.ApiError(404, f'{kind} record not found')
    return row, json.loads(row['data'])


def save(con, kind, record, owner, actor):
    record['updatedAt'] = time.time()
    con.execute('UPDATE records SET data=? WHERE id=?', (json.dumps(record), record['id']))
    event(con, kind, record, owner, actor, 'updated')
    return record


def insert(con, kind, data, owner, actor):
    record = dict(data, id=str(uuid.uuid4()), updatedAt=time.time())
    con.execute('INSERT INTO records VALUES (?,?,?,?,?)', (record['id'], kind, owner, None, json.dumps(record)))
    event(con, kind, record, owner, actor, 'created')
    return record


def authority(c, user):
    if user['role'] != 'authority':
        raise c.ApiError(403, 'Authority role required')


def access_report(c, con, rid, user):
    row, record = get(c, con, 'reports', rid)
    if user['role'] != 'authority' and row['owner'] != user['id']:
        raise c.ApiError(404, 'Report not found')
    return row, record


def pagination(c, query):
    try:
        limit, offset = int(query.get('limit', 100)), int(query.get('offset', 0))
    except (ValueError, TypeError):
        raise c.ApiError(400, 'Invalid pagination')
    if not 1 <= limit <= 500 or offset < 0:
        raise c.ApiError(400, 'limit must be 1-500 and offset nonnegative')
    return limit, offset


def list_records(c, con, kind, user, query):
    limit, offset = pagination(c, query)
    where, args = ['kind=?'], [kind]
    if kind == 'reports' and user['role'] != 'authority':
        where.append('owner=?')
        args.append(user['id'])
    for field in ['state', 'district', 'level', 'severity', 'status', 'locationId']:
        if field in query:
            where.append(f"json_extract(data, '$.{field}')=?")
            args.append(query[field])
    condition = ' AND '.join(where)
    total = con.execute('SELECT COUNT(*) FROM records WHERE ' + condition, args).fetchone()[0]
    rows = con.execute('SELECT data FROM records WHERE ' + condition + ' ORDER BY rowid DESC LIMIT ? OFFSET ?',
                       args + [limit, offset]).fetchall()
    return {'items': [json.loads(r[0]) for r in rows], 'total': total, 'limit': limit, 'offset': offset}


def rate_limit(c, key, maximum=240):
    now = time.time()
    with c.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('DELETE FROM limits WHERE starts<?', (now - 3600,))
        row = con.execute('SELECT * FROM limits WHERE key=?', (key,)).fetchone()
        if row and now - row['starts'] < 60:
            if row['count'] >= maximum:
                raise c.ApiError(429, 'Rate limit reached; retry after one minute')
            con.execute('UPDATE limits SET count=count+1 WHERE key=?', (key,))
        else:
            con.execute('INSERT OR REPLACE INTO limits VALUES (?,?,1)', (key, now))


def validate_extra(c, kind, data):
    for key in ['severity', 'level', 'status']:
        if key in data and not isinstance(data[key], str):
            raise c.ApiError(400, f'{key} must be a string')
    if kind in {'villages', 'infrastructure', 'history', 'satellite'}:
        c.required(data, 'name')
        c.number(data, 'lat', -90, 90)
        c.number(data, 'lng', -180, 180)
    if kind in {'villages', 'locations'} and 'population' in data:
        c.number(data, 'population', 0, 100_000_000)
    if kind == 'infrastructure':
        c.required(data, 'type')
    if kind == 'sensors':
        if 'feature' in data and (not isinstance(data['feature'], str) or data['feature'] not in risk_engine.FEATURES):
            raise c.ApiError(400, 'Sensor feature must name a risk input')
        for threshold in ['warningAbove', 'criticalAbove']:
            if threshold in data:
                c.number(data, threshold, -1_000_000, 1_000_000)
        if 'warningAbove' in data and 'criticalAbove' in data and data['warningAbove'] > data['criticalAbove']:
            raise c.ApiError(400, 'warningAbove cannot exceed criticalAbove')
    if kind in {'history', 'satellite'}:
        c.number(data, 'observedAt', 0, time.time() + 300)
        c.required(data, 'source')
    for key, high in [('rainfall', 2000), ('soil', 100), ('slope', 90), ('hospitalDistanceKm', 10000)]:
        if key in data:
            c.number(data, key, 0, high)
    if kind == 'alerts':
        if 'translations' in data and (not isinstance(data['translations'], dict) or any(k not in {'en', 'hi', 'as'} or not isinstance(v, str) or not 1 <= len(v) <= 2000 for k, v in data['translations'].items())):
            raise c.ApiError(400, 'translations must map en, hi or as to reviewed message text')
        for field in ['ack', 'resolved']:
            if field in data and not isinstance(data[field], bool):
                raise c.ApiError(400, f'{field} must be boolean')


def validate_links(c, con, data):
    for key, kind in [('locationId', 'locations'), ('roadId', 'roads')]:
        if key in data:
            c.required(data, key, 128)
            get(c, con, kind, data[key])


def settings_default():
    return {'language': 'en', 'inApp': True, 'sms': False, 'phone': '', 'states': []}


def alert_message(alert, language):
    # Informational review notices only. Local translations should be reviewed before field use.
    headings = {'en': 'Hazard notice - official review required',
                'hi': 'खतरे की सूचना - अधिकारी की समीक्षा आवश्यक',
                'as': 'বিপদৰ জাননী - বিষয়াৰ পৰ্যালোচনা প্ৰয়োজন'}
    translations = alert.get('translations', {})
    if isinstance(translations, dict) and isinstance(translations.get(language), str):
        return translations[language]
    return f"{headings.get(language, headings['en'])}: {alert['location']}. {alert['severity']}. {alert['description']}"


def publish(c, alert_id, user):
    authority(c, user)
    with c.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row, alert = get(c, con, 'alerts', alert_id)
        if alert.get('resolved'):
            raise c.ApiError(409, 'Resolved alerts cannot be published')
        if alert.get('reviewRequired') and not alert.get('approvedBy'):
            raise c.ApiError(409, 'An authority must approve this screening alert before publication')
        count = 0
        for account in con.execute('SELECT id FROM users').fetchall():
            pref_row = con.execute('SELECT data FROM settings WHERE user_id=?', (account['id'],)).fetchone()
            pref = json.loads(pref_row[0]) if pref_row else settings_default()
            if pref['states'] and alert.get('state') not in pref['states']:
                continue
            for channel in ['inApp', 'sms']:
                if not pref[channel]:
                    continue
                status = 'delivered' if channel == 'inApp' else ('pending' if os.environ.get('NOTIFICATION_MODE') == 'live' else 'dry-run')
                result = con.execute('INSERT OR IGNORE INTO notifications(id,alert_id,user_id,channel,body,destination,status) VALUES (?,?,?,?,?,?,?)',
                          (str(uuid.uuid4()), alert_id, account['id'], channel, alert_message(alert, pref['language']), pref['phone'], status))
                count += result.rowcount
        alert['publishedAt'] = time.time()
        save(con, 'alerts', alert, row['owner'], user['id'])
    return {'queued': count, 'externalDeliveryMode': os.environ.get('NOTIFICATION_MODE', 'dry-run')}


def process_notifications(c):
    # Never retry ambiguous provider acceptance automatically: that can duplicate SMS.
    if os.environ.get('NOTIFICATION_MODE') != 'live':
        return {'processed': 0, 'mode': 'dry-run'}
    processed = 0
    for _ in range(50):
        with c.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute("SELECT * FROM notifications WHERE channel='sms' AND status='pending' AND next_at<=? LIMIT 1", (time.time(),)).fetchone()
            if row is None:
                break
            _, alert = get(c, con, 'alerts', row['alert_id'])
            preference = con.execute('SELECT data FROM settings WHERE user_id=?', (row['user_id'],)).fetchone()
            pref = json.loads(preference[0]) if preference else settings_default()
            if alert.get('resolved') or not pref['sms'] or pref['phone'] != row['destination'] or (alert.get('reviewRequired') and not alert.get('approvedBy')):
                con.execute("UPDATE notifications SET status='cancelled',last_error='Alert or subscription no longer eligible' WHERE id=?", (row['id'],))
                continue
            con.execute("UPDATE notifications SET status='sending', attempts=attempts+1, next_at=? WHERE id=?", (time.time(), row['id']))
        try:
            result = providers.send_sms(row['destination'], row['body'])
            if not isinstance(result.get('sid'), str):
                raise ValueError('Missing provider message id')
            status, provider_id, error = 'accepted', result['sid'], None
        except Exception:
            status, provider_id, error = 'unknown', None, 'Provider outcome uncertain; check provider before retrying'
        with c.connect() as con:
            con.execute('UPDATE notifications SET status=?,provider_id=?,last_error=? WHERE id=?', (status, provider_id, error, row['id']))
        processed += 1
    with c.connect() as con:
        con.execute("UPDATE notifications SET status='unknown',last_error='Worker interrupted; verify provider before retry' WHERE status='sending' AND next_at<?", (time.time() - 300,))
        accepted = con.execute("SELECT id,provider_id FROM notifications WHERE status='accepted' LIMIT 50").fetchall()
    for row in accepted:
        try:
            result = providers.message_status(row['provider_id'])
            status = result.get('status')
            if status in {'delivered', 'failed', 'undelivered'}:
                with c.connect() as con:
                    con.execute('UPDATE notifications SET status=? WHERE id=?', (status, row['id']))
        except Exception:
            pass  # Keep accepted until the provider supplies a definitive delivery result.
    return {'processed': processed, 'mode': 'live'}


def refresh_weather(c, location_id):
    with c.connect() as con:
        _, location = get(c, con, 'locations', location_id)
    try:
        raw = providers.weather(location['lat'], location['lng'])
        hourly = raw['hourly']
        times = hourly['time']
        if not times or len(times) != len(hourly['precipitation']):
            raise ValueError('Malformed hourly data')
        now = time.time()
        def rain_between(start, end):
            selected = [v for t, v in zip(times, hourly['precipitation']) if start < t <= end]
            if not selected or any(v is None or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in selected):
                return None
            return round(sum(selected), 3)
        record = {'locationId': location_id, 'source': 'Open-Meteo', 'retrievedAt': now,
                  'rainfall24h': rain_between(now - 86400, now), 'rainfall72h': rain_between(now - 259200, now),
                  'forecastRainfall24h': rain_between(now, now + 86400),
                  'hourly': hourly, 'units': raw.get('hourly_units', {}),
                  'notice': 'Weather model output, not an on-site observation. Soil moisture is volumetric m3/m3, not saturation percent.'}
        with c.connect() as con:
            con.execute('INSERT OR REPLACE INTO weather_cache VALUES (?,?,?)', (location_id, now, json.dumps(record)))
        return record
    except c.ApiError:
        raise
    except Exception:
        raise c.ApiError(502, 'Weather provider unavailable or returned invalid data; existing cache was preserved')


def prediction(c, data, user):
    authority(c, user)
    location_id = c.required(data, 'locationId', 128)
    inputs = data.get('inputs')
    if not isinstance(inputs, dict):
        raise c.ApiError(400, 'inputs must contain the six risk features')
    observed = c.number(data, 'observedAt', 0, time.time() + 300)
    if time.time() - observed > 86400:
        raise c.ApiError(409, 'Risk inputs are older than 24 hours')
    try:
        result = risk_engine.assess(inputs)
    except ValueError as exc:
        raise c.ApiError(400, str(exc))
    except (OSError, KeyError, TypeError):
        raise c.ApiError(503, 'Configured model could not be loaded')
    with c.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row, location = get(c, con, 'locations', location_id)
        result.update(locationId=location_id, observedAt=observed, source=c.required(data, 'source'))
        record = insert(con, 'predictions', result, user['id'], user['id'])
        location.update(score=result['score'], level=result['level'], confidence=None,
                        predictionId=record['id'], riskMethod=result['method'], operationallyValidated=False)
        save(con, 'locations', location, row['owner'], user['id'])
        if result['level'] in {'High', 'Critical'}:
            active = con.execute("SELECT data FROM records WHERE kind='alerts' AND json_extract(data,'$.locationId')=? AND json_extract(data,'$.reviewRequired')=1 AND COALESCE(json_extract(data,'$.resolved'),0)=0", (location_id,)).fetchall()
            if not any(json.loads(a[0]).get('severity') == result['level'] for a in active):
                insert(con, 'alerts', {'type': 'RISK SCREENING REVIEW', 'severity': result['level'],
                       'location': location['name'], 'locationId': location_id, 'state': location['state'],
                       'description': f"Screening score {result['score']}/100. This is not a validated early warning.",
                       'action': 'Request qualified field assessment.', 'reviewRequired': True,
                       'predictionId': record['id'], 'resolved': False, 'ack': False}, user['id'], user['id'])
    return record


def priorities(c, con):
    locations = [json.loads(r[0]) for r in con.execute("SELECT data FROM records WHERE kind='locations'")]
    roads = [json.loads(r[0]) for r in con.execute("SELECT data FROM records WHERE kind='roads'")]
    output = []
    for loc in locations:
        score = loc.get('score')
        if score is None:
            continue
        blocked = sum(r.get('locationId') == loc['id'] and r.get('status') in {'Blocked', 'Partially Blocked'} for r in roads)
        people = loc.get('population', 0)
        distance = loc.get('hospitalDistanceKm', 0)
        value = round(.6 * score + .25 * min(people / 5000, 1) * 100 + .1 * min(blocked, 1) * 100 + .05 * min(distance / 50, 1) * 100, 2)
        output.append({'locationId': loc['id'], 'name': loc['name'], 'priorityScore': value,
                       'riskScore': score, 'population': people, 'blockedRoads': blocked,
                       'hospitalDistanceKm': distance, 'method': 'planning-index-v1',
                       'missingImpactData': [k for k in ['population', 'hospitalDistanceKm'] if k not in loc]})
    return sorted(output, key=lambda x: (-x['priorityScore'], x['locationId']))


def routes(c, method, path, data, user, query, token):
    parts = path.strip('/').split('/')
    if path == '/api/import' and method == 'POST':
        authority(c, user)
        kind, items = data.get('collection'), data.get('items')
        if not isinstance(kind, str) or kind not in c.COLLECTIONS - c.READ_ONLY or not isinstance(items, list) or len(items) > 100:
            raise c.ApiError(400, 'Use a writable collection and at most 100 items')
        results = []
        for index, item in enumerate(items):
            try:
                if not isinstance(item, dict):
                    raise c.ApiError(400, 'Item must be an object')
                status, record = c.dispatch('POST', '/api/' + kind, item, token)
                results.append({'index': index, 'status': status, 'record': record})
            except c.ApiError as exc:
                results.append({'index': index, 'status': exc.status, 'error': exc.message})
        return 200, {'results': results, 'atomic': False}
    if len(parts) == 3 and parts[1] == 'forecast' and method == 'POST':
        authority(c, user)
        return 201, forecast(c, parts[2], data, user)
    if path == '/api/settings':
        with c.connect() as con:
            row = con.execute('SELECT data FROM settings WHERE user_id=?', (user['id'],)).fetchone()
            pref = json.loads(row[0]) if row else settings_default()
            if method == 'GET':
                return 200, pref
            if method == 'PATCH':
                if set(data) - set(pref):
                    raise c.ApiError(400, 'Unknown settings field')
                pref.update(data)
                if pref['language'] not in {'en', 'hi', 'as'} or any(not isinstance(pref[k], bool) for k in ['sms', 'inApp']):
                    raise c.ApiError(400, 'Invalid language or notification setting')
                if not isinstance(pref['phone'], str) or (pref['sms'] and not re.fullmatch(r'\+[1-9]\d{7,14}', pref['phone'])):
                    raise c.ApiError(400, 'SMS requires an international phone number such as +919876543210')
                if not isinstance(pref['states'], list) or len(pref['states']) > 8 or any(not isinstance(s, str) or len(s) > 80 for s in pref['states']):
                    raise c.ApiError(400, 'states must be a list of up to eight state names')
                con.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (user['id'], json.dumps(pref)))
                return 200, pref
    if path == '/api/auth/password' and method == 'POST':
        old = c.required(data, 'currentPassword', 256)
        new = c.required(data, 'newPassword', 256)
        if len(new) < 12:
            raise c.ApiError(400, 'New password needs at least 12 characters')
        import hmac
        if not hmac.compare_digest(c.password_hash(old, user['salt']), user['password']):
            raise c.ApiError(401, 'Current password incorrect')
        salt = secrets.token_hex(16)
        with c.connect() as con:
            con.execute('UPDATE users SET salt=?,password=? WHERE id=?', (salt, c.password_hash(new, salt), user['id']))
            con.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
        return 200, {'changed': True, 'loginRequired': True}
    if path == '/api/sync' and method == 'POST':
        reports = data.get('reports')
        if not isinstance(reports, list) or len(reports) > 100:
            raise c.ApiError(400, 'reports must be an array with at most 100 items')
        results = []
        for report in reports:
            try:
                if not isinstance(report, dict):
                    raise c.ApiError(400, 'Each report must be an object')
                status, record = c.dispatch('POST', '/api/reports', report, token)
                results.append({'clientId': report.get('clientId'), 'status': status, 'record': record})
            except c.ApiError as exc:
                results.append({'clientId': report.get('clientId') if isinstance(report, dict) else None,
                                'status': exc.status, 'error': exc.message})
        return 200, {'results': results}
    if path in {'/api/sync', '/api/audit'} and method == 'GET':
        if path == '/api/audit':
            authority(c, user)
        limit, _ = pagination(c, query)
        try:
            cursor = int(query.get('cursor', 0))
            if cursor < 0:
                raise ValueError()
        except ValueError:
            raise c.ApiError(400, 'cursor must be nonnegative')
        with c.connect() as con:
            maximum = con.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
            where, params = 'seq>?', [cursor]
            if user['role'] != 'authority':
                where += " AND kind NOT IN ('imageAnalyses','deployments') AND (kind!='reports' OR owner=?)"
                params.append(user['id'])
            rows = con.execute('SELECT * FROM events WHERE ' + where + ' ORDER BY seq LIMIT ?', params + [limit + 1]).fetchall()
            more = len(rows) > limit
            rows = rows[:limit]
            items = [{'cursor': r['seq'], 'kind': r['kind'], 'operation': r['operation'], 'at': r['at'], 'record': json.loads(r['data'])} for r in rows]
            return 200, {'items': items, 'nextCursor': rows[-1]['seq'] if more else max(cursor, maximum), 'hasMore': more}
    if len(parts) == 4 and parts[1] == 'reports' and parts[3] == 'media':
        rid = parts[2]
        with c.connect() as con:
            access_report(c, con, rid, user)
            if method == 'GET':
                rows = con.execute('SELECT id,filename,mime,digest,at,length(content) AS size FROM media WHERE report_id=?', (rid,)).fetchall()
                return 200, {'items': [dict(r) for r in rows]}
            if method == 'POST':
                filename = c.required(data, 'filename', 150)
                if '/' in filename or '\\' in filename or any(ord(ch) < 32 for ch in filename):
                    raise c.ApiError(400, 'Filename cannot contain paths or control characters')
                encoded = c.required(data, 'base64', 14_000_000)
                try:
                    content = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error):
                    raise c.ApiError(400, 'Invalid base64 file')
                if not 12 <= len(content) <= 10_000_000:
                    raise c.ApiError(413, 'Media must be 12 bytes to 10 MB')
                mime = 'image/png' if content.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if content.startswith(b'\xff\xd8\xff') else 'image/webp' if content[:4] == b'RIFF' and content[8:12] == b'WEBP' else 'video/mp4' if content[4:8] == b'ftyp' else None
                if mime is None:
                    raise c.ApiError(415, 'Only PNG, JPEG, WebP and MP4 signatures are accepted')
                con.execute('BEGIN IMMEDIATE')
                digest = hashlib.sha256(content).hexdigest()
                previous = con.execute('SELECT id FROM media WHERE report_id=? AND digest=?', (rid, digest)).fetchone()
                if previous:
                    return 200, {'id': previous['id'], 'duplicate': True}
                count = con.execute('SELECT COUNT(*) FROM media WHERE report_id=?', (rid,)).fetchone()[0]
                if count >= 10:
                    raise c.ApiError(409, 'A report can contain at most 10 files')
                used = con.execute('SELECT COALESCE(SUM(length(content)),0) FROM media WHERE owner=?', (user['id'],)).fetchone()[0]
                if used + len(content) > int(os.environ.get('MAX_USER_MEDIA_BYTES', '100000000')):
                    raise c.ApiError(413, 'Account media storage quota exceeded')
                mid = str(uuid.uuid4())
                con.execute('INSERT INTO media VALUES (?,?,?,?,?,?,?,?)', (mid, rid, user['id'], filename, mime, digest, content, time.time()))
                return 201, {'id': mid, 'filename': filename, 'mime': mime, 'size': len(content), 'sha256': digest}
    if len(parts) in {3, 4} and parts[1] == 'media':
        with c.connect() as con:
            row = con.execute('SELECT * FROM media WHERE id=?', (parts[2],)).fetchone()
            if row is None:
                raise c.ApiError(404, 'Media not found')
            access_report(c, con, row['report_id'], user)
            if method == 'GET' and len(parts) == 3:
                return 200, {'id': row['id'], 'filename': row['filename'], 'mime': row['mime'],
                             'base64': base64.b64encode(row['content']).decode()}
            if method == 'POST' and len(parts) == 4 and parts[3] == 'analyze':
                authority(c, user)
                if not row['mime'].startswith('image/'):
                    raise c.ApiError(400, 'Image analysis requires an image')
                if not os.environ.get('VISION_ENDPOINT'):
                    raise c.ApiError(503, 'Image analysis provider is not configured')
                encoded, mime = base64.b64encode(row['content']).decode(), row['mime']
        if method == 'POST' and len(parts) == 4 and parts[3] == 'analyze':
            try:
                analysis = providers.analyze_image(encoded, mime)
                if not isinstance(analysis, dict) or not isinstance(analysis.get('labels'), list):
                    raise ValueError()
            except Exception:
                raise c.ApiError(502, 'Image analysis provider failed')
            with c.connect() as con:
                record = insert(con, 'imageAnalyses', {'mediaId': parts[2], 'reportId': row['report_id'],
                                'labels': analysis['labels'], 'reviewRequired': True}, user['id'], user['id'])
            return 201, record
    if len(parts) == 4 and parts[1] == 'sensors' and parts[3] == 'key' and method == 'POST':
        authority(c, user)
        with c.connect() as con:
            get(c, con, 'sensors', parts[2])
            key = secrets.token_urlsafe(32)
            con.execute('INSERT OR REPLACE INTO device_keys VALUES (?,?)', (parts[2], hashlib.sha256(key.encode()).hexdigest()))
        return 201, {'sensorId': parts[2], 'deviceKey': key, 'notice': 'Save now; issuing a new key revokes the previous key.'}
    if len(parts) == 4 and parts[1] == 'sensors' and parts[3] == 'readings' and method == 'GET':
        limit, offset = pagination(c, query)
        with c.connect() as con:
            get(c, con, 'sensors', parts[2])
            rows = con.execute('SELECT * FROM readings WHERE sensor_id=? ORDER BY at DESC LIMIT ? OFFSET ?', (parts[2], limit, offset)).fetchall()
            return 200, {'items': [dict(r) for r in rows], 'limit': limit, 'offset': offset}
    if len(parts) in {3, 4} and parts[1] == 'weather':
        if method == 'POST' and len(parts) == 4 and parts[3] == 'refresh':
            authority(c, user)
            return 200, refresh_weather(c, parts[2])
        if method == 'GET' and len(parts) == 3:
            with c.connect() as con:
                get(c, con, 'locations', parts[2])
                row = con.execute('SELECT * FROM weather_cache WHERE location_id=?', (parts[2],)).fetchone()
                if not row:
                    raise c.ApiError(404, 'No cached weather; request a refresh first')
                return 200, dict(json.loads(row['data']), stale=time.time() - row['at'] > 3600)
    if path == '/api/predictions' and method == 'POST':
        return 201, prediction(c, data, user)
    if len(parts) == 4 and parts[1] == 'alerts' and method == 'POST':
        authority(c, user)
        if parts[3] == 'publish':
            return 200, publish(c, parts[2], user)
        if parts[3] in {'approve', 'acknowledge', 'resolve'}:
            with c.connect() as con:
                con.execute('BEGIN IMMEDIATE')
                row, record = get(c, con, 'alerts', parts[2])
                if parts[3] == 'approve':
                    record.update(approvedBy=user['id'], approvalNote=c.required(data, 'note'), approvedAt=time.time())
                elif parts[3] == 'acknowledge':
                    record.update(ack=True, acknowledgedBy=user['id'])
                else:
                    record.update(resolved=True, resolvedBy=user['id'])
                return 200, save(con, 'alerts', record, row['owner'], user['id'])
    if path == '/api/notifications' and method == 'GET':
        limit, offset = pagination(c, query)
        with c.connect() as con:
            rows = con.execute('SELECT id,alert_id,channel,body,status,read_at,last_error FROM notifications WHERE user_id=? ORDER BY rowid DESC LIMIT ? OFFSET ?', (user['id'], limit, offset)).fetchall()
            return 200, {'items': [dict(r) for r in rows]}
    if len(parts) == 4 and parts[1] == 'notifications' and parts[3] == 'retry' and method == 'POST':
        authority(c, user)
        if data.get('providerChecked') is not True:
            raise c.ApiError(400, 'Confirm providerChecked after checking that the message was not accepted')
        if os.environ.get('NOTIFICATION_MODE') != 'live':
            raise c.ApiError(409, 'Live notification mode is not enabled')
        with c.connect() as con:
            result = con.execute("UPDATE notifications SET status='pending',next_at=0,last_error=NULL WHERE id=? AND status='unknown' AND attempts<3", (parts[2],))
            if not result.rowcount:
                raise c.ApiError(409, 'Only uncertain messages with fewer than three attempts can be retried')
        return 200, {'queued': True}
    if len(parts) == 4 and parts[1] == 'notifications' and parts[3] == 'read' and method == 'POST':
        with c.connect() as con:
            result = con.execute('UPDATE notifications SET read_at=? WHERE id=? AND user_id=?', (time.time(), parts[2], user['id']))
            if not result.rowcount:
                raise c.ApiError(404, 'Notification not found')
        return 200, {'read': True}
    if path == '/api/response/priorities' and method == 'GET':
        authority(c, user)
        with c.connect() as con:
            return 200, {'items': priorities(c, con)}
    if path == '/api/deployments' and method == 'POST':
        authority(c, user)
        team_id, location_id = c.required(data, 'teamId', 128), c.required(data, 'locationId', 128)
        with c.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row, team = get(c, con, 'teams', team_id)
            get(c, con, 'locations', location_id)
            if team['status'] != 'Available':
                raise c.ApiError(409, 'Team is not available')
            deployment = insert(con, 'deployments', {'teamId': team_id, 'locationId': location_id,
                              'status': 'En Route', 'notes': c.required(data, 'notes')}, user['id'], user['id'])
            team.update(status='En Route', deploymentId=deployment['id'])
            save(con, 'teams', team, row['owner'], user['id'])
            return 201, deployment
    if len(parts) == 4 and parts[1] == 'deployments' and parts[3] == 'status' and method == 'POST':
        authority(c, user)
        with c.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row, deployment = get(c, con, 'deployments', parts[2])
            allowed = {'En Route': {'On Site', 'Cancelled'}, 'On Site': {'Completed', 'Cancelled'}}
            status = data.get('status')
            if status not in allowed.get(deployment['status'], set()):
                raise c.ApiError(409, 'Invalid deployment status transition')
            deployment['status'] = status
            tr, team = get(c, con, 'teams', deployment['teamId'])
            team['status'] = 'Available' if status in {'Completed', 'Cancelled'} else 'Deployed'
            if team['status'] == 'Available':
                team.pop('deploymentId', None)
            save(con, 'teams', team, tr['owner'], user['id'])
            return 200, save(con, 'deployments', deployment, row['owner'], user['id'])
    if path in {'/api/dashboard', '/api/analytics', '/api/gis'} and method == 'GET':
        with c.connect() as con:
            rows = con.execute('SELECT * FROM records').fetchall()
            groups = {}
            for row in rows:
                if row['kind'] in {'reports', 'imageAnalyses'} and user['role'] != 'authority' and row['owner'] != user['id']:
                    continue
                record = json.loads(row['data'])
                if query.get('state') and record.get('state') != query['state']:
                    continue
                groups.setdefault(row['kind'], []).append(record)
            if path == '/api/gis':
                points = [dict(item, kind=kind) for kind in ['locations', 'villages', 'infrastructure', 'history', 'satellite'] for item in groups.get(kind, [])]
                if 'bbox' in query:
                    try:
                        west, south, east, north = map(float, query['bbox'].split(','))
                        if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
                            raise ValueError()
                    except ValueError:
                        raise c.ApiError(400, 'bbox must be west,south,east,north in valid coordinate ranges')
                    points = [p for p in points if west <= p['lng'] <= east and south <= p['lat'] <= north]
                return 200, {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'id': p['id'],
                    'geometry': {'type': 'Point', 'coordinates': [p['lng'], p['lat']]}, 'properties': p} for p in points]}
            if path == '/api/analytics':
                by_state = {}
                for location in groups.get('locations', []):
                    state = by_state.setdefault(location['state'], {'name': location['state'], 'locations': 0, 'maxRisk': None})
                    state['locations'] += 1
                    if location.get('score') is not None:
                        state['maxRisk'] = max(state['maxRisk'] or 0, location['score'])
                months = {}
                for item in groups.get('history', []):
                    month = datetime.fromtimestamp(item['observedAt'], timezone.utc).strftime('%Y-%m')
                    months[month] = months.get(month, 0) + 1
                return 200, {'states': list(by_state.values()), 'historicalEventsByMonth': months,
                             'notice': 'Aggregates only records stored in this database; missing data is not inferred.'}
            alerts = [a for a in groups.get('alerts', []) if not a.get('resolved')]
            levels = {level: sum(l.get('level') == level for l in groups.get('locations', [])) for level in c.LEVELS}
            return 200, {'counts': {kind: len(items) for kind, items in groups.items()}, 'riskLevels': levels,
                         'activeAlerts': alerts, 'locations': groups.get('locations', []),
                         'generatedAt': time.time(), 'dataSource': 'database'}
    if path == '/api/system' and method == 'GET':
        authority(c, user)
        with c.connect() as con:
            return 200, {'weatherProvider': 'Open-Meteo', 'modelConfigured': bool(os.environ.get('MODEL_PATH')),
                         'visionConfigured': bool(os.environ.get('VISION_ENDPOINT')),
                         'notificationMode': os.environ.get('NOTIFICATION_MODE', 'dry-run'),
                         'jobs': [dict(row) for row in con.execute('SELECT * FROM jobs')]}
    return None


def forecast(c, location_id, data, user):
    inputs = data.get('inputs')
    if not isinstance(inputs, dict):
        raise c.ApiError(400, 'inputs must contain the six current risk features')
    try:
        risk_engine.features(inputs)
    except ValueError as exc:
        raise c.ApiError(400, str(exc))
    observed = c.number(data, 'observedAt', 0, time.time() + 300)
    if time.time() - observed > 86400:
        raise c.ApiError(409, 'Risk observations are stale')
    with c.connect() as con:
        get(c, con, 'locations', location_id)
        row = con.execute('SELECT * FROM weather_cache WHERE location_id=?', (location_id,)).fetchone()
        if not row or time.time() - row['at'] > 3600:
            raise c.ApiError(409, 'Refresh weather before forecasting')
        weather = json.loads(row['data'])
    now = time.time()
    scenarios = []
    for horizon in [6, 12, 24, 48]:
        at = now + horizon * 3600
        scenario = dict(inputs)
        for hours, field in [(24, 'rainfall24h'), (72, 'rainfall72h')]:
            rain = [value for ts, value in zip(weather['hourly']['time'], weather['hourly']['precipitation']) if at - hours * 3600 < ts <= at]
            if len(rain) != hours or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in rain):
                raise c.ApiError(502, 'Weather does not cover the complete forecast interval')
            scenario[field] = sum(rain)
        try:
            assessment = risk_engine.assess(scenario)
        except (ValueError, OSError, KeyError, TypeError):
            raise c.ApiError(503, 'Forecast model or weather inputs are invalid')
        scenarios.append(dict(assessment, horizonHours=horizon, forecastAt=at))
    with c.connect() as con:
        return insert(con, 'forecasts', {'locationId': location_id, 'observedAt': observed,
                      'source': 'Open-Meteo rainfall scenarios', 'scenarios': scenarios,
                      'assumptions': 'Soil moisture, slope, ground movement and historical count are held constant. Weather rainfall replaces observed rain for the rolling windows. These are screening scenarios, not validated hazard forecasts.'}, user['id'], user['id'])


def telemetry(c, data, key):
    sensor_id, client_id = c.required(data, 'sensorId', 128), c.required(data, 'clientId', 128)
    observed = c.number(data, 'observedAt', 0, time.time() + 300)
    value = c.number(data, 'value', -1_000_000, 1_000_000)
    unit = c.required(data, 'unit', 30)
    with c.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT digest FROM device_keys WHERE sensor_id=?', (sensor_id,)).fetchone()
        import hmac
        if row is None or not hmac.compare_digest(row['digest'], hashlib.sha256(key.encode()).hexdigest()):
            raise c.ApiError(401, 'Valid sensor device key required')
        sr, sensor = get(c, con, 'sensors', sensor_id)
        if 'unit' in sensor and unit != sensor['unit']:
            raise c.ApiError(400, 'Unit must match the registered sensor unit')
        previous = con.execute('SELECT * FROM readings WHERE sensor_id=? AND client_id=?', (sensor_id, client_id)).fetchone()
        if previous:
            return 200, dict(previous)
        record = {'id': str(uuid.uuid4()), 'sensor_id': sensor_id, 'client_id': client_id,
                  'at': observed, 'value': value, 'unit': unit, 'received': time.time()}
        con.execute('INSERT INTO readings VALUES (?,?,?,?,?,?,?)', tuple(record.values()))
        if observed >= sensor.get('lastReadingAt', 0):
            sensor.update(value=f'{value:g} {unit}', lastReadingAt=observed, unit=unit)
            sensor['status'] = 'Critical' if value >= sensor.get('criticalAbove', float('inf')) else 'Warning' if value >= sensor.get('warningAbove', float('inf')) else 'Online'
            if 'battery' in data:
                sensor['battery'] = c.number(data, 'battery', 0, 100)
            save(con, 'sensors', sensor, sr['owner'], 'device:' + sensor_id)
        return 201, record
