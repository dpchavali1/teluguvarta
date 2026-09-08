"""Seed script — run after migrations.

Currently seeds one admin user (for T05 local login) from ADMIN_SEED_EMAIL/
ADMIN_SEED_PASSWORD. Idempotent: re-running updates the password hash for an
existing row rather than erroring or duplicating. Topics and LINK_ONLY
sources land here once T06 exists.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        return 1

    admin_email = os.environ.get("ADMIN_SEED_EMAIL")
    admin_password = os.environ.get("ADMIN_SEED_PASSWORD")
    if not admin_email or not admin_password:
        print("ADMIN_SEED_EMAIL/ADMIN_SEED_PASSWORD not set — skipping admin user seed.")
        return 0

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.models import User
    from app.security import hash_password

    engine = create_engine(database_url)
    with Session(engine) as db:
        email = admin_email.strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        password_hash = hash_password(admin_password)
        if user is None:
            import uuid

            db.add(User(id=uuid.uuid4(), email=email, role="ADMIN", password_hash=password_hash))
            print(f"Seeded admin user {email}.")
        else:
            user.role = "ADMIN"
            user.password_hash = password_hash
            print(f"Updated existing admin user {email}.")
        db.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
