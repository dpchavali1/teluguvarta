"""Seed script — run after migrations.

Seeds one admin user (for T05 local login) from ADMIN_SEED_EMAIL/
ADMIN_SEED_PASSWORD, plus the T07 starter source registry — 3 LINK_ONLY
government/news feeds with rights evidence already on file (ADR-002: no
source may be enabled without it). Idempotent throughout: re-running updates
existing rows by natural key rather than erroring or duplicating. Topics
land here once a later ticket needs them.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

# feed_url reachability/shape confirmed 2026-09-08; rights_evidence_url points
# at each publisher's own terms/reuse page and should be re-verified by an
# editor before this source is relied on in production (T08+).
SEED_SOURCES = [
    {
        "name": "NPR News",
        "base_url": "https://www.npr.org",
        "feed_url": "https://feeds.npr.org/1001/rss.xml",
        "source_type": "news",
        "country": "US",
        "language": "en",
        "refresh_minutes": 15,
        "rights_evidence_url": "https://www.npr.org/about-npr/179876898/terms-of-use",
        "reviewer": "seed-script",
        "rights_evidence": {
            "terms_url": "https://www.npr.org/about-npr/179876898/terms-of-use",
            "permitted_fields": ["title", "url", "summary"],
            "restrictions": "Link + original summary only — no reproduced article text (ADR-002)",
            "territory": "US",
        },
    },
    {
        "name": "U.S. Department of State — Travel Advisories",
        "base_url": "https://travel.state.gov",
        "feed_url": "https://travel.state.gov/_res/rss/TAsTWs.xml",
        "source_type": "government",
        "country": "US",
        "language": "en",
        "refresh_minutes": 30,
        "rights_evidence_url": "https://travel.state.gov/content/travel/en/copyright.html",
        "reviewer": "seed-script",
        "rights_evidence": {
            "terms_url": "https://travel.state.gov/content/travel/en/copyright.html",
            "permitted_fields": ["title", "url", "summary"],
            "restrictions": "US government work — link + original summary only (ADR-002)",
            "territory": "Global",
        },
    },
    {
        "name": "FEMA Disaster Declarations",
        "base_url": "https://www.fema.gov",
        "feed_url": "https://www.fema.gov/feeds/disasters.rss",
        "source_type": "government",
        "country": "US",
        "language": "en",
        "refresh_minutes": 60,
        "rights_evidence_url": "https://www.fema.gov/about/privacy-policy",
        "reviewer": "seed-script",
        "rights_evidence": {
            "terms_url": "https://www.fema.gov/about/privacy-policy",
            "permitted_fields": ["title", "url", "summary"],
            "restrictions": "US government work — link + original summary only (ADR-002)",
            "territory": "US",
        },
    },
]


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        return 1

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.models import Source, User
    from app.security import hash_password

    engine = create_engine(database_url)

    admin_email = os.environ.get("ADMIN_SEED_EMAIL")
    admin_password = os.environ.get("ADMIN_SEED_PASSWORD")
    if not admin_email or not admin_password:
        print("ADMIN_SEED_EMAIL/ADMIN_SEED_PASSWORD not set — skipping admin user seed.")
    else:
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

    with Session(engine) as db:
        now = datetime.now(timezone.utc)
        for spec in SEED_SOURCES:
            source = db.scalar(select(Source).where(Source.name == spec["name"]))
            if source is None:
                import uuid

                source = Source(id=uuid.uuid4(), name=spec["name"])
                db.add(source)
            source.base_url = spec["base_url"]
            source.feed_url = spec["feed_url"]
            source.source_type = spec["source_type"]
            source.country = spec["country"]
            source.language = spec["language"]
            source.refresh_minutes = spec["refresh_minutes"]
            source.rights_status = "LINK_ONLY"
            source.rights_evidence_url = spec["rights_evidence_url"]
            source.rights_reviewed_at = now
            source.reviewer = spec["reviewer"]
            source.rights_evidence = spec["rights_evidence"]
            source.active = True
        db.commit()
        print(f"Seeded {len(SEED_SOURCES)} LINK_ONLY sources.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
