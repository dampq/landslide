"""WSGI adapter shared by Waitress and the deployment image."""
import json
import logging
from http import HTTPStatus
from urllib.parse import parse_qs

import server
import domain

server.initialize()


def application(environ, start_response):
    origin = environ.get('HTTP_ORIGIN', '')
    headers = [('Content-Type', 'application/json; charset=utf-8'), ('Cache-Control', 'no-store'),
               ('X-Content-Type-Options', 'nosniff'), ('Vary', 'Origin')]
    if origin == server.os.environ.get('CORS_ORIGIN', 'http://localhost:5173'):
        headers.append(('Access-Control-Allow-Origin', origin))
    headers.extend([('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
                    ('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS')])
    try:
        method, path = environ['REQUEST_METHOD'], environ.get('PATH_INFO', '/').rstrip('/') or '/'
        if method == 'OPTIONS':
            status, result = 204, None
        else:
            auth = path in {'/api/auth/login', '/api/auth/register'}
            # Do not trust a caller-supplied X-Forwarded-For header.
            domain.rate_limit(server, environ.get('REMOTE_ADDR', 'local') + (':auth' if auth else ':api'), 20 if auth else 240)
            size = int(environ.get('CONTENT_LENGTH') or 0)
            maximum = 14_100_000 if path.endswith('/media') else 1_048_576
            if size < 0 or size > maximum:
                raise server.ApiError(413, 'Request body exceeds endpoint size limit')
            if size and environ.get('CONTENT_TYPE', '').split(';')[0].strip() != 'application/json':
                raise server.ApiError(415, 'Use application/json')
            raw = environ['wsgi.input'].read(size) if size else b'{}'
            data = json.loads(raw, parse_constant=server.reject_constant)
            if not isinstance(data, dict):
                raise server.ApiError(400, 'Expected a JSON object')
            header = environ.get('HTTP_AUTHORIZATION', '')
            token = header[7:] if header.startswith('Bearer ') else ''
            query = {k: v[-1] for k, v in parse_qs(environ.get('QUERY_STRING', '')).items()}
            status, result = server.dispatch(method, path, data, token, query)
    except server.ApiError as exc:
        status, result = exc.status, {'error': exc.message}
    except (ValueError, UnicodeError):
        status, result = 400, {'error': 'Invalid JSON or Content-Length'}
    except Exception:
        logging.exception('API request failed')
        status, result = 500, {'error': 'Internal server error'}
    body = b'' if status == 204 else json.dumps(result, ensure_ascii=False, allow_nan=False).encode()
    headers.append(('Content-Length', str(len(body))))
    if status == 429:
        headers.append(('Retry-After', '60'))
    start_response(f'{status} {HTTPStatus(status).phrase}', headers)
    return [body]
