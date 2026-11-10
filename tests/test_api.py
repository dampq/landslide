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


def test_model_absent_and_no_fake_predictions(actors, monkeypatch):
    monkeypatch.delenv("RF_MODEL_PATH", raising=False)
    assert actors["citizen"].get("/api/model").json()["available"] is False
    payload = {
        "locationId": "demo-location-0",
        "observedAt": __import__("time").time(),
        "source": "Test observations",
        "inputs": {
            "rainfall24h": 20,
            "rainfall72h": 60,
            "soilMoisture": 50,
            "slope": 30,
            "groundMovement": 1,
            "historicalEvents": 2,
        },
    }
    r = actors["official"].post("/api/predictions", json=payload)
    assert r.status_code == 503 and "not been supplied" in r.json()["detail"]
    assert actors["official"].get("/api/records/predictions").json()["total"] == 0
    payload["inputs"]["slope"] = 100
    assert actors["official"].post("/api/predictions", json=payload).status_code == 422


def test_model_checksum_enforced(actors, monkeypatch, tmp_path):
    path = tmp_path / "model.skops"
    path.write_bytes(b"not a model")
    monkeypatch.setenv("RF_MODEL_PATH", str(path))
    monkeypatch.setenv("RF_MODEL_SHA256", "0" * 64)
    result = actors["official"].get("/api/model").json()
    assert result["available"] is False and "checksum" in result["message"].lower()


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
