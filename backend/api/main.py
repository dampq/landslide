"""Ashtaraksha FastAPI application: connected student demonstration platform."""

import csv
import hashlib
import io
import json
import math
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "25000000")
import cv2
import httpx
import numpy as np
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, text, func
from sqlalchemy.exc import IntegrityError
from .db import (
    Session,
    engine,
    User,
    LoginAttempt,
    LoginSession,
    Record,
    Attachment,
    Audit,
    now,
    uid,
)
from .security import (
    db_session,
    user,
    official,
    admin,
    public_user,
    hash_password,
    verify_password,
    token_hash,
    audit,
)
from .prediction import FEATURES, predict, load_model
from .weather_data import sample_weather

ORIGINS = os.environ.get(
    "APP_ORIGINS",
    "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://localhost:4173",
).split(",")
KINDS = {
    "locations",
    "roads",
    "villages",
    "infrastructure",
    "history",
    "satellite",
    "sensors",
    "alerts",
    "teams",
    "reports",
    "readings",
    "predictions",
    "deployments",
    "notifications",
}
WRITABLE = {
    "locations",
    "roads",
    "villages",
    "infrastructure",
    "history",
    "satellite",
    "teams",
    "alerts",
}
LEVELS = {"Low", "Moderate", "High", "Critical"}
SOURCES = [
    {
        "name": "Open-Meteo",
        "purpose": "Weather forecasts and historical weather",
        "url": "https://open-meteo.com/",
        "access": "Forecast adapter integrated; live access depends on network availability",
        "license": "CC BY 4.0; attribution required",
    },
    {
        "name": "OpenStreetMap",
        "purpose": "Roads, villages, infrastructure and base map",
        "url": "https://www.openstreetmap.org/",
        "access": "Base tiles integrated; GeoJSON import supported. Do not bulk-download public tiles.",
        "license": "ODbL; © OpenStreetMap contributors",
    },
    {
        "name": "GSI Bhukosh",
        "purpose": "Historical landslide inventory",
        "url": "https://bhukosh.gsi.gov.in/",
        "access": "Import permitted exports; availability and access terms vary",
        "license": "Check dataset terms before import",
    },
    {
        "name": "NRSC Bhuvan",
        "purpose": "Historical landslide and terrain information",
        "url": "https://bhuvan.nrsc.gov.in/",
        "access": "Optional public portal; no restricted access assumed",
        "license": "Check source-specific terms",
    },
    {
        "name": "NASA GPM IMERG",
        "purpose": "Rainfall observations",
        "url": "https://gpm.nasa.gov/data/imerg",
        "access": "Optional dataset download/import; Earthdata registration may be needed",
        "license": "Follow NASA dataset attribution",
    },
    {
        "name": "NASA SRTM",
        "purpose": "Elevation and derived slope",
        "url": "https://www.earthdata.nasa.gov/data/instruments/srtm",
        "access": "Optional downloaded terrain values; slope must be derived/validated externally",
        "license": "Follow NASA dataset attribution",
    },
    {
        "name": "NASA SMAP / MOSDAC",
        "purpose": "Soil moisture",
        "url": "https://www.earthdata.nasa.gov/data/instruments/smap",
        "access": "Optional; volumetric moisture is not saturation percent. Do not interchange units.",
        "license": "Check dataset terms",
    },
    {
        "name": "WorldPop",
        "purpose": "Approximate population distribution",
        "url": "https://www.worldpop.org/",
        "access": "Import population grid-cell centres with counts and resolution; PostGIS radius exposure sum",
        "license": "Check selected dataset; record year, resolution and attribution",
    },
    {
        "name": "Copernicus Browser",
        "purpose": "Explore Sentinel-1 and Sentinel-2 imagery",
        "url": "https://browser.dataspace.copernicus.eu/",
        "access": "Optional external imagery exploration; account may be needed for downloads",
        "license": "Copernicus Sentinel data terms",
    },
]

