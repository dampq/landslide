"""Read-only runtime checks; reports observations, never credentials or fake data."""

import httpx
from sqlalchemy import text
from .db import engine


def check_services():
    result = {}
    try:
        with engine.connect() as conn:
            result["database"] = {
                "ok": True,
                "engine": "PostgreSQL",
                "postgis": conn.execute(text("SELECT PostGIS_Version()")).scalar(),
            }
    except Exception:
        result["database"] = {
            "ok": False,
            "message": "Cannot query PostgreSQL/PostGIS. Verify DATABASE_URL and database startup.",
        }
    try:
        with httpx.Client(timeout=15, verify=True) as client:
            response = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": 25.297,
                    "longitude": 91.582,
                    "hourly": "precipitation",
                    "forecast_days": 1,
                    "timezone": "UTC",
                },
            )
            response.raise_for_status()
            payload = response.json()
        hourly = payload["hourly"]
        assert hourly["time"] and len(hourly["time"]) == len(hourly["precipitation"])
        result["weather"] = {
            "ok": True,
            "provider": "Open-Meteo",
            "hours": len(hourly["time"]),
            "message": "Provider response received. Refresh a location in the official portal to populate its live cache.",
        }
    except Exception:
        result["weather"] = {
            "ok": False,
            "provider": "Open-Meteo",
            "message": "Live provider could not be verified from this machine. Check outbound HTTPS to api.open-meteo.com. Explicitly labelled sample weather remains available.",
        }
    result["map"] = {
        "mode": "Bundled public-domain regional reference; online tiles optional",
        "message": "Verify street-tile access in the actual browser. Server connectivity cannot establish browser referrer or provider authorization.",
    }
    result["model"] = {
        "required": False,
        "message": "Model supplied by the separate team; no model is trained or substituted by this check.",
    }
    return result
