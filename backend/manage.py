"""Local administration; no public privilege escalation or model training."""

import argparse
import getpass
from sqlalchemy import select
from api.db import Session, User, Record, LoginSession, migrate, wait_for_database
from api.security import hash_password, audit

STATES = [
    ("Mawsynram", "East Khasi Hills", "Meghalaya", 25.297, 91.582),
    ("Gangtok", "Gangtok", "Sikkim", 27.338, 88.607),
    ("Aizawl", "Aizawl", "Mizoram", 23.727, 92.717),
    ("Kohima", "Kohima", "Nagaland", 25.675, 94.108),
    ("Itanagar", "Papum Pare", "Arunachal Pradesh", 27.084, 93.605),
    ("Haflong", "Dima Hasao", "Assam", 25.17, 93.01),
    ("Imphal", "Imphal West", "Manipur", 24.817, 93.937),
    ("Agartala", "West Tripura", "Tripura", 23.831, 91.287),
]


def seed():
    with Session.begin() as db:
        for i, (name, district, state, lat, lng) in enumerate(STATES):
            common = {
                "source": "Ashtaraksha synthetic demonstration dataset; not a recorded event or live observation",
                "simulated": True,
            }
            locid = f"demo-location-{i}"
            values = {
                locid: (
                    "locations",
                    {
                        "name": name,
                        "district": district,
                        "state": state,
                        "lat": lat,
                        "lng": lng,
                        "level": ["Critical", "High", "Moderate", "Low"][i % 4],
                        "slope": 20 + i * 3,
                    },
                ),
                f"demo-road-{i}": (
                    "roads",
                    {
                        "name": name + " demonstration access road",
                        "route": "Sample route only",
                        "district": district,
                        "lat": lat + 0.005,
                        "lng": lng + 0.005,
                        "status": "Blocked" if i % 3 == 0 else "Open",
                        "locationId": locid,
                    },
                ),
                f"demo-village-{i}": (
                    "villages",
                    {
                        "name": name + " sample population cell",
                        "lat": lat + 0.01,
                        "lng": lng + 0.01,
                        "population": 500 + i * 120,
                        "year": 2026,
                        "resolutionM": 1000,
                        "license": "Synthetic educational data",
                        "locationId": locid,
                    },
                ),
                f"demo-infra-{i}": (
                    "infrastructure",
                    {
                        "name": name + " sample shelter",
                        "type": "Emergency shelter",
                        "lat": lat - 0.01,
                        "lng": lng - 0.01,
                        "locationId": locid,
                    },
                ),
                f"demo-history-{i}": (
                    "history",
                    {
                        "name": "Synthetic monsoon event — " + name,
                        "lat": lat,
                        "lng": lng,
                        "observedAt": 1750000000 + i * 86400 * 15,
                        "description": "Invented record for demonstrating the history module; not a GSI/NRSC event.",
                    },
                ),
                f"demo-team-{i}": (
                    "teams",
                    {
                        "name": name + " demonstration response team",
                        "status": "Available",
                    },
                ),
            }
            for id, (kind, data) in values.items():
                if not db.get(Record, id):
                    data = {**data, **common}
                    db.add(
                        Record(
                            id=id,
                            kind=kind,
                            data=data,
                            lat=data.get("lat"),
                            lng=data.get("lng"),
                        )
                    )
        from datetime import datetime, timezone
        from api.db import now

        for i, (name, *_) in enumerate(STATES):
            weather_id = f"weather-demo-location-{i}"
            if not db.get(Record, weather_id):
                current = int(now() // 3600) * 3600
                hourly = [
                    {
                        "time": datetime.fromtimestamp(
                            current + h * 3600, timezone.utc
                        ).strftime("%Y-%m-%dT%H:%M"),
                        "rainfall": round((h % 7) * 1.2 + i * 0.1, 1),
                        "temperature": 20 + i,
                        "humidity": 80 + i,
                    }
                    for h in range(-72, 49)
                ]
                data = {
                    "source": "Synthetic weather demonstration; not Open-Meteo data",
                    "attribution": "Ashtaraksha educational sample",
                    "simulated": True,
                    "rainfall24h": round(sum(h["rainfall"] for h in hourly[48:72]), 1),
                    "rainfall72h": round(sum(h["rainfall"] for h in hourly[:72]), 1),
                    "forecast24h": round(sum(h["rainfall"] for h in hourly[72:96]), 1),
                    "hourly": hourly,
                    "units": {"rainfall": "mm", "temperature": "°C", "humidity": "%"},
                }
                db.add(Record(id=weather_id, kind="weather", data=data))
        audit(db, None, "seed-demo", "synthetic-records")
    print(
        "Synthetic demonstration records prepared; no accounts, predictions or public warnings created."
    )


def main():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("migrate")
    subs.add_parser("wait-db")
    subs.add_parser("check-services")
    subs.add_parser("seed-demo")
    create = subs.add_parser("create-user")
    create.add_argument("email")
    create.add_argument("--name", required=True)
    create.add_argument(
        "--role", choices=["citizen", "official", "admin"], default="admin"
    )
    promote = subs.add_parser("set-role")
    promote.add_argument("email")
    promote.add_argument("role", choices=["citizen", "official", "admin"])
    password = subs.add_parser("set-password")
    password.add_argument("email")
    args = parser.parse_args()
    if args.command == "check-services":
        import json
        from api.diagnostics import check_services

        result = check_services()
        print(json.dumps(result, indent=2))
        raise SystemExit(
            0 if result["database"]["ok"] and result["weather"]["ok"] else 1
        )
    if args.command == "wait-db":
        try:
            wait_for_database()
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from None
        print("PostgreSQL accepts authenticated application connections.")
        return
    if args.command == "migrate":
        migrate()
        print("PostgreSQL/PostGIS migration 1 applied.")
        return
    if args.command == "seed-demo":
        seed()
        return
    with Session.begin() as db:
        u = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if args.command == "set-role":
            if not u:
                raise SystemExit("Register the account first.")
            u.role = args.role
            audit(db, None, "local:set-role", u.id)
            print("Role updated.")
            return
        if args.command == "set-password":
            if not u:
                raise SystemExit("Account not found. Register or create the account first.")
            pw = getpass.getpass("New password (12–128 characters): ")
            if not 12 <= len(pw) <= 128:
                raise SystemExit("Password must contain 12–128 characters.")
            if pw != getpass.getpass("Confirm new password: "):
                raise SystemExit("Passwords differ. Password was not changed.")
            u.password = hash_password(pw)
            for session in db.scalars(select(LoginSession).where(LoginSession.user_id == u.id)):
                db.delete(session)
            audit(db, None, "local:set-password", u.id)
            print("Password changed. Existing sessions signed out; sign in with the new password.")
            return
        if u:
            raise SystemExit("Account already exists; use set-role.")
        pw = getpass.getpass("Password (at least 12 characters): ")
        if not 12 <= len(pw) <= 128:
            raise SystemExit("Password must contain 12–128 characters.")
        if pw != getpass.getpass("Confirm password: "):
            raise SystemExit("Passwords differ.")
        if "@" not in args.email:
            raise SystemExit("Invalid email")
        u = User(
            email=args.email.strip().lower(),
            name=args.name,
            password=hash_password(pw),
            role=args.role,
        )
        db.add(u)
        db.flush()
        audit(db, None, "local:create-user", u.id)
        print("Account created.")


if __name__ == "__main__":
    main()
