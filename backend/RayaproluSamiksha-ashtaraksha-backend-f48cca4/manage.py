"""Local database maintenance, demo setup and authority account management."""
import argparse
import getpass
import json
import sqlite3
import time
from pathlib import Path

import server
import domain


def seed():
    with server.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        existing = con.execute("SELECT data FROM records WHERE kind='locations' AND json_extract(data,'$.demo')=1 LIMIT 1").fetchone()
        if existing:
            return {'message': 'Demo already seeded', 'location': json.loads(existing[0])}
        location = domain.insert(con, 'locations', {'name': 'DEMO - Mawsynram slope', 'district': 'East Khasi Hills',
             'state': 'Meghalaya', 'lat': 25.297, 'lng': 91.582, 'level': 'Moderate', 'score': 45,
             'population': 2450, 'hospitalDistanceKm': 8, 'slope': 42, 'demo': True,
             'source': 'Synthetic demonstration data, not live conditions'}, None, 'demo-seed')
        linked = {'locationId': location['id'], 'demo': True}
        domain.insert(con, 'roads', dict(linked, name='DEMO road', route='Test route', district='East Khasi Hills', status='Open'), None, 'demo-seed')
        domain.insert(con, 'sensors', dict(linked, location=location['name'], type='Soil Moisture', value='50 %', unit='%', status='Online', battery=100), None, 'demo-seed')
        domain.insert(con, 'teams', {'name': 'DEMO response team', 'status': 'Available', 'demo': True}, None, 'demo-seed')
        domain.insert(con, 'villages', dict(linked, name='DEMO village', lat=25.30, lng=91.59, population=2450), None, 'demo-seed')
        return {'location': location}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    account = sub.add_parser('create-authority')
    account.add_argument('email')
    sub.add_parser('seed-demo')
    backup = sub.add_parser('backup')
    backup.add_argument('destination')
    sub.add_parser('check')
    args = parser.parse_args()
    server.initialize()
    if args.command == 'create-authority':
        print(server.create_user({'email': args.email, 'password': getpass.getpass('Password (12+ characters): ')}, 'authority'))
    elif args.command == 'seed-demo':
        print(json.dumps(seed(), indent=2))
    elif args.command == 'backup':
        destination = Path(args.destination).resolve()
        if destination == server.DB.resolve() or destination.exists():
            parser.error('Choose a new backup destination, different from the live database')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with server.connect() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()
        print(f'Backup created: {destination}')
    else:
        with server.connect() as con:
            print({'integrity': con.execute('PRAGMA integrity_check').fetchone()[0], 'checkedAt': time.time()})
