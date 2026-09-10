"""Machine-readable API contract, importable into Postman or Swagger tooling."""
import re


def schema():
    paths = {}
    def add(path, method, summary, required=None, public=False, properties=None):
        operation = {'summary': summary, 'operationId': method + '_' + re.sub(r'[^a-zA-Z0-9]+', '_', path).strip('_'),
                     'security': [] if public else [{'bearerAuth': []}],
                     'responses': {'200': {'description': 'Success'}, '201': {'description': 'Created'},
                                   '400': {'description': 'Invalid input'}, '401': {'description': 'Authentication required'},
                                   '403': {'description': 'Insufficient role'}, '404': {'description': 'Not found'},
                                   '409': {'description': 'Conflict or stale data'}, '429': {'description': 'Rate limited'}}}
        parameters = [{'name': name, 'in': 'path', 'required': True, 'schema': {'type': 'string'}} for name in re.findall(r'{(.*?)}', path)]
        if method == 'get':
            parameters += [{'name': 'limit', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 500}},
                           {'name': 'offset', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 0}}]
        if parameters:
            operation['parameters'] = parameters
        if method in {'post', 'patch'}:
            operation['requestBody'] = {'required': bool(required), 'content': {'application/json': {'schema': {
                'type': 'object', 'properties': properties or {}, **({'required': required} if required else {})}}}}
        paths.setdefault(path, {})[method] = operation

    add('/health', 'get', 'Database health', public=True)
    for route in ['register', 'login']:
        add('/api/auth/' + route, 'post', route.title(), ['email', 'password'], True,
            {'email': {'type': 'string'}, 'password': {'type': 'string', 'format': 'password'}})
    add('/api/auth/me', 'get', 'Current account')
    add('/api/auth/logout', 'post', 'Revoke current session')
    add('/api/auth/password', 'post', 'Change password and revoke all sessions', ['currentPassword', 'newPassword'])
    required = {
        'reports': ['clientId', 'incident', 'location', 'lat', 'lng', 'severity', 'description'],
        'locations': ['name', 'district', 'state', 'lat', 'lng', 'level'],
        'sensors': ['location', 'type', 'value', 'status', 'battery'],
        'roads': ['name', 'route', 'district', 'status'],
        'alerts': ['type', 'location', 'description', 'action', 'severity'],
        'teams': ['name', 'status'], 'villages': ['name', 'lat', 'lng'],
        'infrastructure': ['name', 'type', 'lat', 'lng'],
        'history': ['name', 'lat', 'lng', 'observedAt', 'source'],
        'satellite': ['name', 'lat', 'lng', 'observedAt', 'source'],
    }
    for kind, fields in required.items():
        add('/api/' + kind, 'get', 'List ' + kind)
        add('/api/' + kind, 'post', 'Create ' + kind + (' (citizen or authority)' if kind == 'reports' else ' (authority)'), fields)
        add('/api/' + kind + '/{id}', 'get', 'Read ' + kind)
        add('/api/' + kind + '/{id}', 'patch', 'Update ' + kind + ' (authority)')
    for kind in ['predictions', 'forecasts', 'deployments', 'imageAnalyses']:
        add('/api/' + kind, 'get', 'List ' + kind)
        add('/api/' + kind + '/{id}', 'get', 'Read ' + kind)
    for path, summary, fields in [
        ('/api/predictions', 'Evaluate current risk and create review alerts (authority)', ['locationId', 'inputs', 'observedAt', 'source']),
        ('/api/forecast/{locationId}', 'Weather-linked screening scenarios (authority)', ['inputs', 'observedAt']),
        ('/api/telemetry', 'Ingest reading; Bearer token must be the sensor device key', ['sensorId', 'clientId', 'observedAt', 'value', 'unit']),
        ('/api/sensors/{id}/key', 'Rotate sensor key (authority)', []),
        ('/api/weather/{id}/refresh', 'Fetch and cache weather (authority)', []),
        ('/api/reports/{id}/media', 'Upload media as base64 JSON', ['filename', 'base64']),
        ('/api/media/{id}/analyze', 'Configured vision provider (authority)', []),
        ('/api/alerts/{id}/approve', 'Approve screening notice (authority)', ['note']),
        ('/api/alerts/{id}/publish', 'Queue subscribed notifications (authority)', []),
        ('/api/alerts/{id}/acknowledge', 'Acknowledge alert (authority)', []),
        ('/api/alerts/{id}/resolve', 'Resolve alert (authority)', []),
        ('/api/notifications/{id}/read', 'Mark own notification read', []),
        ('/api/notifications/{id}/retry', 'Requeue uncertain SMS after provider check (authority)', ['providerChecked']),
        ('/api/deployments', 'Assign an available team (authority)', ['teamId', 'locationId', 'notes']),
        ('/api/deployments/{id}/status', 'Advance deployment (authority)', ['status']),
        ('/api/import', 'Partial-success batch import (authority)', ['collection', 'items']),
        ('/api/sync', 'Upload offline reports with per-item results', ['reports'])]:
        add(path, 'post', summary, fields)
    for path in ['/api/sensors/{id}/readings', '/api/weather/{id}', '/api/reports/{id}/media', '/api/media/{id}',
                 '/api/notifications', '/api/response/priorities', '/api/settings', '/api/dashboard', '/api/analytics',
                 '/api/gis', '/api/sync', '/api/audit', '/api/system']:
        add(path, 'get', path.rsplit('/', 1)[-1])
    add('/api/settings', 'patch', 'Set language and notification subscriptions')
    for path in ['/api/sync', '/api/audit']:
        paths[path]['get']['parameters'].append({'name': 'cursor', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 0}})
    paths['/api/gis']['get']['parameters'].append({'name': 'bbox', 'in': 'query', 'schema': {'type': 'string'}, 'description': 'west,south,east,north'})
    return {'openapi': '3.0.3', 'info': {'title': 'Ashtaraksha Backend', 'version': '2.0.0',
            'description': 'Independent backend. Screening values are not validated landslide warnings. See README.md for field definitions and integration limits.'},
            'servers': [{'url': 'http://127.0.0.1:8000'}], 'paths': paths,
            'components': {'securitySchemes': {'bearerAuth': {'type': 'http', 'scheme': 'bearer'}}}}
