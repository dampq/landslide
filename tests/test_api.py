"""Integration tests against a disposable PostgreSQL/PostGIS database, never SQLite."""

import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://ashtaraksha:local-development@127.0.0.1:5433/ashtaraksha_test",
)
if not os.environ["DATABASE_URL"].rsplit("/", 1)[-1].endswith("_test"):
    raise RuntimeError("Tests require a separate database whose name ends with _test")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import pytest
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from api.main import app
from api.db import Session, User, Record, engine, migrate
from api.security import hash_password
import manage

PASSWORD = "test-password-at-least-12"


@pytest.fixture(autouse=True)
def clean():
    migrate()
    with engine.begin() as c:
        c.execute(
            text(
                "TRUNCATE attachments,records,sessions,users,audit,login_attempts CASCADE"
            )
        )
    manage.seed()


@pytest.fixture
def actors():
    clients = {}
    with Session.begin() as db:
        for role in ["citizen", "other", "official", "admin"]:
            db.add(
                User(
                    email=f"{role}@example.test",
                    name=role,
                    password=hash_password(PASSWORD),
                    role="citizen" if role == "other" else role,
                )
            )
    for role in ["citizen", "other", "official", "admin"]:
        c = TestClient(app)
        assert (
            c.post(
                "/api/auth/login",
                json={"email": f"{role}@example.test", "password": PASSWORD},
            ).status_code
            == 200
        )
        clients[role] = c
    return clients