app = FastAPI(
    title="Ashtaraksha API",
    version="3.0.0",
    description="Student disaster monitoring platform. Demonstration records are explicitly labelled. No model training is provided.",
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and origin
        and origin not in ORIGINS
    ):
        return JSONResponse({"detail": "Untrusted request origin"}, status_code=403)
    if (
        request.headers.get("content-length", "").isdigit()
        and int(request.headers["content-length"]) > 11_000_000
    ):
        return JSONResponse({"detail": "Request exceeds 11 MB"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


class LoginCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    model_config = ConfigDict(extra="forbid")


class RegistrationCredentials(LoginCredentials):
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=100)


class ReportInput(BaseModel):
    clientId: str = Field(min_length=8, max_length=100)
    incident: str = Field(min_length=2, max_length=80)
    location: str = Field(min_length=2, max_length=200)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    severity: Literal["Low", "Moderate", "High", "Critical"]
    description: str = Field(min_length=10, max_length=4000)
    model_config = ConfigDict(extra="forbid")


class Verification(BaseModel):
    status: Literal["Verified", "Rejected", "Resolved"]
    note: str = Field(min_length=5, max_length=2000)


class PredictionInput(BaseModel):
    locationId: str
    observedAt: float = Field(allow_inf_nan=False)
    inputs: dict[str, float]
    source: str = Field(min_length=3, max_length=200)


def serial(r):
    return {
        **r.data,
        "id": r.id,
        "kind": r.kind,
        "lat": r.lat,
        "lng": r.lng,
        "createdAt": r.created,
        "updatedAt": r.updated,
    }


def get_record(db, id, kind=None):
    r = db.get(Record, id)
    if not r or (kind and r.kind != kind):
        raise HTTPException(404, "Record not found")
    return r


def report_access(r, account):
    if account.role == "citizen" and r.owner_id != account.id:
        raise HTTPException(404, "Report not found")


def add_record(db, kind, data, owner=None, client_id=None, id=None):
    r = Record(
        id=id or uid(),
        kind=kind,
        owner_id=owner,
        client_id=client_id,
        data=data,
        lat=data.get("lat"),
        lng=data.get("lng"),
    )
    db.add(r)
    db.flush()
    return r


def valid_record(kind, data):
    if not isinstance(data, dict):
        raise HTTPException(422, "Expected record object")
    try:
        encoded = json.dumps(data, allow_nan=False)
    except (ValueError, TypeError):
        raise HTTPException(422, "Record contains invalid numeric values")
    if len(encoded) > 30000:
        raise HTTPException(422, "Expected record object under 30 KB")
    required = {
        "locations": ["name", "district", "state", "lat", "lng"],
        "roads": ["name", "status", "lat", "lng"],
        "villages": ["name", "lat", "lng", "population"],
        "infrastructure": ["name", "type", "lat", "lng"],
        "history": ["name", "lat", "lng", "observedAt"],
        "satellite": ["name", "lat", "lng", "url"],
        "teams": ["name"],
        "alerts": ["name", "locationId", "severity", "description", "action"],
    }[kind]
    for key in required:
        if key not in data or data[key] is None or data[key] == "":
            raise HTTPException(422, f"{key} is required")
    for key, lo, hi in [
        ("lat", -90, 90),
        ("lng", -180, 180),
        ("population", 0, 1e9),
        ("slope", 0, 90),
        ("resolutionM", 1, 100000),
    ]:
        if key in data and (
            isinstance(data[key], bool)
            or not isinstance(data[key], (int, float))
            or not math.isfinite(data[key])
            or not lo <= data[key] <= hi
        ):
            raise HTTPException(422, f"{key} must be a number between {lo} and {hi}")
    if (
        data.get("level", "Low") not in LEVELS
        or data.get("severity", "Low") not in LEVELS
    ):
        raise HTTPException(422, "Invalid risk level")
    if kind == "roads" and data["status"] not in (
        "Open",
        "Partially Blocked",
        "Blocked",
        "Under Verification",
    ):
        raise HTTPException(422, "Invalid road status")
    if not isinstance(data.get("source"), str) or not data["source"].strip():
        raise HTTPException(422, "source attribution is required")
    for key in ("name", "description", "action", "district", "state"):
        if key in data and (not isinstance(data[key], str) or len(data[key]) > 4000):
            raise HTTPException(422, f"{key} must be text under 4000 characters")
    if kind == "history" and (
        not isinstance(data["observedAt"], (int, float))
        or not 0 <= data["observedAt"] <= now() + 86400
    ):
        raise HTTPException(422, "Historical event time must be valid UTC Unix seconds")
    if not isinstance(data.get("simulated"), bool):
        raise HTTPException(422, "simulated must explicitly be true or false")
    if kind == "satellite" and not str(data["url"]).startswith("https://"):
        raise HTTPException(422, "Imagery URL must use HTTPS")
    if kind == "villages" and not data["simulated"]:
        for k in ("year", "resolutionM", "license"):
            if not data.get(k):
                raise HTTPException(422, f"Population data requires {k}")
    return data


@app.get("/health")
def health(db=Depends(db_session)):
    version = db.execute(text("SELECT PostGIS_Version()")).scalar()
    return {
        "status": "ok",
        "service": "ashtaraksha",
        "database": "PostgreSQL",
        "postgis": version,
        "version": "3.0.0",
    }


@app.get("/api/sources")
def sources():
    return {"items": SOURCES}


@app.post("/api/auth/register", status_code=201)
def register(body: RegistrationCredentials, db=Depends(db_session)):
    email = body.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1] or not body.name.strip():
        raise HTTPException(422, "A valid email and name are required")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email is already registered")
    u = User(
        email=email,
        name=body.name.strip(),
        password=hash_password(body.password),
        role="citizen",
    )
    db.add(u)
    try:
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "Email is already registered")
    audit(db, u, "register", u.id)
    return public_user(u)


@app.post("/api/auth/login")
def login(body: LoginCredentials, response: Response, db=Depends(db_session)):
    email = body.email.strip().lower()
    key = hashlib.sha256(email.encode()).hexdigest()
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})
    attempt = db.get(LoginAttempt, key)
    if not attempt:
        attempt = LoginAttempt(key=key, attempts=0, since=now())
        db.add(attempt)
    if now() - attempt.since > 900:
        attempt.since = now()
        attempt.attempts = 0
    if attempt.attempts >= 10:
        raise HTTPException(429, "Too many attempts; retry in 15 minutes")
    u = db.scalar(select(User).where(User.email == email))
    if not u or not u.active or not verify_password(body.password, u.password):
        attempt.attempts += 1
        db.commit()
        raise HTTPException(401, "Invalid email or password")
    attempt.attempts = 0
    token = secrets.token_urlsafe(32)
    db.add(
        LoginSession(token_hash=token_hash(token), user_id=u.id, expires=now() + 86400)
    )
    response.set_cookie(
        "ashtaraksha_session",
        token,
        max_age=86400,
        httponly=True,
        samesite="strict",
        secure=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        path="/",
    )
    audit(db, u, "login", u.id)
    return public_user(u)


