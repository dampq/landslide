"""PostgreSQL persistence. Schema migrations run explicitly via manage.py migrate."""

import os
import time
import uuid
from sqlalchemy import (
    create_engine,
    String,
    Float,
    ForeignKey,
    LargeBinary,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://ashtaraksha:local-development@127.0.0.1:5433/ashtaraksha",
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)


def uid():
    return str(uuid.uuid4())


def now():
    return time.time()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    password: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="citizen")
    active: Mapped[bool] = mapped_column(default=True)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    created: Mapped[float] = mapped_column(Float, default=now)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    since: Mapped[float] = mapped_column(Float, default=now)


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires: Mapped[float] = mapped_column(Float)


class Record(Base):
    __tablename__ = "records"
    __table_args__ = (
        UniqueConstraint("owner_id", "client_id", name="report_retry_unique"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String, index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    created: Mapped[float] = mapped_column(Float, default=now)
    updated: Mapped[float] = mapped_column(Float, default=now)


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        UniqueConstraint("report_id", "sha256", name="media_retry_unique"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    report_id: Mapped[str] = mapped_column(ForeignKey("records.id"))
    filename: Mapped[str] = mapped_column(String)
    mime: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    processing: Mapped[dict] = mapped_column(JSONB, default=dict)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    actor: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String)
    at: Mapped[float] = mapped_column(Float, default=now)


def migrate():
    # Idempotent first migration; subsequent schema changes require new numbered migrations.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text("SELECT pg_advisory_xact_lock(18752401)"))
        Base.metadata.create_all(conn)
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, applied_at timestamptz DEFAULT now())"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE records ADD COLUMN IF NOT EXISTS geom geography(Point,4326) GENERATED ALWAYS AS (CASE WHEN lat IS NOT NULL AND lng IS NOT NULL THEN ST_SetSRID(ST_MakePoint(lng,lat),4326)::geography END) STORED"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS records_geom_idx ON records USING gist(geom)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO schema_migrations(version) VALUES (1) ON CONFLICT DO NOTHING"
            )
        )


def wait_for_database(timeout=60, interval=1):
    """Probe the application's real TCP/credential path, not the init Unix socket."""
    probe = create_engine(
        DATABASE_URL, connect_args={"connect_timeout": 3}, poolclass=NullPool
    )
    deadline = time.monotonic() + timeout
    announced = False
    try:
        while True:
            try:
                with probe.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return
            except OperationalError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError(
                        "PostgreSQL did not accept an authenticated application connection. "
                        "Inspect docker compose logs --tail=80 db and verify DATABASE_URL. "
                        "Do not delete the database volume."
                    ) from None
                if not announced:
                    print(
                        "Waiting for PostgreSQL to accept an authenticated connection...",
                        flush=True,
                    )
                    announced = True
                time.sleep(min(interval, remaining))
    finally:
        probe.dispose()
