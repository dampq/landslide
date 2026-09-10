"""Real Waitress subprocess smoke test using only a temporary database."""
import importlib.util
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path


class DeploymentTests(unittest.TestCase):
    def test_seed_and_database_backup(self):
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, DATABASE_PATH=str(Path(directory) / 'source.sqlite3'))
            command = [sys.executable, str(root / 'manage.py')]
            for _ in range(2):
                subprocess.run(command + ['seed-demo'], cwd=root, env=env, capture_output=True, check=True, timeout=15)
            backup = Path(directory) / 'backup.sqlite3'
            subprocess.run(command + ['backup', str(backup)], cwd=root, env=env, capture_output=True, check=True, timeout=15)
            connection = sqlite3.connect(backup)
            try:
                self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM records').fetchone()[0], 5)
            finally:
                connection.close()

    def test_waitress_startup_and_openapi(self):
        root = Path(__file__).resolve().parent
        if not (root / '.deps' / 'waitress').exists() and importlib.util.find_spec('waitress') is None:
            self.skipTest('Install requirements.txt to exercise Waitress')
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            env = dict(os.environ, DATABASE_PATH=str(Path(directory) / 'smoke.sqlite3'), NOTIFICATION_MODE='dry-run')
            process = subprocess.Popen([sys.executable, str(root / 'run.py'), '--port', str(port)],
                                       cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                for _ in range(100):
                    if process.poll() is not None:
                        self.fail(process.stderr.read().decode())
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as response:
                            result = json.load(response)
                        break
                    except OSError:
                        time.sleep(.1)
                else:
                    self.fail('Waitress did not become healthy')
                self.assertEqual(result['status'], 'ok')
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/openapi.json', timeout=3) as response:
                    document = json.load(response)
                self.assertIn('/api/reports/{id}/media', document['paths'])
            finally:
                process.terminate()
                process.communicate(timeout=10)
