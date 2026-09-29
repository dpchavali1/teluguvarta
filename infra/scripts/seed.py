"""Seed script — run after migrations.

Seeds one admin user (for T05 local login), the T07 starter source registry
(3 LINK_ONLY government/news feeds with rights evidence already on file —
ADR-002: no source may be enabled without it), the §3.3 interest taxonomy as
`Topic` rows, and one demo `PUBLISHED` story (T14: apps/web's acceptance
criteria is real data "for at least one seeded story" — this is that
story). Idempotent throughout: re-running updates existing rows by natural
key rather than erroring or duplicating.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

# §3.3 interest taxonomy.
SEED_TOPICS = [
    ("immigration", "Immigration"),
    ("money", "Money"),
    ("andhra-pradesh", "Andhra Pradesh"),
    ("telangana", "Telangana"),
    ("hyderabad", "Hyderabad"),
    ("jobs", "Jobs"),
    ("property", "Property"),
    ("education", "Education"),
    ("parents", "Parents"),
    ("travel", "Travel"),
    ("community", "Community"),
    ("entertainment", "Entertainment"),
    ("sports", "Sports"),
]

# S2 (docs/tickets/S2.md) / §3.1's student topic taxonomy — plain `Topic`
# rows, same table as SEED_TOPICS above (no separate topic model), so they
# flow through the existing ranking/notification/onboarding code unchanged.
# `packages/domain`'s `STUDENT_TOPIC_SLUGS` is the client-side grouping list
# used to label these separately in onboarding/settings UI; keep the two in
# sync. §3.1 also lists "travel" as a student topic, but that's the same
# concept as the general "Travel" topic above, not a duplicate row.
STUDENT_SEED_TOPICS = [
    ("f1", "F-1"),
    ("cpt", "CPT"),
    ("opt", "OPT"),
    ("stem-opt", "STEM OPT"),
    ("h1b-transition", "H-1B Transition"),
    ("internships", "Internships"),
    ("university-policy", "University Policy"),
    ("campus-safety", "Campus Safety"),
    ("taxes", "Taxes"),
    ("housing", "Housing"),
    ("scholarships", "Scholarships"),
    ("student-community", "Student Community"),
    ("international-student-jobs", "International Student Jobs"),
]

DEMO_STORY_SLUG = "demo-h1b-visa-fee-update"

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
            "public_domain_basis": "U.S. federal government work, 17 U.S.C. §105",
        },
        # ADR-020: store the advisory text as internal evidence (never shown).
        "description_evidence": True,
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

    from app.models import Source, SourceItem, Story, StorySource, StoryTopic, StoryVariant, Topic, User
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
            source.description_evidence = spec.get("description_evidence", False)
            source.active = True
        db.commit()
        print(f"Seeded {len(SEED_SOURCES)} LINK_ONLY sources.")

    with Session(engine) as db:
        all_topics = SEED_TOPICS + STUDENT_SEED_TOPICS
        for slug, name in all_topics:
            topic = db.scalar(select(Topic).where(Topic.slug == slug))
            if topic is None:
                db.add(Topic(id=uuid.uuid4(), slug=slug, name=name, active=True))
            else:
                topic.name = name
                topic.active = True
        db.commit()
        print(f"Seeded {len(all_topics)} topics ({len(STUDENT_SEED_TOPICS)} student).")

    if os.environ.get("SEED_DEMO_STORY", "1") == "0":
        print("SEED_DEMO_STORY=0 — skipping demo story.")
        return 0

    with Session(engine) as db:
        story = db.scalar(select(Story).where(Story.canonical_slug == DEMO_STORY_SLUG))
        if story is not None:
            print(f"Demo story '{DEMO_STORY_SLUG}' already exists — skipping.")
        else:
            source = db.scalar(select(Source).where(Source.name == "NPR News"))
            if source is None:
                print("NPR News source not seeded yet — skipping demo story.")
            else:
                item = SourceItem(
                    id=uuid.uuid4(), source_id=source.id, external_id="seed-demo-item",
                    url="https://www.npr.org/sections/immigration/",
                    title="Demo source item for the seeded story", raw_hash="seed-demo-hash",
                    ingest_status="ARCHIVED",
                )
                db.add(item)
                db.flush()

                story = Story(
                    id=uuid.uuid4(), canonical_slug=DEMO_STORY_SLUG, status="DRAFT",
                    sensitivity="NONE", importance=0.8,
                )
                db.add(story)
                db.flush()
                db.add(StorySource(id=uuid.uuid4(), story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=0))

                topic = db.scalar(select(Topic).where(Topic.slug == "immigration"))
                if topic is not None:
                    db.add(StoryTopic(story_id=story.id, topic_id=topic.id, weight=1))

                db.add(StoryVariant(
                    id=uuid.uuid4(), story_id=story.id, language="en",
                    headline="H-1B visa fee changes: what applicants need to know",
                    summary=(
                        "US Citizenship and Immigration Services has updated H-1B "
                        "filing fees for the upcoming cap season. Employers and "
                        "applicants should review the new fee schedule before "
                        "submitting petitions."
                    ),
                    why_matters=(
                        "If you're on OPT/STEM OPT or your employer is sponsoring an "
                        "H-1B this season, the new fees change your total filing cost "
                        "and the paperwork timeline."
                    ),
                    qa_status="PASSED",
                ))
                db.add(StoryVariant(
                    id=uuid.uuid4(), story_id=story.id, language="te",
                    headline="H-1B వీసా ఫీజు మార్పులు: దరఖాస్తుదారులు తెలుసుకోవలసినవి",
                    summary=(
                        "రాబోయే క్యాప్ సీజన్ కోసం USCIS H-1B దాఖలు రుసుములను నవీకరించింది. "
                        "యజమానులు మరియు దరఖాస్తుదారులు పిటిషన్లు సమర్పించే ముందు కొత్త రుసుము "
                        "షెడ్యూల్‌ను సమీక్షించాలి."
                    ),
                    why_matters=(
                        "మీరు OPT/STEM OPTలో ఉన్నా లేదా మీ యజమాని ఈ సీజన్‌లో H-1B స్పాన్సర్ "
                        "చేస్తున్నా, కొత్త రుసుములు మీ మొత్తం దాఖలు ఖర్చును మరియు కాగితప్పనుల "
                        "కాలక్రమాన్ని మారుస్తాయి."
                    ),
                    qa_status="PASSED",
                ))
                db.flush()

                for intermediate in ("AI_READY", "REVIEW_REQUIRED", "APPROVED", "SCHEDULED", "PUBLISHED"):
                    story.status = intermediate
                    db.flush()
                story.published_at = datetime.now(timezone.utc)
                db.commit()
                print(f"Seeded demo published story '{DEMO_STORY_SLUG}'.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
