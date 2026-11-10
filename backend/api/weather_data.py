"""Explicit synthetic weather for demonstrations; never a provider fallback."""

from datetime import datetime, timezone


def sample_weather(timestamp):
    hour = int(timestamp // 3600) * 3600
    hourly = [
        {
            "time": datetime.fromtimestamp(hour + h * 3600, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M"
            ),
            "rainfall": round((h % 7) * 1.2, 1),
            "temperature": 20,
            "humidity": 85,
        }
        for h in range(-72, 49)
    ]
    total = lambda start, end: round(sum(h["rainfall"] for h in hourly[start:end]), 1)
    return {
        "source": "Synthetic weather demonstration; not Open-Meteo data",
        "attribution": "Ashtaraksha educational sample",
        "simulated": True,
        "rainfall24h": total(48, 72),
        "rainfall72h": total(0, 72),
        "forecast24h": total(72, 96),
        "hourly": hourly,
        "units": {"rainfall": "mm", "temperature": "°C", "humidity": "%"},
    }
