"""Run periodic weather refreshes and the notification outbox as a separate process."""
import argparse
import json
import time

import server
import domain


def run_once():
    output = {'weatherRefreshed': 0, 'weatherFailed': 0, 'predictionsCreated': 0, 'predictionsSkipped': 0}
    with server.connect() as con:
        locations = con.execute("SELECT id FROM records WHERE kind='locations'").fetchall()
    for location in locations:
        with server.connect() as con:
            row = con.execute('SELECT at FROM weather_cache WHERE location_id=?', (location['id'],)).fetchone()
        if not row or time.time() - row['at'] >= 3600:
            try:
                domain.refresh_weather(server, location['id'])
                output['weatherRefreshed'] += 1
            except server.ApiError:
                output['weatherFailed'] += 1
        try:
            inputs, observed = monitoring_inputs(location['id'])
            domain.prediction(server, {'locationId': location['id'], 'inputs': inputs, 'observedAt': observed,
                              'source': 'worker: fresh registered telemetry, weather model rain and supplied terrain/history'},
                              {'id': None, 'role': 'authority'})
            output['predictionsCreated'] += 1
        except (server.ApiError, ValueError):
            output['predictionsSkipped'] += 1
    output['notifications'] = domain.process_notifications(server)
    with server.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        for row in con.execute("SELECT * FROM records WHERE kind='sensors'").fetchall():
            sensor = json.loads(row['data'])
            if sensor.get('status') != 'Offline' and time.time() - sensor.get('lastReadingAt', sensor['updatedAt']) > 3600:
                sensor['status'] = 'Offline'
                domain.save(con, 'sensors', sensor, row['owner'], 'worker')
        con.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?)',
                    ('monitoring', time.time(), json.dumps(output)))
    return output


def monitoring_inputs(location_id):
    now = time.time()
    expected = {'rainfall24h': 'mm', 'rainfall72h': 'mm', 'soilMoisture': '%', 'slope': 'deg',
                'groundMovement': 'mm/h', 'historicalEvents': 'count'}
    with server.connect() as con:
        _, location = domain.get(server, con, 'locations', location_id)
        values = {key: location[key] for key in ['slope', 'historicalEvents'] if key in location}
        observed = []
        weather = con.execute('SELECT * FROM weather_cache WHERE location_id=?', (location_id,)).fetchone()
        if weather and now - weather['at'] < 3600:
            cached = json.loads(weather['data'])
            for key in ['rainfall24h', 'rainfall72h']:
                if cached.get(key) is not None:
                    values[key] = cached[key]
            observed.append(weather['at'])
        sensors = con.execute("SELECT data FROM records WHERE kind='sensors' AND json_extract(data,'$.locationId')=?", (location_id,)).fetchall()
        newest = {}
        for row in sensors:
            sensor = json.loads(row[0])
            feature = sensor.get('feature')
            if feature not in expected:
                continue
            reading = con.execute('SELECT * FROM readings WHERE sensor_id=? AND at>=? ORDER BY at DESC LIMIT 1', (sensor['id'], now - 3600)).fetchone()
            if reading and reading['unit'] == expected[feature] and (feature not in newest or reading['at'] > newest[feature]['at']):
                newest[feature] = reading
        for feature, reading in newest.items():
            values[feature] = reading['value']
            observed.append(reading['at'])
    import risk_engine
    risk_engine.features(values)  # Missing features skip prediction; no invented zeroes.
    return values, min(observed) if observed else now


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--interval', type=int, default=300)
    args = parser.parse_args()
    if args.interval < 30:
        parser.error('interval must be at least 30 seconds')
    server.initialize()
    while True:
        print(json.dumps(run_once()), flush=True)
        if args.once:
            break
        time.sleep(args.interval)