def report(c, key="test-report-001"):
    r = c.post(
        "/api/reports",
        json={
            "clientId": key,
            "incident": "Road Blockage",
            "location": "Test location",
            "lat": 25.297,
            "lng": 91.582,
            "severity": "High",
            "description": "A test road hazard observed from a safe location.",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def alert(c):
    r = c.post(
        "/api/records/alerts",
        json={
            "name": "Test warning",
            "locationId": "demo-location-0",
            "severity": "High",
            "description": "Synthetic test alert",
            "action": "Review the demo scenario",
            "source": "Synthetic test",
            "simulated": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_postgis_health_and_migration_repeatable():
    migrate()
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["database"] == "PostgreSQL" and r.json()["postgis"]


def test_registration_real_authentication_and_cookie():
    c = TestClient(app)
    assert (
        c.post(
            "/api/auth/register",
            json={
                "email": "new@example.test",
                "name": "Citizen",
                "password": PASSWORD,
                "role": "admin",
            },
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/api/auth/register",
            json={"email": "new@example.test", "name": "Citizen", "password": PASSWORD},
        ).json()["role"]
        == "citizen"
    )
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "new@example.test", "password": "incorrect-long-password"},
        ).status_code
        == 401
    )
    r = c.post(
        "/api/auth/login", json={"email": "new@example.test", "password": PASSWORD}
    )
    assert r.status_code == 200
    assert (
        "HttpOnly" in r.headers["set-cookie"]
        and "SameSite=strict" in r.headers["set-cookie"]
    )
    assert c.get("/api/auth/me").json()["name"] == "Citizen"
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401


def test_permissions_and_origin(actors):
    c = actors["citizen"]
    for path in [
        "/api/admin/users",
        "/api/admin/system",
        "/api/response/priorities",
        "/api/analytics",
        "/api/export/reports",
    ]:
        assert c.get(path).status_code == 403, path
    assert c.post("/api/sensors/simulate").status_code == 403
    assert (
        c.post(
            "/api/auth/logout", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_report_privacy_validation_and_review(actors):
    row = report(actors["citizen"])
    id = row["id"]
    assert actors["other"].get("/api/records/reports").json()["total"] == 0
    assert actors["other"].get(f"/api/reports/{id}/media").status_code == 404
    assert (
        actors["citizen"]
        .patch(
            f"/api/reports/{id}/verify",
            json={"status": "Verified", "note": "Confirmed on site"},
        )
        .status_code
        == 403
    )
    assert (
        actors["official"]
        .patch(
            f"/api/reports/{id}/verify",
            json={"status": "Resolved", "note": "Confirmed on site"},
        )
        .status_code
        == 409
    )
    assert (
        actors["official"]
        .patch(
            f"/api/reports/{id}/verify",
            json={"status": "Verified", "note": "Confirmed on site"},
        )
        .status_code
        == 200
    )
    assert (
        actors["official"]
        .patch(
            f"/api/reports/{id}/verify",
            json={"status": "Resolved", "note": "Site made safe"},
        )
        .status_code
        == 200
    )
    assert (
        actors["official"]
        .patch(
            f"/api/reports/{id}/verify",
            json={"status": "Rejected", "note": "Changed mind"},
        )
        .status_code
        == 409
    )


@pytest.mark.parametrize(
    "change",
    [
        {"lat": 91},
        {"lng": 181},
        {"description": "short"},
        {"severity": "Fake"},
        {"lat": "NaN"},
    ],
)
def test_bad_report_inputs(actors, change):
    data = {
        "clientId": "valid-client-id",
        "incident": "Road Blockage",
        "location": "Test village",
        "lat": 25,
        "lng": 91,
        "severity": "High",
        "description": "A sufficiently detailed test report.",
    }
    assert (
        actors["citizen"].post("/api/reports", json={**data, **change}).status_code
        == 422
    )


def test_concurrent_report_retries(actors):
    c = actors["citizen"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: report(c, "concurrent-retry-id"), range(4)))
    assert len({r["id"] for r in results}) == 1
    assert c.get("/api/records/reports").json()["total"] == 1


def test_opencv_media_dedup_and_authorization(actors):
    id = report(actors["citizen"])["id"]
    ok, encoded = cv2.imencode(".png", np.ones((20, 30, 3), dtype=np.uint8) * 80)
    assert ok
    content = encoded.tobytes()
    c = actors["citizen"]
    r = c.post(
        f"/api/reports/{id}/media", files={"file": ("photo.png", content, "image/png")}
    )
    assert r.status_code == 201, r.text
    assert r.json()["processing"]["width"] == 30
    again = c.post(
        f"/api/reports/{id}/media", files={"file": ("retry.png", content, "image/png")}
    )
    assert again.json()["id"] == r.json()["id"]
    assert actors["other"].get("/api/media/" + r.json()["id"]).status_code == 404
    assert actors["official"].get("/api/media/" + r.json()["id"]).content == content
    assert (
        c.post(
            f"/api/reports/{id}/media",
            files={"file": ("bad.png", b"\x89PNG\r\n\x1a\nnot-an-image", "image/png")},
        ).status_code
        == 422
    )


def test_partial_offline_sync_and_retry(actors):
    c = actors["citizen"]
    row = {
        "clientId": "offline-report-1",
        "incident": "Ground Crack",
        "location": "Test location",
        "lat": 25,
        "lng": 91,
        "severity": "Low",
        "description": "An offline report description.",
    }
    payload = {"reports": [row, {**row, "clientId": "offline-report-2", "lat": 999}]}
    result = c.post("/api/sync", json=payload)
    assert result.status_code == 200, result.text
    assert [v["ok"] for v in result.json()["results"]] == [True, False]
    assert (
        c.post("/api/sync", json={"reports": [row]}).json()["results"][0]["report"][
            "id"
        ]
        == result.json()["results"][0]["report"]["id"]
    )


def test_spatial_layers_bbox_and_population(actors):
    c = actors["citizen"]
    features = c.get("/api/gis?layers=locations&bbox=91,25,92,26").json()["features"]
    assert len(features) == 1 and features[0]["properties"]["name"] == "Mawsynram"
    assert c.get("/api/gis?bbox=invalid").status_code == 422
    ex = c.get("/api/exposure/demo-location-0?radius=5000").json()
    assert ex["approximatePopulation"] == 500 and ex["simulated"] is True
    assert c.get("/api/exposure/demo-location-0?radius=0").status_code == 422


def test_alert_review_publish_idempotency_and_preferences(actors):
    c = actors["official"]
    r = alert(c)
    id = r["id"]
    assert actors["citizen"].get("/api/records/alerts").json()["total"] == 0
    assert (
        c.post(
            f"/api/alerts/{id}/publish", json={"note": "Reviewed for test"}
        ).status_code
        == 409
    )
    assert (
        c.post(
            f"/api/alerts/{id}/approve", json={"note": "Reviewed for test"}
        ).status_code
        == 200
    )
    assert (
        actors["other"].patch("/api/settings", json={"inApp": False}).status_code == 200
    )
    for _ in range(2):
        assert (
            c.post(
                f"/api/alerts/{id}/publish", json={"note": "Approved test publication"}
            ).status_code
            == 200
        )
    assert actors["citizen"].get("/api/records/alerts").json()["total"] == 1
    assert actors["citizen"].get("/api/records/notifications").json()["total"] == 1
    assert actors["other"].get("/api/records/notifications").json()["total"] == 0
    assert (
        c.patch(f"/api/records/alerts/{id}", json={"description": "Edited"}).status_code
        == 409
    )
    assert (
        c.post(
            f"/api/alerts/{id}/resolve", json={"note": "Demo warning resolved"}
        ).status_code
        == 200
    )


def test_edit_alert_invalidates_approval(actors):
    c = actors["official"]
    id = alert(c)["id"]
    c.post(f"/api/alerts/{id}/approve", json={"note": "Review test"})
    assert (
        c.patch(
            f"/api/records/alerts/{id}", json={"description": "Updated warning wording"}
        ).json()["status"]
        == "Draft"
    )


def test_atomic_deployment_and_transitions(actors):
    c = actors["official"]
    payload = {"teamId": "demo-team-0", "locationId": "demo-location-0"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: c.post("/api/deployments", json=payload), range(2))
        )
    assert sorted(r.status_code for r in results) == [201, 409]
    id = next(r for r in results if r.status_code == 201).json()["id"]
    assert (
        c.post(
            f"/api/deployments/{id}/status", json={"status": "Completed"}
        ).status_code
        == 409
    )
    assert (
        c.post(f"/api/deployments/{id}/status", json={"status": "On Site"}).status_code
        == 200
    )
    assert (
        c.post(
            f"/api/deployments/{id}/status", json={"status": "Completed"}
        ).status_code
        == 200
    )
    assert c.post("/api/deployments", json=payload).status_code == 201


V1_FEATURES = dict(worldcover_class=10, clay_fraction=.199, sand_fraction=.367,
                   soil_ph=5.5, soc_stock_t_ha=170.)
V2_FEATURES = {**V1_FEATURES, "bio12_annual_precipitation_mm": 2500.,
               "bio13_wettest_month_precip_mm": 500., "bio15_precipitation_seasonality_pct": 80.,
               "bio16_wettest_quarter_precip_mm": 1200., "bio17_driest_quarter_precip_mm": 100.,
               "elevation_m": 450., "slope_degrees": 18., "aspect_sin": .5, "aspect_cos": .866}


def prediction_payload(version="1", inputs=None):
    return {"locationId": "demo-location-0", "observedAt": 1600000000,
            "source": "Documented environmental layer extraction", "modelVersion": version,
            "inputs": inputs if inputs is not None else (V1_FEATURES if version == "1" else V2_FEATURES)}


@pytest.mark.parametrize("version", ["1", "2"])
def test_supplied_model_http_and_helper_parity(actors, version, tmp_path):
    import importlib.util
    from api import prediction
    files = prediction.bundle(version)
    for name, raw in files.items():
        (tmp_path / name).write_bytes(raw)
    helper = "predict" if version == "1" else "predict_v2"
    spec = importlib.util.spec_from_file_location("handoff_" + version, tmp_path / (helper + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = prediction_payload(version)
    expected = module.predict_relative_score(payload["inputs"])["experimental_presence_background_score"]
    if version == "1":
        assert expected == pytest.approx(0.7506392613449581, abs=1e-14)
    c = actors["official"]
    status = c.get("/api/model", params={"version": version}).json()
    assert status["available"] and len(status["features"]) == (5 if version == "1" else 14)
    assert c.get("/health").json()["status"] == "ok"
    assert actors["admin"].get("/api/admin/system").json()["model"]["available"]
    # Key order must not affect inference.
    payload["inputs"] = dict(reversed(list(payload["inputs"].items())))
    r = c.post("/api/predictions", json=payload)
    assert r.status_code == 201, r.text
    result = r.json()
    assert result["experimental_presence_background_score"] == pytest.approx(expected, abs=1e-14)
    assert result["modelVersion"] == version and not result["operationallyValidated"]
    assert result["source"] == payload["source"]
    assert "probability" not in result and "label" not in result
    assert "not a calibrated probability" in result["interpretation"]
    assert c.get("/api/records/predictions").json()["total"] == 1
    assert actors["citizen"].post("/api/predictions", json=payload).status_code == 403
    if version == "2":
        payload["inputs"] = {k: v if k == "worldcover_class" else None for k, v in V2_FEATURES.items()}
        result = c.post("/api/predictions", json=payload).json()
        assert len(result["imputed_fields"]) == 13
        assert result["experimental_presence_background_score"] == pytest.approx(
            module.predict_relative_score(payload["inputs"])["experimental_presence_background_score"])


@pytest.mark.parametrize("version", ["1", "2"])
def test_model_invalid_inputs_never_persist(actors, version):
    base = V1_FEATURES if version == "1" else V2_FEATURES
    invalid = [dict(base, worldcover_class=x) for x in [True, 20, "10", 10.0, None]]
    invalid += [dict(base, clay_fraction=x) for x in [True, "0.2", -1, 2, [], {}]]
    invalid += [{k: v for k, v in base.items() if k != "soil_ph"}, dict(base, extra=1)]
    if version == "1":
        invalid += [dict(base, soil_ph=None), dict(base, soil_ph=0)]
    for inputs in invalid:
        r = actors["official"].post("/api/predictions", json=prediction_payload(version, inputs))
        assert r.status_code == 422, r.text
    assert actors["official"].get("/api/records/predictions").json()["total"] == 0


def test_model_missing_and_checksum_fail_closed(actors, monkeypatch, tmp_path):
    import zipfile
    import joblib
    from api import prediction
    original = prediction.ARCHIVE
    monkeypatch.setattr(prediction, "ARCHIVE", tmp_path / "missing.zip")
    assert not actors["official"].get("/api/model").json()["available"]
    assert actors["official"].post("/api/predictions", json=prediction_payload()).status_code == 503
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(original) as src, zipfile.ZipFile(tampered, "w") as dst:
        for name in src.namelist():
            raw = src.read(name)
            dst.writestr(name, raw + b"tampered" if name.endswith(".joblib") else raw)
    monkeypatch.setattr(prediction, "ARCHIVE", tampered)
    monkeypatch.setattr(joblib, "load", lambda *a, **kw: pytest.fail("Unverified model deserialized"))
    for version in ["1", "2"]:
        status = actors["official"].get("/api/model", params={"version": version}).json()
        assert not status["available"] and "checksum" in status["message"]
        assert actors["official"].post("/api/predictions", json=prediction_payload(version)).status_code == 503
    assert actors["official"].get("/api/records/predictions").json()["total"] == 0
    assert actors["official"].get("/api/model?version=3").status_code == 422


def test_weather_failure_preserves_cache(actors, monkeypatch):
    import api.main as main

    def fail(*a, **kw):
        raise RuntimeError("Provider offline")

    class OfflineClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        get = fail

    monkeypatch.setattr(main.httpx, "Client", OfflineClient)
    c = actors["official"]
    before = c.get("/api/weather/demo-location-0").json()
    assert c.post("/api/weather/demo-location-0/refresh").status_code == 502
    assert c.get("/api/weather/demo-location-0").json() == before


def test_simulated_sensor_history(actors):
    c = actors["official"]
    assert c.post("/api/sensors/simulate").json()["updated"] == 8
    assert c.post("/api/sensors/simulate").json()["updated"] == 8
    sensors = c.get("/api/records/sensors").json()
    assert sensors["total"] == 8 and all(r["simulated"] for r in sensors["items"])
    for sensor in sensors["items"]:
        assert sensor["rainfall72hMm"] >= sensor["value"]
        assert 0 <= sensor["soilMoisturePercent"] <= 100
        assert 0 <= sensor["groundMovementMmPerHour"] <= 10
    assert c.get("/api/records/readings").json()["total"] == 16
    assert c.get("/api/records/predictions").json()["total"] == 0


def test_import_idempotent_attributed_and_population_requirements(actors):
    c = actors["admin"]
    item = {
        "name": "Imported event",
        "lat": 25,
        "lng": 91,
        "observedAt": 1750000000,
        "source": "Synthetic test import",
        "simulated": True,
    }
    assert (
        c.post("/api/admin/import/history", json={"items": [item]}).json()["inserted"]
        == 1
    )
    assert (
        c.post("/api/admin/import/history", json={"items": [item]}).json()["unchanged"]
        == 1
    )
    assert (
        c.post(
            "/api/admin/import/history", json={"items": [{**item, "source": ""}]}
        ).status_code
        == 422
    )
    pop = {
        "name": "Population cell",
        "lat": 25,
        "lng": 91,
        "source": "WorldPop",
        "simulated": False,
        "population": 100,
    }
    assert (
        c.post("/api/admin/import/villages", json={"items": [pop]}).status_code == 422
    )
    assert (
        c.post(
            "/api/admin/import/villages",
            json={
                "items": [
                    {**pop, "year": 2020, "resolutionM": 100, "license": "CC BY 4.0"}
                ]
            },
        ).status_code
        == 200
    )


def test_admin_role_changes_revoke_sessions(actors):
    c = actors["admin"]
    users = c.get("/api/admin/users").json()["items"]
    citizen = next(u for u in users if u["name"] == "citizen")
    own = next(u for u in users if u["name"] == "admin")
    assert (
        c.patch("/api/admin/users/" + own["id"], json={"role": "citizen"}).status_code
        == 409
    )
    assert (
        c.patch(
            "/api/admin/users/" + citizen["id"], json={"role": "official"}
        ).status_code
        == 200
    )
    assert actors["citizen"].get("/api/auth/me").status_code == 401


def test_csv_formula_escaping_and_analytics(actors):
    c = actors["official"]
    row = {
        "name": '=HYPERLINK("bad")',
        "lat": 25,
        "lng": 91,
        "status": "Open",
        "source": "test",
        "simulated": True,
    }
    assert c.post("/api/records/roads", json=row).status_code == 201
    result = c.get("/api/export/roads")
    assert result.status_code == 200
    assert "'=HYPERLINK" in result.text
    assert "simulated" in result.text and "source" in result.text
    assert len(c.get("/api/analytics").json()["states"]) == 8


def test_malformed_imports_are_validation_errors(actors):
    c = actors["admin"]
    for payload in (
        {"items": [1]},
        {"type": "FeatureCollection", "features": [{}]},
        {
            "type": "FeatureCollection",
            "features": [
                {"properties": {}, "geometry": {"type": "Point", "coordinates": []}}
            ],
        },
    ):
        assert c.post("/api/admin/import/history", json=payload).status_code == 422


def test_missing_population_is_unavailable_not_zero(actors):
    with Session.begin() as db:
        for r in db.scalars(select(Record).where(Record.kind == "villages")):
            db.delete(r)
    result = actors["official"].get("/api/exposure/demo-location-0").json()
    assert result["populationRecords"] == 0 and result["approximatePopulation"] is None
    priority = actors["official"].get("/api/response/priorities").json()["items"][0]
    assert priority["incompletePopulationData"] is True


def test_login_rate_limit_persists():
    c = TestClient(app)
    for _ in range(10):
        assert (
            c.post(
                "/api/auth/login",
                json={"email": "unknown@example.test", "password": PASSWORD},
            ).status_code
            == 401
        )
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "unknown@example.test", "password": PASSWORD},
        ).status_code
        == 429
    )


