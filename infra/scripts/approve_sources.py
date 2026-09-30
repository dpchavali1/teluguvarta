"""Owner-approved LINK_ONLY Telugu sources (2026-09-30) — run once on the server.

The owner approved these as LINK_ONLY on 2026-09-30 (ADR-002: enabling a source
is the ADMIN rights decision; evidence below comes from
docs/sources/telugu-source-candidates.md, feeds re-fetched the same day). Also
deactivates NPR News, which only added general US news.

Prints the plan by default; writes only with --apply. Idempotent: matches by
name like seed.py. It never re-enables a source that is DISABLED — that may be
a revocation (ADR-023) and is undone only from the admin Sources page.

    docker compose -f infra/deploy/docker-compose.prod.yml --env-file .env.prod \
      run --rm api python /srv/infra/scripts/approve_sources.py --reviewer you@example.com --apply
"""

import argparse
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

_LINK_ONLY = "Link + original summary only; no article text or images (ADR-002)"


def _src(
    name,
    base_url,
    feed_url,
    terms_url,
    notes,
    *,
    category=None,
    refresh=30,
    country="IN",
    language="te",
    source_type="news",
):
    return {
        "name": name,
        "base_url": base_url,
        "feed_url": feed_url,
        "source_type": source_type,
        "country": country,
        "language": language,
        "refresh_minutes": refresh,
        "category": category,
        "rights_evidence_url": terms_url,
        "rights_evidence": {
            "terms_url": terms_url,
            "permitted_fields": ["title", "url", "summary"],
            "restrictions": _LINK_ONLY,
            "territory": "Global",
            "notes": notes,
        },
    }


NTNEWS_TERMS = "https://www.ntnews.com/terms-conditions"
NTNEWS_NOTE = (
    "Terms allow news organizations to link without prior approval; no republishing."
)
USGOV_NOTE = "US federal government work, public domain (usa.gov/government-copyright)."

APPROVED_SOURCES = [
    _src(
        "Namasthe Telangana",
        "https://www.ntnews.com",
        "https://www.ntnews.com/feed",
        NTNEWS_TERMS,
        NTNEWS_NOTE,
    ),
    _src(
        "Namasthe Telangana Hyderabad",
        "https://www.ntnews.com",
        "https://www.ntnews.com/hyderabad/feed",
        NTNEWS_TERMS,
        NTNEWS_NOTE,
        refresh=60,
    ),
    _src(
        "Namasthe Telangana Sports",
        "https://www.ntnews.com",
        "https://www.ntnews.com/sports/feed",
        NTNEWS_TERMS,
        NTNEWS_NOTE,
        category="sports",
        refresh=60,
    ),
    _src(
        "Namasthe Telangana Business",
        "https://www.ntnews.com",
        "https://www.ntnews.com/business/feed",
        NTNEWS_TERMS,
        NTNEWS_NOTE,
        refresh=60,
    ),
    _src(
        "NTV Telugu",
        "https://ntvtelugu.com",
        "https://ntvtelugu.com/feed",
        "https://ntvtelugu.com/terms-conditions",
        "Terms cover IP only; silent on RSS and linking. Robots allows *.",
    ),
    _src(
        "Telugu360",
        "https://www.telugu360.com",
        "https://www.telugu360.com/feed/",
        "https://www.telugu360.com/terms-of-use/",
        "Terms: 'You may read the website and share links to our pages.'",
    ),
    _src(
        "Telangana State Portal",
        "https://www.telangana.gov.in",
        "https://www.telangana.gov.in/feed/",
        "https://www.telangana.gov.in/website-policies/copyright-policy/",
        "Government portal copyright policy.",
        source_type="government",
        language="en",
        refresh=60,
    ),
    _src(
        "123telugu",
        "https://www.123telugu.com",
        "https://www.123telugu.com/feed",
        "https://www.123telugu.com/disclaimer",
        "Only a warranty disclaimer; no copyright, RSS or linking clause.",
        category="entertainment",
        language="en",
    ),
    _src(
        "Telugu Times",
        "https://www.telugutimes.net",
        "https://www.telugutimes.net/feed",
        "https://www.telugutimes.net/terms-and-conditions",
        "US diaspora outlet. Terms bar reproduction; linking not addressed.",
        category="community_events",
        country="US",
    ),
    _src(
        "USCIS News Releases",
        "https://www.uscis.gov",
        "https://www.uscis.gov/news/rss-feed/59144",
        "https://www.uscis.gov/website-policies",
        USGOV_NOTE,
        category="immigration",
        source_type="government",
        country="US",
        language="en",
        refresh=60,
    ),
    _src(
        "Study in the States (DHS)",
        "https://studyinthestates.dhs.gov",
        "https://studyinthestates.dhs.gov/rss.xml",
        "https://www.usa.gov/government-copyright",
        USGOV_NOTE,
        category="immigration",
        source_type="government",
        country="US",
        language="en",
        refresh=60,
    ),
]

DEACTIVATE = ["NPR News"]


def apply(db, reviewer: str, now: datetime) -> list[str]:
    """Stage the changes on `db` (caller commits) and return what was done."""
    from sqlalchemy import select

    from app.models import Source

    log: list[str] = []
    for spec in APPROVED_SOURCES:
        source = db.scalar(select(Source).where(Source.name == spec["name"]))
        if source is not None and source.rights_status == "DISABLED":
            log.append(
                f"skip {spec['name']}: DISABLED (re-enable from the admin Sources page)"
            )
            continue
        if source is None:
            source = Source(id=uuid.uuid4(), name=spec["name"])
            db.add(source)
            log.append(f"add {spec['name']}")
        else:
            log.append(f"update {spec['name']}")
        if source.rights_status != "LINK_ONLY" or not source.active:
            source.rights_reviewed_at = now
            source.reviewer = reviewer
        for field in (
            "base_url",
            "feed_url",
            "source_type",
            "country",
            "language",
            "refresh_minutes",
            "category",
            "rights_evidence_url",
            "rights_evidence",
        ):
            setattr(source, field, spec[field])
        source.rights_status = "LINK_ONLY"
        source.active = True
    for name in DEACTIVATE:
        source = db.scalar(select(Source).where(Source.name == name))
        if source is not None and source.active:
            source.active = False
            log.append(f"deactivate {name}")
    return log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reviewer", required=True, help="the approving ADMIN's email")
    parser.add_argument(
        "--apply", action="store_true", help="write the changes (default: preview)"
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 1

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    with Session(create_engine(database_url)) as db:
        for line in apply(db, args.reviewer.strip().lower(), datetime.now(UTC)):
            print(line)
        if args.apply:
            db.commit()
            print("Applied.")
        else:
            db.rollback()
            print("Preview only; re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
