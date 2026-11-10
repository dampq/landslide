import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text
from api.db import migrate, engine, Session, User
from api.security import hash_password
from manage import seed

if not os.environ.get("DATABASE_URL", "").rsplit("/", 1)[-1].endswith("_e2e_test"):
    raise SystemExit("Use an isolated _e2e_test database")
migrate()
with engine.begin() as c:
    c.execute(
        text("TRUNCATE attachments,records,sessions,users,audit,login_attempts CASCADE")
    )
seed()
with Session.begin() as db:
    for role in ("citizen", "official", "admin"):
        db.add(
            User(
                email=f"{role}@e2e.test",
                name="E2E " + role,
                password=hash_password("e2e-test-password-only"),
                role=role,
            )
        )