def test_weather_success_is_attributed_and_replaces_sample(actors, monkeypatch):
    import api.main as main
    from datetime import datetime, timezone

    current = int(main.now() // 3600) * 3600
    hours = [
        datetime.fromtimestamp(current + h * 3600, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M"
        )
        for h in range(-72, 73)
    ]
    payload = {
        "hourly": {
            "time": hours,
            "precipitation": [1] * len(hours),
            "temperature_2m": [20] * len(hours),
            "relative_humidity_2m": [80] * len(hours),
        }
    }

    class ProviderResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    class ProviderClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def get(self, *a, **kw):
            return ProviderResponse()

    monkeypatch.setattr(main.httpx, "Client", ProviderClient)
    result = actors["official"].post("/api/weather/demo-location-0/refresh")
    assert result.status_code == 200, result.text
    assert result.json()["rainfall24h"] == 24 and result.json()["rainfall72h"] == 72
    assert result.json()["forecast24h"] == 24 and result.json()["simulated"] is False
    assert "Open-Meteo" in result.json()["source"]


def test_explicit_sample_weather_requires_official_and_is_consistent(actors):
    c = actors["official"]
    assert (
        actors["citizen"]
        .post("/api/weather/demo-location-0/sample", json={})
        .status_code
        == 403
    )
    result = c.post("/api/weather/demo-location-0/sample", json={})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["simulated"] is True and "not Open-Meteo" in data["source"]
    rain = [h["rainfall"] for h in data["hourly"]]
    assert data["rainfall24h"] == round(sum(rain[48:72]), 1)
    assert data["rainfall72h"] == round(sum(rain[:72]), 1)
    assert data["forecast24h"] == round(sum(rain[72:96]), 1)
    assert c.get("/api/weather/demo-location-0").json()["simulated"] is True


def test_sample_weather_never_silently_overwrites_a_live_cache(actors):
    with Session.begin() as db:
        row = db.get(Record, "weather-demo-location-0")
        row.data = {**row.data, "simulated": False, "source": "Test live cache marker"}
    c = actors["official"]
    assert c.post("/api/weather/demo-location-0/sample", json={}).status_code == 409
    assert (
        c.get("/api/weather/demo-location-0").json()["source"]
        == "Test live cache marker"
    )
    assert (
        c.post(
            "/api/weather/demo-location-0/sample", json={"replaceLive": True}
        ).json()["simulated"]
        is True
    )


def test_malformed_live_weather_cannot_corrupt_existing_cache(actors, monkeypatch):
    import api.main as main

    class ProviderResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "hourly": {
                    "time": ["2026-11-10T00:00"],
                    "precipitation": [1],
                    "temperature_2m": [],
                    "relative_humidity_2m": [80],
                }
            }

    class ProviderClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def get(self, *a, **kw):
            return ProviderResponse()

    before = actors["official"].get("/api/weather/demo-location-0").json()
    monkeypatch.setattr(main.httpx, "Client", ProviderClient)
    assert (
        actors["official"].post("/api/weather/demo-location-0/refresh").status_code
        == 502
    )
    assert actors["official"].get("/api/weather/demo-location-0").json() == before