@app.get("/api/auth/me")
def me(account=Depends(user)):
    return public_user(account)


@app.post("/api/auth/logout")
def logout(
    request: Request, response: Response, account=Depends(user), db=Depends(db_session)
):
    s = db.get(LoginSession, token_hash(request.cookies.get("ashtaraksha_session", "")))
    if s:
        db.delete(s)
    response.delete_cookie("ashtaraksha_session", path="/")
    return {"ok": True}


@app.patch("/api/settings")
def preferences(body: dict, account=Depends(user), db=Depends(db_session)):
    if set(body) - {"language", "inApp", "states"}:
        raise HTTPException(422, "Unsupported preference")
    if body.get("language", "en") not in ("en", "hi", "as"):
        raise HTTPException(422, "Supported languages: en, hi, as")
    if "inApp" in body and not isinstance(body["inApp"], bool):
        raise HTTPException(422, "inApp must be boolean")
    if "states" in body and (
        not isinstance(body["states"], list)
        or len(body["states"]) > 8
        or any(not isinstance(v, str) for v in body["states"])
    ):
        raise HTTPException(422, "states must be an array of up to 8 names")
    account.preferences = {**account.preferences, **body}
    return public_user(account)


@app.get("/api/records/{kind}")
def records(
    kind: str,
    limit: int = 100,
    offset: int = 0,
    q: str = "",
    account=Depends(user),
    db=Depends(db_session),
):
    if kind not in KINDS:
        raise HTTPException(404, "Unknown collection")
    if kind in ("predictions", "deployments") and account.role == "citizen":
        raise HTTPException(403, "Official access required")
    query = select(Record).where(Record.kind == kind)
    if kind in ("reports", "notifications") and account.role == "citizen":
        query = query.where(Record.owner_id == account.id)
    if kind == "notifications":
        query = query.where(Record.owner_id == account.id)
    if kind == "alerts" and account.role == "citizen":
        query = query.where(Record.data["status"].astext == "Published")
    if q:
        query = query.where(
            Record.data.cast(__import__("sqlalchemy").String).ilike("%" + q[:100] + "%")
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.order_by(Record.created.desc())
        .limit(min(max(limit, 1), 500))
        .offset(max(offset, 0))
    ).all()
    return {
        "items": [serial(r) for r in items],
        "total": total,
        "limit": min(max(limit, 1), 500),
        "offset": max(offset, 0),
    }


@app.post("/api/records/{kind}", status_code=201)
def create_record(
    kind: str, body: dict, account=Depends(official), db=Depends(db_session)
):
    if kind not in WRITABLE:
        raise HTTPException(403, "Use the dedicated workflow for this collection")
    data = valid_record(kind, body.copy())
    if kind == "alerts":
        loc = get_record(db, data["locationId"], "locations")
        data.update(status="Draft", lat=loc.lat, lng=loc.lng)
    if kind == "teams":
        data["status"] = "Available"
    r = add_record(db, kind, data, account.id)
    audit(db, account, "create:" + kind, r.id)
    return serial(r)


@app.patch("/api/records/{kind}/{id}")
def update_record(
    kind: str, id: str, body: dict, account=Depends(official), db=Depends(db_session)
):
    if kind not in WRITABLE:
        raise HTTPException(403, "Use the dedicated workflow")
    r = db.scalar(select(Record).where(Record.id == id).with_for_update())
    if not r or r.kind != kind:
        raise HTTPException(404, "Record not found")
    if kind == "teams":
        raise HTTPException(403, "Team status changes through deployment transitions")
    if kind == "alerts" and r.data.get("status") == "Published":
        raise HTTPException(
            409, "Published warnings cannot be edited; resolve and create a new warning"
        )
    data = valid_record(kind, {**r.data, **body})
    if kind == "alerts":
        loc = get_record(db, data["locationId"], "locations")
        data.update(status="Draft", lat=loc.lat, lng=loc.lng)
        data.pop("reviewNote", None)
    r.data = data
    r.lat = data.get("lat")
    r.lng = data.get("lng")
    r.updated = now()
    audit(db, account, "update:" + kind, id)
    return serial(r)


@app.post("/api/reports", status_code=201)
def submit_report(body: ReportInput, account=Depends(user), db=Depends(db_session)):
    # Serialize retries for a user/device key, including requests arriving simultaneously.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": account.id + body.clientId},
    )
    existing = db.scalar(
        select(Record).where(
            Record.owner_id == account.id, Record.client_id == body.clientId
        )
    )
    if existing:
        return serial(existing)
    data = body.model_dump()
    data.update(
        status="Awaiting Verification",
        reporter=account.name,
        reporterRole=account.role,
        source="User submitted; unverified",
        simulated=False,
    )
    r = add_record(db, "reports", data, account.id, body.clientId)
    audit(db, account, "report:submit", r.id)
    return serial(r)


