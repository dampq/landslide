import base64
import csv
import io
import json
import os
import tempfile
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import domain
import providers
import risk_engine
import server
import train_model
import worker


class PlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        server.DB = Path(cls.directory.name) / 'platform.sqlite3'
        server.initialize()
        cls.tokens = {}
        cls.users = {}
        for role, email in [('authority', 'admin@test.org'), ('citizen', 'alice@test.org'), ('other', 'bob@test.org')]:
            credentials = {'email': email, 'password': 'testing-password-123'}
            cls.users[role] = server.create_user(credentials, 'authority' if role == 'authority' else 'citizen')
            cls.tokens[role] = server.dispatch('POST', '/api/auth/login', credentials)[1]['token']

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.env = patch.dict(os.environ, {'MODEL_PATH': '', 'NOTIFICATION_MODE': 'dry-run', 'VISION_ENDPOINT': ''})
        self.env.start()
        self.addCleanup(self.env.stop)

    def call(self, method, path, data=None, role='authority', query=None):
        try:
            return server.dispatch(method, path, data or {}, self.tokens[role], query)
        except server.ApiError as exc:
            return exc.status, {'error': exc.message}

    def location(self):
        code, record = self.call('POST', '/api/locations', {'name': 'Test ' + str(uuid.uuid4()), 'state': 'Meghalaya',
                      'district': 'East Khasi Hills', 'lat': 25.297, 'lng': 91.582, 'level': 'Low',
                      'slope': 40, 'historicalEvents': 4, 'population': 1000, 'hospitalDistanceKm': 10})
        self.assertEqual(code, 201)
        return record

    def report(self):
        code, record = self.call('POST', '/api/reports', {'clientId': str(uuid.uuid4()), 'incident': 'Ground Crack',
               'location': 'Private test location', 'lat': 25.3, 'lng': 91.5, 'description': 'Private notes', 'severity': 'High'}, 'citizen')
        self.assertEqual(code, 201)
        return record

    def sensor(self, location, feature=None, unit=None):
        data = {'locationId': location['id'], 'location': location['name'], 'type': 'Test', 'value': '0', 'status': 'Online', 'battery': 90}
        if feature:
            data.update(feature=feature, unit=unit)
        sensor = self.call('POST', '/api/sensors', data)[1]
        key = self.call('POST', f"/api/sensors/{sensor['id']}/key")[1]['deviceKey']
        return sensor, key

    def weather(self):
        start = int(time.time() // 3600) * 3600
        times = [start + h * 3600 for h in range(-80, 74)]
        return {'hourly': {'time': times, 'precipitation': [1.0] * len(times)}, 'hourly_units': {'precipitation': 'mm'}}

    def inputs(self):
        return {'rainfall24h': 180, 'rainfall72h': 450, 'soilMoisture': 90,
                'slope': 55, 'groundMovement': 8, 'historicalEvents': 15}

    def test_media_upload_deduplication_privacy_and_signature(self):
        report = self.report()
        payload = {'filename': 'photo.png', 'base64': base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'example data').decode()}
        path = f"/api/reports/{report['id']}/media"
        code, media = self.call('POST', path, payload, 'citizen')
        self.assertEqual(code, 201)
        self.assertEqual(self.call('POST', path, payload, 'citizen')[0], 200)
        self.assertEqual(self.call('GET', '/api/media/' + media['id'], role='other')[0], 404)
        self.assertEqual(self.call('GET', '/api/media/' + media['id'], role='citizen')[1]['base64'], payload['base64'])
        self.assertEqual(self.call('POST', path, dict(payload, filename='../x'), 'citizen')[0], 400)
        self.assertEqual(self.call('POST', path, dict(payload, base64=base64.b64encode(b'<html>bad file</html>').decode()), 'citizen')[0], 415)
        self.assertEqual(self.call('POST', '/api/media/' + media['id'] + '/analyze')[0], 503)
        with patch.dict(os.environ, {'VISION_ENDPOINT': 'https://vision.example.test'}), patch.object(providers, 'analyze_image', return_value={'labels': ['ground crack']}):
            self.assertEqual(self.call('POST', '/api/media/' + media['id'] + '/analyze')[0], 201)

    def test_telemetry_key_rotation_and_out_of_order_readings(self):
        sensor, key = self.sensor(self.location(), 'soilMoisture', '%')
        reading = {'sensorId': sensor['id'], 'clientId': 'r1', 'observedAt': time.time(), 'value': 70, 'unit': '%'}
        self.assertEqual(server.dispatch('POST', '/api/telemetry', reading, key)[0], 201)
        self.assertEqual(server.dispatch('POST', '/api/telemetry', reading, key)[0], 200)
        old = dict(reading, clientId='old', observedAt=time.time() - 1000, value=10)
        server.dispatch('POST', '/api/telemetry', old, key)
        self.assertEqual(self.call('GET', '/api/sensors/' + sensor['id'])[1]['value'], '70 %')
        self.assertEqual(len(self.call('GET', '/api/sensors/' + sensor['id'] + '/readings')[1]['items']), 2)
        self.call('POST', '/api/sensors/' + sensor['id'] + '/key')
        with self.assertRaises(server.ApiError) as error:
            server.dispatch('POST', '/api/telemetry', dict(reading, clientId='r2'), key)
        self.assertEqual(error.exception.status, 401)

    def test_weather_cache_forecast_and_provider_failure(self):
        location = self.location()
        path = '/api/weather/' + location['id']
        self.assertEqual(self.call('GET', path)[0], 404)
        with patch.object(providers, 'weather', return_value=self.weather()):
            code, result = self.call('POST', path + '/refresh')
        self.assertEqual(code, 200)
        self.assertEqual(result['rainfall24h'], 24)
        self.assertEqual(result['rainfall72h'], 72)
        with patch.object(providers, 'weather', side_effect=TimeoutError()):
            self.assertEqual(self.call('POST', path + '/refresh')[0], 502)
        self.assertEqual(self.call('GET', path)[1]['rainfall24h'], 24)
        code, result = self.call('POST', '/api/forecast/' + location['id'], {'inputs': self.inputs(), 'observedAt': time.time()})
        self.assertEqual(code, 201)
        self.assertEqual([s['horizonHours'] for s in result['scenarios']], [6, 12, 24, 48])
        with server.connect() as con:
            con.execute('UPDATE weather_cache SET at=0 WHERE location_id=?', (location['id'],))
        self.assertTrue(self.call('GET', path)[1]['stale'])
        self.assertEqual(self.call('POST', '/api/forecast/' + location['id'], {'inputs': self.inputs(), 'observedAt': time.time()})[0], 409)

    def test_risk_review_publish_and_notification_preferences(self):
        location = self.location()
        data = {'locationId': location['id'], 'inputs': self.inputs(), 'observedAt': time.time(), 'source': 'test'}
        code, prediction = self.call('POST', '/api/predictions', data)
        self.assertEqual(code, 201)
        self.assertIsNone(prediction['probability'])
        self.assertFalse(prediction['operationallyValidated'])
        self.assertEqual(self.call('POST', '/api/predictions', data, 'citizen')[0], 403)
        self.call('POST', '/api/predictions', data)
        alerts = self.call('GET', '/api/alerts', query={'locationId': location['id']})[1]['items']
        self.assertEqual(len(alerts), 1)
        path = '/api/alerts/' + alerts[0]['id']
        self.assertEqual(self.call('POST', path + '/publish')[0], 409)
        self.assertEqual(self.call('POST', path + '/approve', {'note': 'Test exercise approved'})[0], 200)
        self.call('PATCH', '/api/settings', {'sms': True, 'phone': '+919876543210', 'language': 'hi'}, 'citizen')
        self.assertGreater(self.call('POST', path + '/publish')[1]['queued'], 0)
        self.assertEqual(self.call('POST', path + '/publish')[1]['queued'], 0)
        notices = self.call('GET', '/api/notifications', role='citizen')[1]['items']
        mine = [n for n in notices if n['alert_id'] == alerts[0]['id']]
        self.assertEqual({n['status'] for n in mine}, {'delivered', 'dry-run'})
        self.assertEqual(self.call('POST', '/api/notifications/' + mine[0]['id'] + '/read', role='other')[0], 404)
        self.assertEqual(self.call('POST', path + '/resolve')[0], 200)
        self.assertEqual(self.call('POST', path + '/publish')[0], 409)

    def test_concurrent_deployment_and_state_transitions(self):
        location = self.location()
        team = self.call('POST', '/api/teams', {'name': 'Concurrent team', 'status': 'Available'})[1]
        payload = {'teamId': team['id'], 'locationId': location['id'], 'notes': 'Test deployment'}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.call('POST', '/api/deployments', payload), range(2)))
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        deployment = next(record for status, record in results if status == 201)
        path = '/api/deployments/' + deployment['id'] + '/status'
        self.assertEqual(self.call('POST', path, {'status': 'Completed'})[0], 409)
        self.assertEqual(self.call('PATCH', '/api/teams/' + team['id'], {'status': 'Available'})[0], 409)
        self.assertEqual(self.call('POST', path, {'status': 'On Site'})[0], 200)
        self.assertEqual(self.call('POST', path, {'status': 'Completed'})[0], 200)
        self.assertEqual(self.call('GET', '/api/teams/' + team['id'])[1]['status'], 'Available')

    def test_sync_privacy_partial_upload_and_pagination(self):
        report = self.report()
        data = {'reports': [dict(report, clientId=str(uuid.uuid4())), {'bad': True}]}
        results = self.call('POST', '/api/sync', data, 'citizen')[1]['results']
        self.assertEqual([r['status'] for r in results], [201, 400])
        foreign = self.call('GET', '/api/sync', role='other', query={'limit': '500'})[1]
        self.assertFalse(any(r['kind'] in {'reports', 'imageAnalyses', 'deployments'} for r in foreign['items']))
        self.assertEqual(self.call('GET', '/api/audit', role='citizen')[0], 403)
        page = self.call('GET', '/api/reports', role='citizen', query={'limit': '1'})[1]
        self.assertEqual(len(page['items']), 1)
        self.assertGreaterEqual(page['total'], 2)
        self.assertEqual(self.call('GET', '/api/reports', query={'limit': '-1'})[0], 400)

    def test_gis_import_analytics_and_priorities(self):
        location = self.location()
        data = {'collection': 'history', 'items': [{'name': 'Test past event', 'lat': 25.3, 'lng': 91.5,
                'observedAt': time.time() - 86400, 'source': 'test', 'locationId': location['id']}, {'bad': 1}]}
        self.assertEqual([r['status'] for r in self.call('POST', '/api/import', data)[1]['results']], [201, 400])
        self.call('POST', '/api/predictions', {'locationId': location['id'], 'inputs': self.inputs(), 'observedAt': time.time(), 'source': 'test'})
        geo = self.call('GET', '/api/gis', query={'bbox': '91,25,92,26'})[1]
        self.assertEqual(geo['type'], 'FeatureCollection')
        self.assertTrue(any(p['id'] == location['id'] for p in geo['features']))
        self.assertEqual(self.call('GET', '/api/gis', query={'bbox': 'broken'})[0], 400)
        self.assertTrue(self.call('GET', '/api/analytics')[1]['historicalEventsByMonth'])
        self.assertTrue(self.call('GET', '/api/response/priorities')[1]['items'])
        self.assertEqual(self.call('GET', '/api/dashboard')[0], 200)

    def test_worker_requires_complete_fresh_inputs(self):
        location = self.location()
        with self.assertRaises(ValueError):
            worker.monitoring_inputs(location['id'])
        with patch.object(providers, 'weather', return_value=self.weather()):
            domain.refresh_weather(server, location['id'])
        for feature, unit, value in [('soilMoisture', '%', 80), ('groundMovement', 'mm/h', 4)]:
            sensor, key = self.sensor(location, feature, unit)
            server.dispatch('POST', '/api/telemetry', {'sensorId': sensor['id'], 'clientId': 'sample',
                            'observedAt': time.time(), 'value': value, 'unit': unit}, key)
        inputs, observed = worker.monitoring_inputs(location['id'])
        self.assertEqual(inputs['soilMoisture'], 80)
        self.assertEqual(inputs['rainfall72h'], 72)
        self.assertGreater(observed, time.time() - 60)

    def test_provider_delivery_uncertainty_does_not_auto_retry(self):
        self.call('PATCH', '/api/settings', {'sms': True, 'phone': '+919876543210'})
        alert = self.call('POST', '/api/alerts', {'type': 'TEST', 'location': 'Test', 'description': 'Test only', 'action': 'Review', 'severity': 'Low'})[1]
        uid = str(uuid.uuid4())
        with server.connect() as con:
            con.execute("INSERT INTO notifications(id,alert_id,user_id,channel,body,destination,status) VALUES (?,?,?,?,?,?,'pending')", (uid, alert['id'], self.users['authority']['id'], 'sms', 'test', '+919876543210'))
        with patch.dict(os.environ, {'NOTIFICATION_MODE': 'live'}), patch.object(providers, 'send_sms', side_effect=TimeoutError()) as sender:
            domain.process_notifications(server)
            domain.process_notifications(server)
            self.assertEqual(sender.call_count, 1)
        with server.connect() as con:
            self.assertEqual(con.execute('SELECT status FROM notifications WHERE id=?', (uid,)).fetchone()[0], 'unknown')

    def test_notification_cancellation_and_confirmed_delivery(self):
        alert = self.call('POST', '/api/alerts', {'type': 'TEST', 'location': 'Test', 'description': 'Test', 'action': 'Review', 'severity': 'Low'})[1]
        self.call('PATCH', '/api/settings', {'sms': True, 'phone': '+919876543210'})
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        with server.connect() as con:
            con.execute("INSERT INTO notifications(id,alert_id,user_id,channel,body,destination,status) VALUES (?,?,?,?,?,?,'pending')", (ids[0], alert['id'], self.users['authority']['id'], 'sms', 'test', '+919876543210'))
        with patch.dict(os.environ, {'NOTIFICATION_MODE': 'live'}), patch.object(providers, 'send_sms', return_value={'sid': 'SM123'}), patch.object(providers, 'message_status', return_value={'status': 'delivered'}):
            domain.process_notifications(server)
        with server.connect() as con:
            self.assertEqual(con.execute('SELECT status FROM notifications WHERE id=?', (ids[0],)).fetchone()[0], 'delivered')
            con.execute("INSERT INTO notifications(id,alert_id,user_id,channel,body,destination,status) VALUES (?,?,?,?,?,?,'pending')", (ids[1], alert['id'], self.users['other']['id'], 'sms', 'test', '+919876543210'))
        with patch.dict(os.environ, {'NOTIFICATION_MODE': 'live'}), patch.object(providers, 'send_sms') as sender:
            domain.process_notifications(server)
            sender.assert_not_called()
        with server.connect() as con:
            self.assertEqual(con.execute('SELECT status FROM notifications WHERE id=?', (ids[1],)).fetchone()[0], 'cancelled')

    def test_password_change_revokes_every_session(self):
        credentials = {'email': 'password-test@example.org', 'password': 'old-password-123'}
        server.create_user(credentials)
        tokens = [server.dispatch('POST', '/api/auth/login', credentials)[1]['token'] for _ in range(2)]
        result = server.dispatch('POST', '/api/auth/password', {'currentPassword': credentials['password'], 'newPassword': 'new-password-456'}, tokens[0])
        self.assertEqual(result[0], 200)
        for token in tokens:
            with self.assertRaises(server.ApiError):
                server.authenticate(token)
        self.assertEqual(server.dispatch('POST', '/api/auth/login', dict(credentials, password='new-password-456'))[0], 200)

    def test_training_pipeline_and_loaded_model(self):
        dataset = Path(self.directory.name) / 'training.csv'
        model = Path(self.directory.name) / 'model.json'
        with dataset.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=risk_engine.FEATURES + ['landslideOccurred'])
            writer.writeheader()
            for i in range(40):
                high = i >= 20
                writer.writerow(dict(zip(risk_engine.FEATURES, [180, 450, 90, 55, 8, 15] if high else [10, 20, 20, 10, 0, 0]), landslideOccurred=int(high)))
        metrics = train_model.train(dataset, model, epochs=100)
        self.assertEqual(metrics['heldoutCount'], 8)
        with patch.dict(os.environ, {'MODEL_PATH': str(model)}):
            result = risk_engine.assess(self.inputs())
        self.assertEqual(result['method'], 'trained-logistic')
        self.assertTrue(0 <= result['probability'] <= 1)
        self.assertFalse(result['operationallyValidated'])

    def test_wsgi_validation_cors_schema_and_rate_limit(self):
        import app
        def request(path, method='GET', raw=b'', extra=None):
            env = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'REMOTE_ADDR': 'wsgi-test', 'CONTENT_LENGTH': str(len(raw)),
                   'CONTENT_TYPE': 'application/json', 'wsgi.input': io.BytesIO(raw), 'HTTP_ORIGIN': 'http://localhost:5173'}
            env.update(extra or {})
            result = []
            body = b''.join(app.application(env, lambda status, headers: result.extend([status, dict(headers)])))
            return result, body
        response, _ = request('/health')
        self.assertTrue(response[0].startswith('200'))
        self.assertIn('Access-Control-Allow-Origin', response[1])
        response, body = request('/openapi.json')
        self.assertIn('/api/predictions', json.loads(body)['paths'])
        response, _ = request('/api/auth/register', 'POST', b'{"a":NaN}')
        self.assertTrue(response[0].startswith('400'))
        response, _ = request('/api/auth/register', 'POST', b'{}', {'CONTENT_LENGTH': '99999999'})
        self.assertTrue(response[0].startswith('413'))
        for _ in range(2):
            domain.rate_limit(server, 'test-quota', maximum=2)
        with self.assertRaises(server.ApiError) as error:
            domain.rate_limit(server, 'test-quota', maximum=2)
        self.assertEqual(error.exception.status, 429)


if __name__ == '__main__':
    unittest.main()
