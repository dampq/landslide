import hashlib
import hmac
import secrets
from fastapi import HTTPException, Request, Depends
from sqlalchemy import select
from .db import Session, User, LoginSession, Audit, now


def hash_password(value: str):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(
        value.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
    ).hex()
    return f"{salt}:{digest}"


def verify_password(value, stored):
    salt, digest = stored.split(":")
    actual = hashlib.scrypt(
        value.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
    ).hex()
    return hmac.compare_digest(actual, digest)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def db_session():
    with Session() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def user(request: Request, db=Depends(db_session)):
    token = request.cookies.get("ashtaraksha_session", "")
    session = db.get(LoginSession, token_hash(token)) if token else None
    account = (
        db.get(User, session.user_id) if session and session.expires > now() else None
    )
    if not account or not account.active:
        raise HTTPException(401, "Please sign in")
    return account


def official(account=Depends(user)):
    if account.role not in ("official", "admin"):
        raise HTTPException(403, "Field official or administrator access required")
    return account


def admin(account=Depends(user)):
    if account.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return account


def public_user(account):
    return {
        k: getattr(account, k)
        for k in ("id", "email", "name", "role", "active", "preferences")
    }


def audit(db, actor, action, target):
    db.add(Audit(actor=actor.id if actor else None, action=action, target=str(target)))