@app.patch("/api/reports/{id}/verify")
def verify_report(
    id: str, body: Verification, account=Depends(official), db=Depends(db_session)
):
    r = db.scalar(
        select(Record)
        .where(Record.id == id, Record.kind == "reports")
        .with_for_update()
    )
    if not r:
        raise HTTPException(404, "Report not found")
    if body.status == "Resolved" and r.data["status"] != "Verified":
        raise HTTPException(409, "Verify a report before resolving it")
    if r.data["status"] in ("Resolved", "Rejected"):
        raise HTTPException(409, "Report review is already final")
    r.data = {
        **r.data,
        "status": body.status,
        "verificationNote": body.note,
        "verifiedBy": account.name,
    }
    r.updated = now()
    audit(db, account, "report:" + body.status, id)
    return serial(r)


@app.post("/api/reports/{id}/media", status_code=201)
async def upload(
    id: str, file: UploadFile = File(...), account=Depends(user), db=Depends(db_session)
):
    r = get_record(db, id, "reports")
    report_access(r, account)
    if r.owner_id != account.id:
        raise HTTPException(403, "Only the report author can attach media")
    content = await file.read(10_000_001)
    if not content or len(content) > 10_000_000:
        raise HTTPException(413, "Media must be between 1 byte and 10 MB")
    digest = hashlib.sha256(content).hexdigest()
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": "media-owner-" + account.id},
    )
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": id})
    existing = db.scalar(
        select(Attachment).where(
            Attachment.report_id == id, Attachment.sha256 == digest
        )
    )
    if existing:
        return {
            "id": existing.id,
            "filename": existing.filename,
            "processing": existing.processing,
        }
    if (
        db.scalar(
            select(func.count())
            .select_from(Attachment)
            .where(Attachment.report_id == id)
        )
        >= 5
    ):
        raise HTTPException(413, "Maximum 5 attachments per report")
    used = db.scalar(
        select(func.coalesce(func.sum(func.octet_length(Attachment.content)), 0))
        .join(Record, Attachment.report_id == Record.id)
        .where(Record.owner_id == account.id)
    )
    if used + len(content) > 100_000_000:
        raise HTTPException(413, "Account media quota is 100 MB")
    processing = {}
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        mime = "image/webp"
    elif len(content) > 12 and content[4:8] == b"ftyp":
        mime = "video/mp4"
    else:
        raise HTTPException(422, "Supported formats: JPEG, PNG, WebP, MP4")
    if mime.startswith("image/"):
        os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "25000000")
        try:
            image = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
        except cv2.error:
            image = None
        if image is None or image.shape[0] * image.shape[1] > 25_000_000:
            raise HTTPException(422, "Invalid image or image exceeds 25 megapixels")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        processing = {
            "width": image.shape[1],
            "height": image.shape[0],
            "brightness": round(float(gray.mean()), 2),
            "sharpness": round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2),
            "edgeFraction": round(float((cv2.Canny(gray, 100, 200) > 0).mean()), 4),
            "method": "OpenCV image quality measurements",
            "classification": "Not configured; no landslide classification is inferred",
        }
    media = Attachment(
        report_id=id,
        filename=Path(file.filename or "upload").name[:150],
        mime=mime,
        sha256=digest,
        content=content,
        processing=processing,
    )
    db.add(media)
    db.flush()
    audit(db, account, "media:upload", id)
    return {"id": media.id, "filename": media.filename, "processing": processing}


@app.get("/api/reports/{id}/media")
def report_media(id: str, account=Depends(user), db=Depends(db_session)):
    report_access(get_record(db, id, "reports"), account)
    return {
        "items": [
            {
                "id": m.id,
                "filename": m.filename,
                "mime": m.mime,
                "processing": m.processing,
            }
            for m in db.scalars(select(Attachment).where(Attachment.report_id == id))
        ]
    }


@app.get("/api/media/{id}")
def media_file(id: str, account=Depends(user), db=Depends(db_session)):
    m = db.get(Attachment, id)
    if not m:
        raise HTTPException(404, "Media not found")
    report_access(get_record(db, m.report_id, "reports"), account)
    return Response(
        content=m.content,
        media_type=m.mime,
        headers={"Content-Disposition": "attachment; filename=attachment"},
    )


@app.post("/api/sync")
def sync(body: dict, account=Depends(user), db=Depends(db_session)):
    if not isinstance(body.get("reports"), list) or len(body["reports"]) > 100:
        raise HTTPException(422, "Expected up to 100 reports")
    results = []
    for item in body["reports"]:
        try:
            with db.begin_nested():
                r = submit_report(ReportInput.model_validate(item), account, db)
                results.append({"clientId": item["clientId"], "ok": True, "report": r})
        except Exception as exc:
            if not isinstance(exc, (HTTPException, ValueError)):
                raise
            results.append(
                {
                    "clientId": (
                        item.get("clientId") if isinstance(item, dict) else None
                    ),
                    "ok": False,
                    "error": str(getattr(exc, "detail", exc)),
                }
            )
    return {"results": results}


