import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import server


class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        server.DB = Path(cls.directory.name) / 'test.sqlite3'
        server.initialize()
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.http.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        cls.directory.cleanup()

    def call(self, method, path, data=None, token=''):
        req = urllib.request.Request(self.base + path, method=method,
              data=json.dumps(data).encode() if data is not None else None,
              headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.loads(response.read())

    def account(self, suffix, role='citizen'):
        credentials = {'email': suffix + '@example.com', 'password': 'test-password-123'}
        if role == 'authority':
            server.create_user(credentials, role)
        else:
            code, user = self.call('POST', '/api/auth/register', dict(credentials, role='authority'))
            self.assertEqual(code, 201)
            self.assertEqual(user['role'], 'citizen')
        code, session = self.call('POST', '/api/auth/login', credentials)
        self.assertEqual(code, 200)
        return session['token']

    def report(self, client='offline-1'):
        return {'clientId': client, 'incident': 'Road Blockage', 'location': 'Test location',
                'lat': 25.297, 'lng': 91.582, 'severity': 'High', 'description': 'Test report'}

    def test_health_and_protected_endpoints(self):
        self.assertEqual(self.call('GET', '/health')[0], 200)
        self.assertEqual(self.call('GET', '/api/reports')[0], 401)
        self.assertEqual(self.call('POST', '/api/auth/register', {'email': 'a@b', 'password': 'short'})[0], 400)
        self.assertEqual(self.call('POST', '/api/auth/login', {'email': 'missing@b', 'password': 'bad'})[0], 401)

    def test_report_retry_privacy_verification_and_logout(self):
        citizen = self.account('reporter')
        other = self.account('other')
        authority = self.account('official', 'authority')
        code, report = self.call('POST', '/api/reports', self.report(), citizen)
        self.assertEqual(code, 201)
        self.assertEqual(report['status'], 'Awaiting Verification')
        code, duplicate = self.call('POST', '/api/reports', self.report(), citizen)
        self.assertEqual(code, 200)
        self.assertEqual(duplicate['id'], report['id'])
        path = '/api/reports/' + report['id']
        self.assertEqual(self.call('GET', path, token=other)[0], 404)
        self.assertEqual(self.call('PATCH', path, {'status': 'Verified'}, citizen)[0], 403)
        self.assertEqual(self.call('PATCH', path, {'status': 'Verified'}, authority)[1]['status'], 'Verified')
        self.assertEqual(self.call('PATCH', path, {'status': 'Invented'}, authority)[0], 400)
        self.assertEqual(self.call('PATCH', path, {'ownerId': 'other'}, authority)[0], 400)
        server.initialize()  # Reopening the database must not erase records.
        self.assertEqual(self.call('GET', path, token=citizen)[1]['status'], 'Verified')
        self.assertEqual(self.call('POST', '/api/auth/logout', {}, citizen)[0], 200)
        self.assertEqual(self.call('GET', path, token=citizen)[0], 401)

    def test_validation_and_authority_collections(self):
        citizen = self.account('validation')
        authority = self.account('manager', 'authority')
        for invalid in [dict(self.report(), lat=100), dict(self.report(), lng=float('nan')),
                        dict(self.report(), severity='Extreme'), dict(self.report(), clientId='')]:
            self.assertEqual(self.call('POST', '/api/reports', invalid, citizen)[0], 400)
        fixtures = {
            'locations': {'name': 'Test slope', 'district': 'Test', 'state': 'Meghalaya',
                          'lat': 25, 'lng': 91, 'level': 'Low', 'score': 10},
            'sensors': {'location': 'Test slope', 'type': 'Soil Moisture', 'value': '40%', 'status': 'Online', 'battery': 90},
            'roads': {'name': 'Test road', 'route': 'A to B', 'district': 'Test', 'status': 'Open'},
            'alerts': {'type': 'TEST', 'location': 'Test slope', 'description': 'Exercise only', 'action': 'Review', 'severity': 'Low'},
            'teams': {'name': 'Test team', 'status': 'Available'},
        }
        for kind, data in fixtures.items():
            path = '/api/' + kind
            self.assertEqual(self.call('POST', path, data, citizen)[0], 403)
            code, record = self.call('POST', path, data, authority)
            self.assertEqual(code, 201)
            self.assertEqual(self.call('GET', path + '/' + record['id'], token=citizen)[0], 200)
        self.assertEqual(self.call('PATCH', '/api/teams/' + record['id'], {'status': 'Deployed'}, authority)[0], 200)

    def test_concurrent_offline_retries(self):
        token = self.account('concurrent')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.call('POST', '/api/reports', self.report('same'), token), range(4)))
        self.assertTrue(all(status in (200, 201) for status, _ in results))
        self.assertEqual(len({body['id'] for _, body in results}), 1)

    def test_invalid_body(self):
        self.assertEqual(self.call('POST', '/api/auth/register', [1, 2])[0], 400)


if __name__ == '__main__':
    unittest.main()