def test_registration_policy_does_not_silently_block_short_login_attempts():
    c = TestClient(app)
    assert (
        c.post(
            "/api/auth/register",
            json={
                "email": "short-policy@example.test",
                "name": "Policy check",
                "password": "short",
            },
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "short-policy@example.test", "password": "short"},
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/api/auth/register",
            json={"email": "short-policy@example.test", "password": PASSWORD},
        ).status_code
        == 422
    )
    assert (
        c.post(
            "/api/auth/register",
            json={
                "email": "short-policy@example.test",
                "name": "Policy check",
                "password": PASSWORD,
            },
        ).status_code
        == 201
    )
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "short-policy@example.test", "password": "short"},
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/api/auth/login",
            json={"email": "short-policy@example.test", "password": PASSWORD},
        ).status_code
        == 200
    )
    assert c.get("/api/auth/me").json()["role"] == "citizen"


def test_supplied_examples_separate_and_evaluation_context(actors):
    c = actors['official']
    before = c.get('/api/records/predictions').json()['total']
    for version in ['1', '2']:
        sample = c.get(f'/api/model/examples/{version}').json()
        assert sample['simulated'] and len(sample['inputs']) == (5 if version == '1' else 14)
        result = c.post(f'/api/model/examples/{version}/run').json()
        assert result['simulated'] and result['locationId'] is None
        assert result['assessmentMode'] == 'supplied-example'
        if version == '1':
            assert result['experimental_presence_background_score'] == pytest.approx(sample['referenceScore'], abs=1e-14)
        else:
            assert sample['referenceScore'] is None
        assert actors['citizen'].post(f'/api/model/examples/{version}/run').status_code == 403
    assert c.get('/api/records/predictions').json()['total'] == before
    comparison = c.get('/api/model/comparison').json()['versions']
    assert len(comparison) == 2
    for v in comparison:
        e = v['evaluation']
        assert e['evaluatedRows'] == 358 and e['threshold'] == .5
        assert e['sampleEvents'] == 179 and e['sampleBackground'] == 179
        assert e['independentTestSize'] is None and e['method']
        assert e['precision'] is not None and e['recall'] is not None and e['f1'] is not None