@app.get("/api/gis")
def gis(
    layers: str = "locations,roads,villages,infrastructure,history,sensors",
    bbox: str | None = None,
    account=Depends(user),
    db=Depends(db_session),
):
    selected = set(layers.split(",")) & {
        "locations",
        "roads",
        "villages",
        "infrastructure",
        "history",
        "sensors",
        "satellite",
    }
    query = select(Record).where(Record.kind.in_(selected), Record.lat.isnot(None))
    if bbox:
        try:
            west, south, east, north = map(float, bbox.split(","))
            if not all(map(math.isfinite, [west, south, east, north])) or not (
                -180 <= west <= east <= 180 and -90 <= south <= north <= 90
            ):
                raise ValueError()
        except ValueError:
            raise HTTPException(422, "bbox must be west,south,east,north")
        query = query.where(
            text("ST_Intersects(geom::geometry, ST_MakeEnvelope(:w,:s,:e,:n,4326))")
        ).params(w=west, s=south, e=east, n=north)
    items = db.scalars(query.limit(2000)).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r.lng, r.lat]},
                "properties": serial(r),
            }
            for r in items
        ],
        "limit": 2000,
    }


@app.get("/api/exposure/{id}")
def exposure(
    id: str, radius: int = 5000, account=Depends(user), db=Depends(db_session)
):
    loc = get_record(db, id, "locations")
    if loc.lat is None:
        raise HTTPException(422, "Location has no coordinates")
    if not 100 <= radius <= 50000:
        raise HTTPException(422, "Radius must be 100–50000 metres")
    nearby = db.scalars(
        select(Record)
        .where(
            Record.kind.in_(["villages", "infrastructure", "roads"]),
            text(
                "ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, :radius)"
            ),
        )
        .params(lng=loc.lng, lat=loc.lat, radius=radius)
    ).all()
    cells = [r for r in nearby if r.kind == "villages"]
    return {
        "locationId": id,
        "radiusM": radius,
        "approximatePopulation": (
            sum(r.data.get("population", 0) for r in cells) if cells else None
        ),
        "simulated": any(r.data.get("simulated", False) for r in cells),
        "populationRecords": len(cells),
        "items": [serial(r) for r in nearby],
        "method": "Sum of population counts at imported cell/settlement centres inside a geodesic radius; approximate, not individual exposure or a landslide footprint.",
        "sources": list({r.data.get("source", "Unknown") for r in cells}),
    }


@app.get("/api/dashboard")
def dashboard(account=Depends(user), db=Depends(db_session)):
    counts = dict(
        db.execute(select(Record.kind, func.count()).group_by(Record.kind)).all()
    )
    reports = select(Record).where(Record.kind == "reports")
    if account.role == "citizen":
        reports = reports.where(Record.owner_id == account.id)
    counts["reports"] = db.scalar(select(func.count()).select_from(reports.subquery()))
    active = select(Record).where(
        Record.kind == "alerts", Record.data["status"].astext == "Published"
    )
    counts["publishedAlerts"] = db.scalar(
        select(func.count()).select_from(active.subquery())
    )
    return {
        "counts": counts,
        "sampleRecords": db.scalar(
            select(func.count())
            .select_from(Record)
            .where(Record.data["simulated"].astext == "true")
        ),
        "modelConfigured": bool(os.environ.get("RF_MODEL_PATH")),
        "notice": "Records may include labelled samples. Counts are stored records, not regional totals.",
    }


@app.get("/api/weather/{id}")
def weather(id: str, account=Depends(user), db=Depends(db_session)):
    get_record(db, id, "locations")
    r = db.get(Record, "weather-" + id)
    if not r:
        return {
            "available": False,
            "message": "No cached forecast. Refresh when online; no weather values are fabricated.",
        }
    return {
        **r.data,
        "available": True,
        "stale": now() - r.updated > 3600,
        "updatedAt": r.updated,
    }


@app.post("/api/weather/{id}/sample")
def load_sample_weather(
    id: str, body: dict, account=Depends(official), db=Depends(db_session)
):
    get_record(db, id, "locations")
    # Serialize explicit cache replacement against concurrent live refreshes.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "weather-" + id}
    )
    r = db.get(Record, "weather-" + id)
    if r and not r.data.get("simulated") and body.get("replaceLive") is not True:
        raise HTTPException(
            409,
            "A live forecast is cached. Confirm replacement before loading sample weather.",
        )
    data = sample_weather(now())
    if r:
        r.data = data
        r.updated = now()
    else:
        r = add_record(db, "weather", data, id="weather-" + id)
    audit(db, account, "weather:sample", id)
    return {**data, "available": True, "stale": False, "updatedAt": r.updated}


