"""ADR-019: the link-first brief auto-publish lane. Uses the same
`FakeProvider` monkeypatch as `test_generate.py`."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.ai import gateway as gateway_module
from app.jobs.brief_lane import cap_day_start, is_single_sentence, title_match
from app.jobs.publish import auto_publish_stories, publish_due_stories
from app.models import (
    AuditEvent,
    ReviewTask,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryVariant,
)

from .test_editorial_workflow import client  # noqa: F401  (fixture)
from .test_generate import FakeProvider

TITLE = "Israel - Level 3: Reconsider Travel"


# --- deterministic checks (no DB) ---


def test_title_match_accepts_sentence_bounded_by_title():
    match = title_match("The State Department set Israel at Level 3, reconsider travel.", [TITLE, "State Department advisory"])
    assert match.ok
    assert "Israel" in match.matched and "3" in match.matched


def test_title_match_rejects_added_number_entity_or_cause():
    assert not title_match("Israel is now at Level 4.", [TITLE]).ok
    assert not title_match("Israel and Jordan are at Level 3.", [TITLE]).ok
    assert not title_match("Israel is at Level 3 because of unrest.", [TITLE]).ok


def test_title_match_allows_cause_the_title_states():
    assert title_match("Flights stop after storm.", ["Flights stop after storm hits coast"]).ok


# Review 2026-09-29 #4: negative cases the lane must send to review.
def test_title_match_rejects_changed_negation():
    assert not title_match("The court did not block the rule.", ["Court blocks rule"]).ok
    assert not title_match("The court blocked the rule.", ["Court does not block rule"]).ok
    assert title_match("The court did not block the rule.", ["Court does not block rule"]).ok


def test_title_match_rejects_reversed_relationship():
    assert not title_match("Jones sues Smith.", ["Smith sues Jones over contract"]).ok
    assert not title_match("Fees rise from 10 to 5.", ["Fees rise from 5 to 10"]).ok
    assert not title_match("Fees rise from 10 to 5.", ["Fees rise from 5 to 10"], order="numbers").ok
    assert title_match("Smith sues Jones.", ["Smith sues Jones over contract"]).ok


def test_single_sentence_check():
    assert is_single_sentence("Israel is at Level 3.")
    assert not is_single_sentence("Israel is at Level 3. Travelers should reconsider.")


def test_cap_day_starts_at_new_york_midnight():
    # 03:00 UTC on Sep 30 is still Sep 29 in New York (EDT, UTC-4).
    start = cap_day_start(datetime(2026, 9, 30, 3, 0, tzinfo=UTC))
    assert start == datetime(2026, 9, 29, 4, 0, tzinfo=UTC)


# --- publish sweep (Postgres) ---


def _brief(item_id, **overrides):
    base = {
        "headline_en": "Travel caution raised for Israel",
        "brief_en": "Israel is now at Level 3: Reconsider Travel.",
        "confidence": 0.9,
        "claims": [{"text": "Israel is at Level 3", "source_refs": [str(item_id)]}],
    }
    base.update(overrides)
    return base


def _story(db, *, reviewed=True, category=None, importance=0.9, sensitivity="NONE", title=TITLE):
    source = Source(
        name="State Dept", feed_url=f"https://example.org/{uuid.uuid4()}.xml", rights_status="LINK_ONLY", active=True,
        rights_reviewed_at=datetime.now(UTC) if reviewed else None,
        rights_evidence_url="https://example.org/terms" if reviewed else None,
        category=category,
    )
    db.add(source)
    db.flush()
    item = SourceItem(
        source_id=source.id, external_id=str(uuid.uuid4()), url="https://example.org/a", title=title,
        raw_hash=str(uuid.uuid4()), ingest_status="SCHEDULED",
    )
    db.add(item)
    db.flush()
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity=sensitivity, importance=importance)
    db.add(story)
    db.flush()
    db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=1))
    db.add(StoryVariant(story_id=story.id, language="en", headline="Full headline", summary="Full summary.", why_matters="Why."))
    db.add(StoryVariant(story_id=story.id, language="te", headline="te", summary="te", qa_status="PASSED"))
    db.commit()
    return story, item


def _fake(monkeypatch, responses):
    provider = FakeProvider(responses)
    monkeypatch.setattr(gateway_module, "_resolve_provider", lambda name: provider)
    return provider


@pytest.fixture
def lane_on(monkeypatch):
    monkeypatch.delenv("AUTO_PUBLISH_GLOBAL", raising=False)
    monkeypatch.setenv("AUTO_PUBLISH_BRIEFS", "true")
    monkeypatch.setenv("AI_OPENAI_API_KEY", "test")
    monkeypatch.delenv("AUTO_PUBLISH_BRIEFS_DAILY_CAP", raising=False)


def _task(db, story):
    return db.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).first()


def test_eligible_story_publishes_as_brief(db_session, lane_on, monkeypatch):
    story, item = _story(db_session)
    _fake(monkeypatch, [_brief(item.id)])

    assert auto_publish_stories(db_session) == 1
    db_session.refresh(story)
    assert story.status == "SCHEDULED"
    assert story.format == "BRIEF"
    variants = db_session.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).all()
    assert [v.language for v in variants] == ["en"]  # stale Telugu dropped for re-translation
    assert variants[0].summary.startswith("Israel is now") and variants[0].why_matters is None

    event = db_session.scalars(select(AuditEvent).where(AuditEvent.entity_id == story.id)).one()
    assert event.actor == "system:brief_lane"
    assert event.metadata_["reason"] == "BRIEF_LANE"
    assert "Israel" in event.metadata_["title_match"]["matched"]

    assert publish_due_stories(db_session) == 1


def test_lane_off_by_default(db_session, lane_on, monkeypatch):
    monkeypatch.delenv("AUTO_PUBLISH_BRIEFS")
    story, _ = _story(db_session)
    _fake(monkeypatch, [])  # no AI call expected
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED" and story.format == "FULL"
    assert _task(db_session, story).reason == "AUTO_PUBLISH_DISABLED"


@pytest.mark.parametrize(
    "overrides",
    [
        {"headline_en": "Caution for Israel trips moves up to 4"},  # invented number
        {"headline_en": "Jordan and Israel travel caution"},  # invented name
        {"headline_en": "Israel travel advice not changed"},  # added negation
    ],
)
def test_headline_with_unsupported_fact_goes_to_review(db_session, lane_on, monkeypatch, overrides):
    story, item = _story(db_session)
    _fake(monkeypatch, [_brief(item.id, **overrides)])
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"
    assert "BRIEF_TITLE_MISMATCH" in _task(db_session, story).reason


def test_claim_is_checked_against_its_own_citation(db_session, lane_on, monkeypatch):
    """Claim 2 states a fact only item 2's title supports but cites item 1."""
    story, item = _story(db_session)
    other = SourceItem(
        source_id=item.source_id, external_id=str(uuid.uuid4()), url="https://example.org/b",
        title="Jordan - Level 2: Exercise Increased Caution", raw_hash=str(uuid.uuid4()), ingest_status="SCHEDULED",
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(StorySource(story_id=story.id, source_item_id=other.id, role="SUPPORTING", evidence_rank=2))
    db_session.commit()
    _fake(monkeypatch, [_brief(item.id, claims=[
        {"text": "Israel is at Level 3", "source_refs": [str(item.id)]},
        {"text": "Jordan is at Level 2", "source_refs": [str(item.id)]},
        {"text": "Jordan advisory exists", "source_refs": [str(other.id)]},
    ])])
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


@pytest.mark.parametrize(
    "kwargs",
    [{"reviewed": False}, {"category": "immigration"}, {"importance": 0.7}, {"title": "Court indicts official"}],
)
def test_ineligible_story_goes_to_review_without_ai_call(db_session, lane_on, monkeypatch, kwargs):
    story, _ = _story(db_session, **kwargs)
    if "title" in kwargs:
        story.privacy_decision = "RESTRICTED"
        db_session.commit()
    _fake(monkeypatch, [])
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"
    assert _task(db_session, story).reason == "AUTO_PUBLISH_DISABLED"


def test_p1_review_off_closes_the_lane(db_session, lane_on, monkeypatch):
    monkeypatch.setenv("AI_REVIEW_P1_STORIES", "false")
    story, _ = _story(db_session)
    _fake(monkeypatch, [])
    auto_publish_stories(db_session)
    assert _task(db_session, story).reason == "AUTO_PUBLISH_DISABLED"


def test_title_mismatch_keeps_full_draft_for_review(db_session, lane_on, monkeypatch):
    story, item = _story(db_session)
    _fake(monkeypatch, [_brief(item.id, brief_en="Israel is at Level 4 after new attacks.")])
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED" and story.format == "FULL"
    assert _task(db_session, story).reason == "AUTO_PUBLISH_DISABLED,BRIEF_TITLE_MISMATCH"
    en = db_session.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "en")).one()
    assert en.summary == "Full summary."


