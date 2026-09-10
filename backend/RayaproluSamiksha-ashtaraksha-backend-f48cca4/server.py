"""Standalone Ashtaraksha API. See app.py for the production WSGI entry point."""
import argparse
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
import sys
import logging
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import config
import domain

DB = Path(os.environ.get('DATABASE_PATH', Path(__file__).with_name('backend.sqlite3')))
if not DB.is_absolute():
    DB = Path(__file__).parent / DB
LEVELS = {'Low', 'Moderate', 'High', 'Critical'}
COLLECTIONS = {'locations', 'sensors', 'roads', 'alerts', 'teams', 'villages', 'infrastructure',
               'history', 'satellite', 'predictions', 'forecasts', 'deployments', 'imageAnalyses'}
READ_ONLY = {'predictions', 'forecasts', 'deployments', 'imageAnalyses'}


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


@contextmanager
def connect():
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        with con:
            yield con
    finally:
        con.close()


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS users (
          id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL,
          password TEXT NOT NULL, role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), expires REAL);
        CREATE TABLE IF NOT EXISTS records (
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner TEXT REFERENCES users(id),
          client_id TEXT, data TEXT NOT NULL, UNIQUE(kind, owner, client_id));
        CREATE INDEX IF NOT EXISTS records_kind ON records(kind);
        ''')
        con.executescript(domain.SCHEMA)
        # One-time migration: existing foundation records also participate in sync.
        for row in con.execute('SELECT * FROM records WHERE NOT EXISTS (SELECT 1 FROM events WHERE events.record_id=records.id)').fetchall():
            domain.event(con, row['kind'], json.loads(row['data']), row['owner'], 'migration', 'created')


def required(data, name, limit=2000):
    value = data.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ApiError(400, f'{name} must be a nonempty string of at most {limit} characters')
    return value.strip()


def number(data, name, low, high):
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise ApiError(400, f'{name} must be between {low} and {high}')
    return value


def validate(kind, data):
    domain.validate_extra(sys.modules[__name__], kind, data)
    if kind == 'reports':
        for key in ['incident', 'location', 'description']:
            required(data, key)
        number(data, 'lat', -90, 90)
        number(data, 'lng', -180, 180)
        if data.get('severity') not in LEVELS:
            raise ApiError(400, 'Invalid severity')
    elif kind == 'locations':
        for key in ['name', 'district', 'state']:
            required(data, key)
        number(data, 'lat', -90, 90)
        number(data, 'lng', -180, 180)
        if 'score' in data:
            number(data, 'score', 0, 100)
        if data.get('level') not in LEVELS:
            raise ApiError(400, 'Invalid level')
    elif kind == 'sensors':
        for key in ['location', 'type', 'value', 'status']:
            required(data, key)
        number(data, 'battery', 0, 100)
    elif kind == 'roads':
        for key in ['name', 'route', 'district']:
            required(data, key)
        if data.get('status') not in {'Open', 'Partially Blocked', 'Blocked', 'Under Verification'}:
            raise ApiError(400, 'Invalid road status')
    elif kind == 'alerts':
        for key in ['type', 'location', 'description', 'action']:
            required(data, key)
        if data.get('severity') not in LEVELS:
            raise ApiError(400, 'Invalid severity')
    elif kind == 'teams':
        required(data, 'name')
        if data.get('status') not in {'Available', 'Deployed', 'En Route'}:
            raise ApiError(400, 'Invalid team status')


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def create_user(data, role='citizen'):
    email = required(data, 'email', 254).lower()
    if '@' not in email:
        raise ApiError(400, 'Invalid email')
    password = required(data, 'password', 256)
    if len(password) < 12:
        raise ApiError(400, 'Use a password of at least 12 characters')
    salt, uid = secrets.token_hex(16), str(uuid.uuid4())
    with connect() as con:
        try:
            con.execute('INSERT INTO users VALUES (?,?,?,?,?)',
                        (uid, email, salt, password_hash(password, salt), role))
        except sqlite3.IntegrityError:
            raise ApiError(409, 'Email already registered')
    return {'id': uid, 'email': email, 'role': role}


def authenticate(token):
    with connect() as con:
        row = con.execute('SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id '
                          'WHERE token=? AND expires>?',
                          (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
    if row is None:
        raise ApiError(401, 'A valid Bearer token is required')
    return dict(row)


def dispatch(method, path, data, token='', query=None):
    core = sys.modules[__name__]
    query = query or {}
    if method == 'GET' and path == '/health':
        with connect() as con:
            con.execute('SELECT 1').fetchone()
        return 200, {'status': 'ok', 'service': 'ashtaraksha', 'version': '2.0.0'}
    if method == 'GET' and path == '/openapi.json':
        from api_schema import schema
        return 200, schema()
    if method == 'POST' and path == '/api/telemetry':
        return domain.telemetry(core, data, token)
    if method == 'POST' and path == '/api/auth/register':
        return 201, create_user(data)
    if method == 'POST' and path == '/api/auth/login':
        email, password = required(data, 'email', 254).lower(), required(data, 'password', 256)
        with connect() as con:
            row = con.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            salt = row['salt'] if row else '00' * 16
            candidate = password_hash(password, salt)
            if row is None or not hmac.compare_digest(candidate, row['password']):
                raise ApiError(401, 'Invalid credentials')
            token = secrets.token_urlsafe(32)
            con.execute('DELETE FROM sessions WHERE expires<=?', (time.time(),))
            con.execute('INSERT INTO sessions VALUES (?,?,?)',
                        (hashlib.sha256(token.encode()).hexdigest(), row['id'], time.time()+86400))
        return 200, {'token': token, 'expiresIn': 86400, 'role': row['role']}
    user = authenticate(token)
    if method == 'POST' and path == '/api/auth/logout':
        with connect() as con:
            con.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(token.encode()).hexdigest(),))
        return 200, {'loggedOut': True}
    if method == 'GET' and path == '/api/auth/me':
        return 200, {key: user[key] for key in ['id', 'email', 'role']}
    result = domain.routes(core, method, path, data, user, query, token)
    if result is not None:
        return result
    parts = path.strip('/').split('/')
    if len(parts) not in (2, 3) or parts[0] != 'api' or parts[1] not in COLLECTIONS | {'reports'}:
        raise ApiError(404, 'Endpoint not found')
    kind = parts[1]
    rid = parts[2] if len(parts) == 3 else None
    if kind in {'deployments', 'imageAnalyses'}:
        domain.authority(core, user)
    with connect() as con:
        if method == 'GET':
            if not rid:
                return 200, domain.list_records(core, con, kind, user, query)
            rows = con.execute('SELECT * FROM records WHERE kind=? ORDER BY rowid DESC', (kind,)).fetchall()
            items = [json.loads(r['data']) for r in rows
                     if (not rid or r['id'] == rid)
                     and (kind != 'reports' or user['role'] == 'authority' or r['owner'] == user['id'])]
            if rid and not items:
                raise ApiError(404, 'Record not found')
            return 200, items[0] if rid else {'items': items, 'total': len(items)}
        if user['role'] != 'authority' and not (kind == 'reports' and method == 'POST' and not rid):
            raise ApiError(403, 'Authority role required')
        if kind in READ_ONLY:
            raise ApiError(405, 'Use the dedicated workflow endpoint to create or update this resource')
        if method == 'POST' and not rid:
            validate(kind, data)
            domain.validate_links(core, con, data)
            client_id = required(data, 'clientId', 128) if kind == 'reports' else None
            # Stable client IDs allow a field device to retry after a lost response.
            if client_id:
                previous = con.execute('SELECT data FROM records WHERE kind=? AND owner=? AND client_id=?',
                                       (kind, user['id'], client_id)).fetchone()
                if previous:
                    return 200, json.loads(previous['data'])
            record = dict(data, id=str(uuid.uuid4()), updatedAt=time.time())
            if kind == 'reports':
                record.update(status='Awaiting Verification', reporter=user['role'], ownerId=user['id'])
            try:
                con.execute('INSERT INTO records VALUES (?,?,?,?,?)',
                            (record['id'], kind, user['id'], client_id, json.dumps(record)))
            except sqlite3.IntegrityError:
                previous = con.execute('SELECT data FROM records WHERE kind=? AND owner=? AND client_id=?',
                                       (kind, user['id'], client_id)).fetchone()
                if previous:
                    return 200, json.loads(previous['data'])
                raise
            domain.event(con, kind, record, user['id'], user['id'], 'created')
            return 201, record
        if method == 'PATCH' and rid:
            # Acquire a write lock before reading to avoid lost concurrent updates.
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT data FROM records WHERE id=? AND kind=?', (rid, kind)).fetchone()
            if row is None:
                raise ApiError(404, 'Record not found')
            record = json.loads(row['data'])
            protected = {'id', 'ownerId', 'clientId', 'reporter', 'updatedAt', 'approvedBy', 'approvedAt',
                         'reviewRequired', 'publishedAt', 'deploymentId', 'predictionId'}
            if protected.intersection(data):
                raise ApiError(400, 'Cannot modify server-owned fields')
            record.update(data)
            if kind == 'alerts' and record.get('reviewRequired') and set(data).intersection({'description', 'severity', 'action', 'location', 'translations'}):
                for field in ['approvedBy', 'approvedAt', 'approvalNote']:
                    record.pop(field, None)
            if kind == 'teams' and record.get('deploymentId') and 'status' in data:
                raise ApiError(409, 'Update the active deployment instead of the team status')
            validate(kind, record)
            domain.validate_links(core, con, record)
            if kind == 'reports' and record.get('status') not in {'Awaiting Verification', 'Verified', 'Rejected', 'Resolved'}:
                raise ApiError(400, 'Invalid report status')
            record['updatedAt'] = time.time()
            con.execute('UPDATE records SET data=? WHERE id=?', (json.dumps(record), rid))
            owner = con.execute('SELECT owner FROM records WHERE id=?', (rid,)).fetchone()[0]
            domain.event(con, kind, record, owner, user['id'], 'updated')
            return 200, record
    raise ApiError(405, 'Method not allowed')


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.respond(204, None)

    def respond(self, status, payload):
        body = json.dumps(payload).encode() if payload is not None else b''
        self.send_response(status)
        allowed = os.environ.get('CORS_ORIGIN', 'http://localhost:5173')
        if self.headers.get('Origin') == allowed:
            self.send_header('Access-Control-Allow-Origin', allowed)
        self.send_header('Vary', 'Origin')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_api(self):
        try:
            self.connection.settimeout(15)
            path = urlsplit(self.path)
            domain.rate_limit(sys.modules[__name__], self.client_address[0] + (':auth' if path.path in {'/api/auth/login', '/api/auth/register'} else ':api'),
                              20 if path.path in {'/api/auth/login', '/api/auth/register'} else 240)
            size = int(self.headers.get('Content-Length', '0'))
            maximum = 14_100_000 if path.path.endswith('/media') else 1_048_576
            if size < 0 or size > maximum:
                raise ApiError(413, 'Request body exceeds endpoint size limit')
            if size and self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                raise ApiError(415, 'Use application/json')
            raw = self.rfile.read(size) if size else b'{}'
            data = json.loads(raw, parse_constant=reject_constant)
            if not isinstance(data, dict):
                raise ApiError(400, 'Expected a JSON object')
            header = self.headers.get('Authorization', '')
            token = header[7:] if header.startswith('Bearer ') else ''
            query = {k: v[-1] for k, v in parse_qs(path.query).items()}
            status, payload = dispatch(self.command, path.path.rstrip('/') or '/', data, token, query)
            self.respond(status, payload)
        except ApiError as exc:
            self.respond(exc.status, {'error': exc.message})
        except (ValueError, UnicodeError):
            self.respond(400, {'error': 'Invalid JSON or Content-Length'})
        except Exception:
            logging.exception('Request failed')
            self.respond(500, {'error': 'Internal server error'})

    do_GET = do_POST = do_PATCH = handle_api


def reject_constant(value):
    raise ValueError('Nonfinite numbers are not valid JSON')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--create-authority', metavar='EMAIL')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    initialize()
    if args.create_authority:
        import getpass
        print(create_user({'email': args.create_authority, 'password': getpass.getpass('Password (12+ characters): ')}, 'authority'))
    else:
        print(f'Ashtaraksha backend: http://127.0.0.1:{args.port}', flush=True)
        ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