@app.post("/api/weather/{id}/refresh")
def refresh_weather(id: str, account=Depends(official), db=Depends(db_session)):
    loc = get_record(db, id, "locations")
    try:
        with httpx.Client(timeout=20, verify=True) as client:
            response = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": loc.lat,
                    "longitude": loc.lng,
                    "hourly": "precipitation,temperature_2m,relative_humidity_2m",
                    "past_days": 3,
                    "forecast_days": 3,
                    "timezone": "UTC",
                },
            )
            response.raise_for_status()
            data = response.json()
        hourly = data["hourly"]
        hours = hourly["time"]
        rain = hourly["precipitation"]
        if not hours or any(
            len(hourly[k]) != len(hours)
            for k in ("precipitation", "temperature_2m", "relative_humidity_2m")
        ):
            raise ValueError("Invalid forecast response")
        from datetime import datetime, timezone

        parsed = [
            datetime.fromisoformat(t).replace(tzinfo=timezone.utc).timestamp()
            for t in hours
        ]

        if len(set(parsed)) != len(parsed) or parsed != sorted(parsed):
            raise ValueError("Forecast timestamps must be unique and ordered")

        def total(a, b):
            values = [v for t, v in zip(parsed, rain) if a <= t < b]
            if len(values) != round((b - a) / 3600) or any(
                not isinstance(v, (int, float)) or not math.isfinite(v) for v in values
            ):
                return None
            return sum(values)

        current = now()
        result = {
            "source": "Open-Meteo forecast model (includes modelled past hours; not a rain gauge)",
            "attribution": "Weather data by Open-Meteo.com, CC BY 4.0",
            "simulated": False,
            "rainfall24h": total(current - 86400, current),
            "rainfall72h": total(current - 259200, current),
            "forecast24h": total(current, current + 86400),
            "hourly": [
                {"time": t, "rainfall": r, "temperature": temp, "humidity": hum}
                for t, r, temp, hum in zip(
                    hours,
                    rain,
                    hourly["temperature_2m"],
                    hourly["relative_humidity_2m"],
                )
            ],
            "units": {"rainfall": "mm", "temperature": "°C", "humidity": "%"},
        }
    except Exception as exc:
        raise HTTPException(
            502,
            "Weather provider unavailable; cached values, if any, are retained. Check network access to api.open-meteo.com.",
        ) from exc
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "weather-" + id}
    )
    r = db.get(Record, "weather-" + id)
    if not r:
        r = add_record(db, "weather", result, id="weather-" + id)
    else:
        r.data = result
        r.updated = now()
    audit(db, account, "weather:refresh", id)
    return {**result, "available": True, "stale": False, "updatedAt": r.updated}


@app.get("/api/model")
def model_status(account=Depends(user)):
    try:
        _, metadata = load_model()
        return {
            "available": True,
            "features": FEATURES,
            "version": metadata["version"],
            "training": "External model team only",
        }
    except HTTPException as exc:
        return {
            "available": False,
            "features": FEATURES,
            "message": exc.detail,
            "training": "External model team only",
        }


@app.post("/api/predictions", status_code=201)
def prediction(
    body: PredictionInput, account=Depends(official), db=Depends(db_session)
):
    get_record(db, body.locationId, "locations")
    if not now() - 86400 <= body.observedAt <= now() + 300:
        raise HTTPException(422, "Current inputs must be within the past 24 hours")
    result = predict(body.inputs)
    r = add_record(
        db,
        "predictions",
        {**body.model_dump(), **result, "simulated": False},
        account.id,
    )
    audit(db, account, "prediction", r.id)
    return serial(r)


@app.post("/api/sensors/simulate")
def simulate(account=Depends(official), db=Depends(db_session)):
    locs = db.scalars(select(Record).where(Record.kind == "locations").limit(50)).all()
    if not locs:
        raise HTTPException(409, "Create monitoring locations first")
    for loc in locs:
        sid = "sim-" + loc.id
        rainfall24 = round(secrets.randbelow(3000) / 10, 1)
        data = {
            "name": loc.data["name"] + " demonstration station",
            "locationId": loc.id,
            "lat": loc.lat,
            "lng": loc.lng,
            "value": rainfall24,
            "unit": "mm/24h",
            "rainfall72hMm": round(rainfall24 + secrets.randbelow(6000) / 10, 1),
            "soilMoisturePercent": round(secrets.randbelow(1000) / 10, 1),
            "groundMovementMmPerHour": round(secrets.randbelow(100) / 10, 1),
            "slopeDegrees": loc.data.get("slope"),
            "feature": "rainfall24h",
            "source": "Synthetic sensor demonstration",
            "simulated": True,
            "status": "Simulated",
            "observedAt": now(),
        }
        r = db.get(Record, sid)
        if r:
            r.data = data
            r.updated = now()
        else:
            add_record(db, "sensors", data, id=sid)
        # Bounded retained history: current sample and up to 1000 recent readings globally.
        add_record(db, "readings", data, account.id)
    old = db.scalars(
        select(Record)
        .where(Record.kind == "readings")
        .order_by(Record.created.desc())
        .offset(1000)
    ).all()
    for r in old:
        db.delete(r)
    audit(db, account, "sensor:simulate", str(len(locs)))
    return {
        "updated": len(locs),
        "simulated": True,
        "notice": "No physical sensors are connected and no predictions or warnings were generated.",
    }


