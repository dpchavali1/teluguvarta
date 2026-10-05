"""ADR-054: source-text auto-publish for breaking and death stories."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import alerts as alerts_module
from app.jobs.breaking_lane import publisher_domain
from app.jobs.publish import auto_publish_stories, publish_due_stories
from app.jobs.translate import translate_stories
from app.models import (
    AuditEvent,
    ReviewTask,
    RuntimeSwitch,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryVariant,
)

from .test_editorial_workflow import client  # noqa: F401  (fixture)

TITLE = "Veteran actor Ramesh passes away at 80"


@pytest.fixture
def lane_on(monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_BREAKING", "true")
    monkeypatch.delenv("AUTO_PUBLISH_GLOBAL", raising=False)
    for name in ("AUTO_PUBLISH_BREAKING_DAILY_CAP", "BREAKING_MIN_SOURCES", "BREAKING_TRUSTED_SOURCES"):
        monkeypatch.delenv(name, raising=False)
    alerts: list[str] = []
    monkeypatch.setattr(alerts_module, "send_alert", lambda message, **_: alerts.append(message))
    return alerts


def _source(db, host, *, name=None, language="en", category=None, rights="LINK_ONLY", active=True):
    source = Source(
        name=name or host, base_url=f"https://{host}", feed_url=f"https://{host}/rss/{uuid.uuid4()}.xml",
        rights_status=rights, active=active, language=language, category=category,
        rights_reviewed_at=datetime.now(UTC), rights_evidence_url="https://example.org/terms",
    )
    db.add(source)
    db.flush()
    return source


def _story(db, hosts, *, sensitivity="BREAKING", title=TITLE, privacy="UNKNOWN", reason="SENSITIVE_CATEGORY", age_hours=1, **kw):
    story = Story(
        canonical_slug=f"story-{uuid.uuid4()}", status="REVIEW_REQUIRED", sensitivity=sensitivity, privacy_decision=privacy,
    )
    db.add(story)
    db.flush()
    sources = []
    for rank, host in enumerate(hosts, start=1):
        source = _source(db, host, **kw)
        item = SourceItem(
            source_id=source.id, external_id=str(uuid.uuid4()), url=f"https://{host}/a", title=title,
            published_at=datetime.now(UTC) - timedelta(hours=age_hours), raw_hash=str(uuid.uuid4()), ingest_status="REVIEW",
        )
        db.add(item)
        db.flush()
        db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY" if rank == 1 else "SUPPORTING", evidence_rank=rank))
        sources.append((source, item))
    db.add(StoryVariant(story_id=story.id, language="en", headline="AI headline", summary="AI summary", model_version="SUMMARY"))
    db.add(StoryVariant(story_id=story.id, language="te", headline="te ai", summary="te ai"))
    db.add(ReviewTask(story_id=story.id, reason=reason, status="PENDING"))
    db.commit()
    return story, sources


def _events(db, story):
    return db.scalars(select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.actor == "system:breaking_lane")).all()


def test_two_independent_sources_publish_source_text(db_session, lane_on):
    story, _ = _story(db_session, ["news-a.com", "news-b.co.uk"])
    assert auto_publish_stories(db_session) == 1
    db_session.refresh(story)
    assert story.status == "SCHEDULED" and story.format == "BRIEF"

    variants = {v.language: v for v in db_session.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id))}
    assert variants["en"].headline == TITLE and variants["en"].model_version == "source_text"
    assert variants["en"].summary == "Reported by news-a.com. Read the original for details."
    assert "te" not in variants  # no Telugu source headline, so no machine translation

    (event,) = _events(db_session, story)
    assert event.metadata_["basis"] == "INDEPENDENT_SOURCES"
    assert event.metadata_["replaced_draft"]["en"]["headline"] == "AI headline"
    task = db_session.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).one()
    assert task.status == "APPROVED" and task.decision == "AUTO_APPROVED_BREAKING"

    assert len(lane_on) == 1 and TITLE in lane_on[0] and "https://news-a.com/a" in lane_on[0] and str(story.id) in lane_on[0]
    assert publish_due_stories(db_session) == 1


def test_single_untrusted_source_stays_in_review(db_session, lane_on):
    """The hoax case: one source, nobody vouched for it."""
    story, _ = _story(db_session, ["hoax.example"])
    assert auto_publish_stories(db_session) == 0
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED" and story.format == "FULL"
    assert not lane_on


def test_two_feeds_from_one_publisher_count_once(db_session, lane_on):
    story, _ = _story(db_session, ["www.news-a.com", "feeds.news-a.com"])
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


def test_single_trusted_source_publishes(db_session, lane_on, monkeypatch):
    monkeypatch.setenv("BREAKING_TRUSTED_SOURCES", "Trusted Wire, other")
    story, _ = _story(db_session, ["wire.example"], name="Trusted Wire")
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "SCHEDULED"
    assert _events(db_session, story)[0].metadata_["basis"] == "TRUSTED_SOURCE"


def test_telugu_source_headline_becomes_telugu_variant(db_session, lane_on):
    story, _ = _story(db_session, ["news-a.com", "news-b.com"])
    te_source = _source(db_session, "te-news.com", language="te")
    te_item = SourceItem(
        source_id=te_source.id, external_id="te1", url="https://te-news.com/a", title="ప్రముఖ నటుడు రమేష్ కన్నుమూత",
        published_at=datetime.now(UTC), raw_hash="te1", ingest_status="REVIEW",
    )
    db_session.add(te_item)
    db_session.flush()
    db_session.add(StorySource(story_id=story.id, source_item_id=te_item.id, role="SUPPORTING", evidence_rank=3))
    db_session.commit()
    auto_publish_stories(db_session)
    te = db_session.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te")).one()
    assert te.headline == "ప్రముఖ నటుడు రమేష్ కన్నుమూత" and te.model_version == "source_text"


@pytest.mark.parametrize("sensitivity", ["IMMIGRATION", "LEGAL", "FINANCIAL", "OBITUARY_ACCUSATION"])
def test_other_sensitive_categories_stay_in_review(db_session, lane_on, sensitivity):
    story, _ = _story(db_session, ["news-a.com", "news-b.com"], sensitivity=sensitivity)
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


def test_source_in_always_reviewed_category_blocks(db_session, lane_on):
    story, _ = _story(db_session, ["news-a.com", "news-b.com"], category="legal")
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


def test_disabled_source_blocks_and_does_not_count(db_session, lane_on):
    story, sources = _story(db_session, ["news-a.com", "news-b.com"])
    sources[1][0].rights_status = "DISABLED"
    db_session.commit()
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


def test_death_word_hold_with_sensitivity_none_publishes(db_session, lane_on):
    story, _ = _story(db_session, ["news-a.com", "news-b.com"], sensitivity="NONE", privacy="RESTRICTED", reason="AI_RETRIES_EXHAUSTED")
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "SCHEDULED"


def test_sensitivity_none_without_death_signal_stays(db_session, lane_on):
    story, _ = _story(db_session, ["news-a.com", "news-b.com"], sensitivity="NONE", privacy="RESTRICTED", title="Tax slab changes announced")
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


def test_stale_items_stay_in_review(db_session, lane_on):
    story, _ = _story(db_session, ["news-a.com", "news-b.com"], age_hours=48)
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


def test_off_by_default_and_kill_switches(db_session, lane_on, monkeypatch):
    story, _ = _story(db_session, ["news-a.com", "news-b.com"])
    monkeypatch.delenv("AUTO_PUBLISH_BREAKING")
    assert auto_publish_stories(db_session) == 0
    monkeypatch.setenv("AUTO_PUBLISH_BREAKING", "true")
    db_session.add(RuntimeSwitch(key="breaking", enabled=False, updated_by="t"))
    db_session.commit()
    assert auto_publish_stories(db_session) == 0
    db_session.get(RuntimeSwitch, "breaking").enabled = True
    db_session.add(RuntimeSwitch(key="auto_publish", enabled=False, updated_by="t"))
    db_session.commit()
    assert auto_publish_stories(db_session) == 0  # the global auto-publish pause wins too
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


def test_daily_cap(db_session, lane_on, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_BREAKING_DAILY_CAP", "1")
    first, _ = _story(db_session, ["news-a.com", "news-b.com"])
    second, _ = _story(db_session, ["news-c.com", "news-d.com"])
    assert auto_publish_stories(db_session) == 1
    assert auto_publish_stories(db_session) == 0  # cap counts earlier runs today
    statuses = {db_session.refresh(s) or s.status for s in (first, second)}
    assert statuses == {"SCHEDULED", "REVIEW_REQUIRED"}


def test_source_text_brief_is_not_machine_translated(db_session, lane_on, monkeypatch):
    monkeypatch.setenv("AI_TRANSLATION_ENABLED", "true")
    story, _ = _story(db_session, ["news-a.com", "news-b.com"])
    auto_publish_stories(db_session)
    assert translate_stories(db_session) == 0
    assert db_session.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te")).first() is None


def test_publisher_domain():
    def dom(host):
        return publisher_domain(Source(id=uuid.uuid4(), name="x", base_url=f"https://{host}/p"))

    assert dom("www.thehindu.com") == dom("feeds.thehindu.com") == "thehindu.com"
    assert dom("news.bbc.co.uk") == "bbc.co.uk"