@pytest.mark.parametrize(
    "overrides",
    [
        {"confidence": 0.7},
        {"brief_en": " ".join(["Israel"] * 31) + "."},
        {"headline_en": TITLE},
        {"claims": []},
        {"claims": [{"text": "Israel", "source_refs": ["not-a-real-item"]}]},
    ],
)
def test_rejected_brief_goes_to_review(db_session, lane_on, monkeypatch, overrides):
    story, item = _story(db_session)
    _fake(monkeypatch, [_brief(item.id, **overrides)])
    auto_publish_stories(db_session)
    assert _task(db_session, story).reason == "AUTO_PUBLISH_DISABLED,BRIEF_REJECTED"


def test_daily_cap_overflow_goes_to_review(db_session, lane_on, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_BRIEFS_DAILY_CAP", "1")
    first, first_item = _story(db_session)
    second, second_item = _story(db_session)
    _fake(monkeypatch, [_brief(first_item.id), _brief(second_item.id)])
    auto_publish_stories(db_session)
    statuses = sorted(s.status for s in (db_session.get(Story, first.id), db_session.get(Story, second.id)))
    assert statuses == ["REVIEW_REQUIRED", "SCHEDULED"]
    held = first if db_session.get(Story, first.id).status == "REVIEW_REQUIRED" else second
    assert _task(db_session, held).reason == "AUTO_PUBLISH_DISABLED,BRIEF_DAILY_CAP"


def test_cap_counts_briefs_since_new_york_midnight_only(db_session, lane_on, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_BRIEFS_DAILY_CAP", "1")
    old = AuditEvent(
        actor="system:brief_lane", action="STORY_AUTO_APPROVED", entity_type="story", entity_id=uuid.uuid4(),
        metadata_={}, created_at=cap_day_start(datetime.now(UTC)) - timedelta(minutes=1),
    )
    db_session.add(old)
    story, item = _story(db_session)
    _fake(monkeypatch, [_brief(item.id)])
    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "SCHEDULED"


def test_budget_breach_closes_the_lane(db_session, lane_on, monkeypatch):
    from app.models import AiCallLog

    monkeypatch.setenv("MONTHLY_AI_BUDGET_USD", "1.00")
    db_session.add(AiCallLog(task="SUMMARY", provider="openai", model="gpt-4o-mini", status="SUCCESS", cost_usd=5.00))
    story, _ = _story(db_session)
    _fake(monkeypatch, [])
    auto_publish_stories(db_session)
    assert _task(db_session, story).reason == "AUTO_PUBLISH_DISABLED"


def test_admin_lists_recent_briefs_and_lane_state(db_session, lane_on, monkeypatch, client):  # noqa: F811
    from tests.test_editorial_workflow import _auth, _token

    story, item = _story(db_session)
    _fake(monkeypatch, [_brief(item.id)])
    auto_publish_stories(db_session)
    token = _token(client, db_session)

    switches = client.get("/v1/admin/kill-switches", headers=_auth(token)).json()
    assert switches["auto_publish_briefs"] is True
    assert switches["auto_publish_briefs_daily_cap"] == 20
    assert switches["briefs_published_today"] == 1

    rows = client.get("/v1/admin/briefs/recent", headers=_auth(token)).json()
    assert [r["story_id"] for r in rows] == [str(story.id)]
    assert rows[0]["source_titles"] == [TITLE]
    assert "Israel" in rows[0]["matched_tokens"]

    detail = client.get(f"/v1/admin/stories/{story.id}", headers=_auth(token)).json()
    assert detail["format"] == "BRIEF"