@app.post("/api/alerts/{id}/{action}")
def alert_action(
    id: str, action: str, body: dict, account=Depends(official), db=Depends(db_session)
):
    r = db.scalar(
        select(Record).where(Record.id == id, Record.kind == "alerts").with_for_update()
    )
    if not r:
        raise HTTPException(404, "Alert not found")
    state = r.data.get("status")
    transitions = {
        "approve": ("Draft", "Approved"),
        "publish": ("Approved", "Published"),
        "resolve": ("Published", "Resolved"),
    }
    if action not in transitions:
        raise HTTPException(404, "Unknown alert action")
    before, after = transitions[action]
    if state == after:
        return serial(r)
    if state != before:
        raise HTTPException(409, f"Alert must be {before} first")
    if len(str(body.get("note", "")).strip()) < 5:
        raise HTTPException(422, "A review note of at least 5 characters is required")
    r.data = {
        **r.data,
        "status": after,
        "reviewNote": body["note"],
        "reviewedBy": account.name,
    }
    r.updated = now()
    if action == "publish":
        for u in db.scalars(select(User).where(User.active == True)):
            prefs = u.preferences
            loc = get_record(db, r.data["locationId"], "locations")
            if prefs.get("inApp", True) and (
                not prefs.get("states") or loc.data.get("state") in prefs["states"]
            ):
                add_record(
                    db,
                    "notifications",
                    {
                        "alertId": r.id,
                        "name": r.data["name"],
                        "description": r.data["description"],
                        "action": r.data["action"],
                        "simulated": r.data["simulated"],
                        "source": r.data["source"],
                        "read": False,
                    },
                    u.id,
                )
    audit(db, account, "alert:" + action, id)
    return serial(r)


@app.post("/api/notifications/{id}/read")
def mark_read(id: str, account=Depends(user), db=Depends(db_session)):
    r = get_record(db, id, "notifications")
    if r.owner_id != account.id:
        raise HTTPException(404, "Notification not found")
    r.data = {**r.data, "read": True}
    return serial(r)


@app.get("/api/response/priorities")
def priorities(account=Depends(official), db=Depends(db_session)):
    items = []
    for loc in db.scalars(select(Record).where(Record.kind == "locations")):
        ex = exposure(loc.id, 5000, account, db)
        blocked = sum(
            r["kind"] == "roads" and r.get("status") == "Blocked" for r in ex["items"]
        )
        # Explicit planning heuristic, never an ML prediction.
        score = min(
            100,
            {"Low": 10, "Moderate": 30, "High": 55, "Critical": 75}.get(
                loc.data.get("level"), 10
            )
            + (
                min(15, ex["approximatePopulation"] / 1000)
                if ex["approximatePopulation"] is not None
                else 0
            )
            + blocked * 10,
        )
        items.append(
            {
                **serial(loc),
                "priorityScore": round(score, 1),
                "exposure": ex["approximatePopulation"],
                "blockedRoads": blocked,
                "incompletePopulationData": ex["approximatePopulation"] is None,
                "method": "Planning heuristic: reviewed level + approximate population + blocked roads. Not a prediction.",
            }
        )
    return {"items": sorted(items, key=lambda v: v["priorityScore"], reverse=True)}


@app.post("/api/deployments", status_code=201)
def deploy(body: dict, account=Depends(official), db=Depends(db_session)):
    team = db.scalar(
        select(Record)
        .where(Record.id == body.get("teamId"), Record.kind == "teams")
        .with_for_update()
    )
    if not team:
        raise HTTPException(404, "Team not found")
    loc = get_record(db, body.get("locationId"), "locations")
    if team.data.get("status") != "Available":
        raise HTTPException(409, "Team is already assigned")
    team.data = {**team.data, "status": "En Route"}
    team.updated = now()
    r = add_record(
        db,
        "deployments",
        {
            "teamId": team.id,
            "team": team.data["name"],
            "locationId": loc.id,
            "location": loc.data["name"],
            "status": "En Route",
            "notes": str(body.get("notes", ""))[:2000],
            "source": "Official assignment",
            "simulated": bool(team.data.get("simulated") or loc.data.get("simulated")),
        },
        account.id,
    )
    audit(db, account, "deployment:create", r.id)
    return serial(r)


@app.post("/api/deployments/{id}/status")
def deployment_status(
    id: str, body: dict, account=Depends(official), db=Depends(db_session)
):
    r = db.scalar(
        select(Record)
        .where(Record.id == id, Record.kind == "deployments")
        .with_for_update()
    )
    if not r:
        raise HTTPException(404, "Deployment not found")
    status = body.get("status")
    current = r.data["status"]
    if status not in {
        "En Route": ["On Site", "Cancelled"],
        "On Site": ["Completed", "Cancelled"],
    }.get(current, []):
        raise HTTPException(409, "Invalid deployment transition")
    team = db.scalar(
        select(Record).where(Record.id == r.data["teamId"]).with_for_update()
    )
    r.data = {**r.data, "status": status}
    r.updated = now()
    team.data = {
        **team.data,
        "status": "Available" if status in ("Completed", "Cancelled") else "Deployed",
    }
    team.updated = now()
    audit(db, account, "deployment:" + status, id)
    return serial(r)


