"""Start a separate, unseeded local workspace; never delete the existing database."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from api.db import DATABASE_URL, wait_for_database


def main():
    source = make_url(DATABASE_URL)
    if source.host not in ('localhost', '127.0.0.1'):
        raise SystemExit('Clean startup supports the local development database only.')
    subprocess.run(['docker', 'compose', 'up', '-d', 'db'], cwd=ROOT, check=True)
    wait_for_database()
    # Connect to an existing database to create the clean sibling only if absent.
    with psycopg.connect(source.set(drivername='postgresql').render_as_string(hide_password=False),
                         autocommit=True) as connection:
        if not connection.execute('SELECT 1 FROM pg_database WHERE datname = %s',
                                  ('ashtaraksha_clean',)).fetchone():
            try:
                connection.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier('ashtaraksha_clean')))
            except psycopg.errors.DuplicateDatabase:
                pass
    env = {**os.environ, 'DATABASE_URL': source.set(database='ashtaraksha_clean').render_as_string(hide_password=False)}
    subprocess.run([sys.executable, 'manage.py', 'migrate'], cwd=ROOT / 'backend', env=env, check=True)
    print('Using ashtaraksha_clean: no demo seeding. Existing databases and user records are retained.', flush=True)
    os.chdir(ROOT)
    os.execvpe('npm', ['npm', 'run', 'dev:all'], env)


if __name__ == '__main__':
    main()
