"""Bounded external adapters. No credentials are stored in API responses."""
import base64
import json
import os
import urllib.parse
import urllib.request
import urllib.error


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'Provider redirects are disabled', headers, fp)


def request_json(url, payload=None, headers=None, form=False):
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise ValueError('Provider URLs must use HTTPS')
    headers = dict(headers or {})
    body = None
    if payload is not None:
        body = (urllib.parse.urlencode(payload) if form else json.dumps(payload)).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
        raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError('Provider response too large')
        return json.loads(raw)


def weather(lat, lng):
    query = urllib.parse.urlencode({'latitude': lat, 'longitude': lng,
            'hourly': 'precipitation,temperature_2m,relative_humidity_2m,soil_moisture_0_to_1cm',
            'past_days': 3, 'forecast_days': 3, 'timezone': 'UTC', 'timeformat': 'unixtime'})
    return request_json('https://api.open-meteo.com/v1/forecast?' + query)


def send_sms(phone, message):
    sid, token, sender = (os.environ.get(k) for k in ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_FROM'])
    if not all([sid, token, sender]):
        raise ValueError('Twilio credentials are not configured')
    if not sid.startswith('AC') or not sid.isalnum():
        raise ValueError('Invalid Twilio account SID')
    auth = base64.b64encode(f'{sid}:{token}'.encode()).decode()
    return request_json(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
                        {'From': sender, 'To': phone, 'Body': message}, {'Authorization': 'Basic ' + auth}, form=True)


def analyze_image(encoded, mime):
    endpoint = os.environ.get('VISION_ENDPOINT')
    if not endpoint:
        raise ValueError('VISION_ENDPOINT is not configured')
    return request_json(endpoint, {'imageBase64': encoded, 'mimeType': mime},
                        {'Authorization': 'Bearer ' + os.environ.get('VISION_API_KEY', '')})


def message_status(message_id):
    sid, token = os.environ.get('TWILIO_ACCOUNT_SID', ''), os.environ.get('TWILIO_AUTH_TOKEN', '')
    if not sid.startswith('AC') or not sid.isalnum() or not message_id.startswith('SM') or not message_id.isalnum() or not token:
        raise ValueError('Invalid provider configuration or message id')
    auth = base64.b64encode(f'{sid}:{token}'.encode()).decode()
    return request_json(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages/{message_id}.json',
                        headers={'Authorization': 'Basic ' + auth})