@app.get("/api/analytics")
def analytics(account=Depends(official), db=Depends(db_session)):
    all_records = db.scalars(
        select(Record).where(
            Record.kind.in_(["history", "reports", "locations", "alerts"])
        )
    ).all()
    states = {}
    statuses = {}
    months = {}
    from datetime import datetime, timezone

    for r in all_records:
        if r.kind == "locations":
            states[r.data.get("state", "Unknown")] = (
                states.get(r.data.get("state", "Unknown"), 0) + 1
            )
        if r.kind == "reports":
            statuses[r.data["status"]] = statuses.get(r.data["status"], 0) + 1
        if r.kind == "history":
            try:
                month = datetime.fromtimestamp(
                    float(r.data["observedAt"]), timezone.utc
                ).strftime("%Y-%m")
            except (ValueError, TypeError, OverflowError):
                continue
            months[month] = months.get(month, 0) + 1
    return {
        "states": [{"name": k, "count": v} for k, v in states.items()],
        "reports": [{"name": k, "count": v} for k, v in statuses.items()],
        "history": [{"name": k, "count": v} for k, v in sorted(months.items())],
        "notice": "Counts describe imported/stored records only. Sample records are included and labelled in downloads.",
    }


@app.get("/api/export/{kind}")
def export(kind: str, account=Depends(official), db=Depends(db_session)):
    if kind not in KINDS - {"notifications"}:
        raise HTTPException(404, "Unknown export")
    rows = [
        serial(r)
        for r in db.scalars(select(Record).where(Record.kind == kind).limit(10000))
    ]
    keys = sorted({k for r in rows for k in r}) or ["id", "kind"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=keys)
    writer.writeheader()
    for row in rows:
        safe = {}
        for k, v in row.items():
            value = (
                json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            )
            if isinstance(value, str) and value.lstrip().startswith(
                ("=", "+", "-", "@", "\t", "\r")
            ):
                value = "'" + value
            safe[k] = value
        writer.writerow(safe)
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="ashtaraksha-{kind}.csv"'
        },
    )


@app.get("/api/admin/users")
def users(account=Depends(admin), db=Depends(db_session)):
    return {
        "items": [
            public_user(u) for u in db.scalars(select(User).order_by(User.created))
        ]
    }


@app.patch("/api/admin/users/{id}")
def update_user(id: str, body: dict, account=Depends(admin), db=Depends(db_session)):
    u = db.get(User, id)
    if not u:
        raise HTTPException(404, "User not found")
    if set(body) - {"role", "active"} or not body:
        raise HTTPException(422, "Only role and active may be changed")
    if body.get("role", u.role) not in ("citizen", "official", "admin"):
        raise HTTPException(422, "Invalid role")
    if "active" in body and not isinstance(body["active"], bool):
        raise HTTPException(422, "active must be boolean")
    if id == account.id:
        raise HTTPException(409, "Cannot change your own role or deactivate yourself")
    u.role = body.get("role", u.role)
    u.active = body.get("active", u.active)
    for s in db.scalars(select(LoginSession).where(LoginSession.user_id == id)):
        db.delete(s)
    audit(db, account, "user:update", id)
    return public_user(u)


@app.get("/api/admin/system")
def system(account=Depends(admin), db=Depends(db_session)):
    return {
        "health": health(db),
        "model": model_status(account),
        "notificationMode": "In-app only; no external SMS is sent",
        "audit": [
            {"actor": a.actor, "action": a.action, "target": a.target, "at": a.at}
            for a in db.scalars(select(Audit).order_by(Audit.at.desc()).limit(100))
        ],
    }


@app.post("/api/admin/import/{kind}")
def import_records(
    kind: str, body: dict, account=Depends(admin), db=Depends(db_session)
):
    if kind not in {
        "locations",
        "roads",
        "villages",
        "infrastructure",
        "history",
        "satellite",
    }:
        raise HTTPException(422, "Unsupported import collection")
    items = body.get("items")
    if body.get("type") == "FeatureCollection":
        items = []
        features = body.get("features")
        if not isinstance(features, list) or not 1 <= len(features) <= 500:
            raise HTTPException(422, "Expected 1–500 GeoJSON features")
        for feature in features:
            if not isinstance(feature, dict) or not isinstance(
                feature.get("properties"), dict
            ):
                raise HTTPException(422, "Invalid GeoJSON feature properties")
            geometry = feature.get("geometry") or {}
            if not isinstance(geometry, dict):
                raise HTTPException(422, "Invalid GeoJSON geometry")
            if geometry.get("type") != "Point":
                raise HTTPException(
                    422,
                    "Import point GeoJSON; roads use a representative point and descriptive route",
                )
            coords = geometry.get("coordinates")
            if not isinstance(coords, list) or len(coords) < 2:
                raise HTTPException(
                    422, "Point coordinates require longitude and latitude"
                )
            lng, lat = coords[:2]
            items.append({**feature.get("properties", {}), "lat": lat, "lng": lng})
    if not isinstance(items, list) or not 1 <= len(items) <= 500:
        raise HTTPException(422, "Import 1–500 records per batch")
    if any(not isinstance(item, dict) for item in items):
        raise HTTPException(422, "Each imported item must be an object")
    validated = [valid_record(kind, item.copy()) for item in items]
    # Stable import key prevents duplicate records when exactly the same batch is retried.
    inserted = 0
    for data in validated:
        id = (
            "import-"
            + hashlib.sha256(
                (kind + json.dumps(data, sort_keys=True)).encode()
            ).hexdigest()
        )
        if not db.get(Record, id):
            add_record(db, kind, data, id=id)
            inserted += 1
    audit(db, account, "import:" + kind, str(inserted))
    return {"inserted": inserted, "unchanged": len(items) - inserted}
