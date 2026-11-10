"""Rebuild the bundled reference from checksum-pinned public Natural Earth data.

Not part of application startup. Full upstream datasets remain in ignored .cache.
No tile downloads, API keys, government permissions or runtime dependencies.
"""

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = {
    "Arunachal Pradesh",
    "Assam",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Sikkim",
    "Tripura",
}
COUNTRIES = {"IND", "BGD", "BTN", "MMR", "NPL", "CHN", "PAK", "LKA"}


def rounded(value):
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, list):
        return [rounded(item) for item in value]
    return value


def main():
    metadata = json.loads((ROOT / "public/reference-map-source.json").read_text())
    cache = ROOT / ".cache/geography"
    cache.mkdir(parents=True, exist_ok=True)
    features = []
    for source in metadata["upstream"]:
        states = "_admin_1_" in source["url"]
        path = cache / ("states.geojson" if states else "countries.geojson")
        if not path.exists():
            with urllib.request.urlopen(source["url"], timeout=120) as response:
                content = response.read()
            if hashlib.sha256(content).hexdigest() != source["sha256"]:
                raise SystemExit(
                    "Upstream dataset checksum changed; review the source version before updating provenance."
                )
            path.write_bytes(content)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != source["sha256"]:
            raise SystemExit("Cached upstream dataset failed its recorded checksum.")
        for feature in json.loads(content)["features"]:
            props = feature["properties"]
            if states and props.get("adm0_a3") == "IND" and props.get("name") in STATES:
                features.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "name": props["name"],
                            "level": "state",
                            "labelLat": props["latitude"],
                            "labelLng": props["longitude"],
                        },
                        "geometry": feature["geometry"],
                    }
                )
            elif not states and props.get("ADM0_A3") in COUNTRIES:
                features.insert(
                    0,
                    {
                        "type": "Feature",
                        "properties": {"name": props["ADMIN"], "level": "country"},
                        "geometry": feature["geometry"],
                    },
                )
    if {
        f["properties"]["name"] for f in features if f["properties"]["level"] == "state"
    } != STATES:
        raise SystemExit("Expected all eight North Eastern state boundaries.")
    for feature in features:
        feature["geometry"]["coordinates"] = rounded(feature["geometry"]["coordinates"])
    output = ROOT / "public/reference-map.geojson"
    output.write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": features}, separators=(",", ":")
        )
    )
    print(
        f"Rebuilt {len(features)} public-domain reference features ({output.stat().st_size} bytes)."
    )


if __name__ == "__main__":
    main()