def test_verified_incident_to_completed_response_preserves_context(actors):
    c = actors['official']
    incident = report(actors['citizen'])
    rid = incident['id']
    payload = dict(teamId='demo-team-0', locationId='demo-location-0', reportId=rid)
    assert c.get(f'/api/response/reports/{rid}').status_code == 409
    assert c.post('/api/deployments', json={**payload, 'confirmLocationAssociation': True}).status_code == 409
    review = c.patch(f'/api/reports/{rid}/verify', json={'status':'Verified', 'note':'Confirmed incident for response planning'}).json()
    planned = c.get(f'/api/response/reports/{rid}').json()
    assert planned['id'] == rid and planned['lat'] == incident['lat']
    assert planned['reviewHistory'] == review['reviewHistory']
    assert c.post('/api/deployments', json=payload).status_code == 422
    assert actors['citizen'].get(f'/api/response/reports/{rid}').status_code == 403
    deployed = c.post('/api/deployments', json={**payload, 'confirmLocationAssociation':True})
    assert deployed.status_code == 201, deployed.text
    data = deployed.json()
    assert data['reportId'] == rid and data['reportCoordinates'] == {'lat':incident['lat'],'lng':incident['lng']}
    assert data['reportReviewHistory'] == review['reviewHistory']
    for status in ['On Site','Completed']:
        result = c.post(f"/api/deployments/{data['id']}/status", json={'status':status})
        assert result.status_code == 200 and result.json()['reportId'] == rid
    audit = actors['admin'].get('/api/admin/system').json()['audit']
    assert any(a['action']=='report:response-association' and a['target']==rid for a in audit)
    assert any(a['action']=='deployment:Completed' and a['target']==data['id'] for a in audit)
