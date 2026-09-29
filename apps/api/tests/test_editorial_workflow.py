"""T12 acceptance tests: editorial approve/reject/retract/correct, the
kill-switch-gated auto-publish sweep, and the audit trail that must cover
every mutation. Needs real Postgres for the native `story_status` enum/
trigger, same fixtures as test_admin_sources.py.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.content.variants import EDITOR_MODEL_VERSION
from app.jobs.publish import auto_publish_stories, publish_due_stories
from app.models import (
    AiCallLog,
    AuditEvent,
    Correction,
    ReviewTask,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryVariant,
)
from tests.conftest import requires_postgres

pytestmark = requires_postgres

ADMIN_EMAIL = "admin@example.com"
PASSWORD = "correct horse battery staple"


@pytest.fixture
def client(migrated_database, monkeypatch):
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")

    from app.db import _engine_for
    from app.main import app

    _engine_for.cache_clear()
    yield TestClient(app)
    _engine_for.cache_clear()


@pytest.fixture
def db_session(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _token(client, db_session, *, role="ADMIN", email=ADMIN_EMAIL):
    # Mints a full-session token directly rather than via /login: these tests
    # exercise editorial workflow, not P0-3/ADR-012's MFA-enrollment gate.
    from app.models import User
    from app.security import create_admin_access_token, hash_password

    user = User(id=uuid.uuid4(), email=email, role=role, password_hash=hash_password(PASSWORD))
    db_session.add(user)
    db_session.commit()

    token, _ = create_admin_access_token(user.id, user.email, role)
    return token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_review_required_story(db: Session, *, sensitivity: str = "NONE", with_english: bool = True) -> Story:
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity=sensitivity)
    db.add(story)
    db.flush()
    story.status = "REVIEW_REQUIRED"
    db.add(ReviewTask(story_id=story.id, reason="TEST_SETUP", status="PENDING"))
    if with_english:
        db.add(StoryVariant(story_id=story.id, language="en", headline="Old headline", summary="Old summary", why_matters="Old why"))
    db.commit()
    db.refresh(story)
    return story


def _publish(db: Session, story: Story) -> None:
    """Drives a REVIEW_REQUIRED story all the way to PUBLISHED for tests
    that need a live story (retract/correct), via the real approve
    transition plus the real publish_scheduler sweep — not a shortcut."""
    story.status = "APPROVED"
    db.flush()
    story.status = "SCHEDULED"
    db.commit()
    publish_due_stories(db)
    db.refresh(story)


def test_approve_transitions_to_scheduled_and_writes_audit_event(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)

    response = client.post(f"/v1/admin/stories/{story.id}/approve", json={"reason": "looks good"}, headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["status"] == "SCHEDULED"

    db_session.refresh(story)
    assert story.status == "SCHEDULED"

    task = db_session.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).first()
    assert task.status == "APPROVED"

    event = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == "STORY_APPROVED")
    ).first()
    assert event is not None
    assert event.actor == ADMIN_EMAIL


def test_approve_rejects_illegal_transition(client, db_session):
    token = _token(client, db_session)
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="DRAFT")
    db_session.add(story)
    db_session.commit()

    response = client.post(f"/v1/admin/stories/{story.id}/approve", json={}, headers=_auth(token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ILLEGAL_TRANSITION"


def _variant(db: Session, story: Story, language: str) -> StoryVariant | None:
    db.expire_all()
    return db.scalars(
        select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == language)
    ).first()


def test_approve_refuses_story_without_english_draft(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session, with_english=False)

    response = client.post(f"/v1/admin/stories/{story.id}/approve", json={}, headers=_auth(token))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_ENGLISH_DRAFT"

    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


def test_editor_writes_english_draft_then_approves(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session, with_english=False)

    response = client.put(
        f"/v1/admin/stories/{story.id}/variants/en",
        json={"headline": "  Editor headline ", "summary": "Editor summary", "why_matters": " ", "reason": "no AI route"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REVIEW_REQUIRED"

    en = _variant(db_session, story, "en")
    assert (en.headline, en.summary, en.why_matters) == ("Editor headline", "Editor summary", None)
    assert en.model_version == EDITOR_MODEL_VERSION

    event = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == "STORY_DRAFT_WRITTEN")
    ).first()
    assert event is not None
    assert event.actor == ADMIN_EMAIL

    response = client.post(f"/v1/admin/stories/{story.id}/approve", json={}, headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["status"] == "SCHEDULED"


def test_rewriting_english_draft_invalidates_telugu(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    db_session.add(StoryVariant(story_id=story.id, language="te", headline="పాత శీర్షిక", summary="పాత సారాంశం"))
    db_session.commit()

    response = client.put(
        f"/v1/admin/stories/{story.id}/variants/en",
        json={"headline": "New headline", "summary": "New summary"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert _variant(db_session, story, "en").headline == "New headline"
    assert _variant(db_session, story, "te") is None


def test_telugu_draft_needs_english_and_must_pass_qa(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session, with_english=False)
    url = f"/v1/admin/stories/{story.id}/variants/te"

    response = client.put(url, json={"headline": "శీర్షిక", "summary": "సారాంశం"}, headers=_auth(token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NO_ENGLISH_DRAFT"

    client.put(
        f"/v1/admin/stories/{story.id}/variants/en",
        json={"headline": "Fees rise to 250 dollars", "summary": "The fee rises."},
        headers=_auth(token),
    )
    response = client.put(url, json={"headline": "రుసుము పెరిగింది", "summary": "రుసుము పెరుగుతుంది."}, headers=_auth(token))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TELUGU_QA_FAILED"
    assert _variant(db_session, story, "te") is None

    response = client.put(url, json={"headline": "రుసుము 250 డాలర్లకు పెరిగింది", "summary": "రుసుము పెరుగుతుంది."}, headers=_auth(token))
    assert response.status_code == 200
    te = _variant(db_session, story, "te")
    assert te.qa_status == "PASSED"
    assert te.model_version == EDITOR_MODEL_VERSION


def test_draft_rejects_blank_text_and_published_story(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    url = f"/v1/admin/stories/{story.id}/variants/en"

    response = client.put(url, json={"headline": "   ", "summary": "S"}, headers=_auth(token))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EMPTY_DRAFT"

    _publish(db_session, story)
    response = client.put(url, json={"headline": "H", "summary": "S"}, headers=_auth(token))
    assert response.status_code == 409  # published stories go through /correct
    assert response.json()["error"]["code"] == "ILLEGAL_TRANSITION"


def test_reject_defaults_to_draft(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)

    response = client.post(f"/v1/admin/stories/{story.id}/reject", json={"reason": "not relevant"}, headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["status"] == "DRAFT"

    event = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == "STORY_REJECTED")
    ).first()
    assert event.metadata_["outcome"] == "DRAFT"


def test_reject_can_archive(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)

    response = client.post(
        f"/v1/admin/stories/{story.id}/reject", json={"reason": "never relevant", "archive": True}, headers=_auth(token)
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"


def test_retract_requires_published_story(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)

    response = client.post(f"/v1/admin/stories/{story.id}/retract", json={}, headers=_auth(token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ILLEGAL_TRANSITION"


def test_retract_published_story(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    _publish(db_session, story)
    assert story.status == "PUBLISHED"

    response = client.post(f"/v1/admin/stories/{story.id}/retract", json={"reason": "correction issue"}, headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["status"] == "RETRACTED"

    # Attempting to approve an already-RETRACTED story is rejected (the
    # ticket's own illegal-transition example).
    response = client.post(f"/v1/admin/stories/{story.id}/approve", json={}, headers=_auth(token))
    assert response.status_code == 409


def test_correct_published_story_creates_correction_and_invalidates_telugu_variant(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    _publish(db_session, story)
    db_session.add(StoryVariant(story_id=story.id, language="te", headline="పాత శీర్షిక", summary="పాత సారాంశం"))
    db_session.commit()

    response = client.post(
        f"/v1/admin/stories/{story.id}/correct",
        json={"reason": "fixed a factual error", "headline": "Corrected headline"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "UPDATED"

    variant = db_session.scalars(
        select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "en")
    ).first()
    assert variant.headline == "Corrected headline"
    assert variant.qa_status == "PENDING"

    te_variant = db_session.scalars(
        select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "te")
    ).first()
    assert te_variant is None  # invalidation hook deletes the stale derived variant

    correction = db_session.scalars(select(Correction).where(Correction.story_id == story.id)).first()
    assert correction is not None
    assert correction.reason == "fixed a factual error"
    assert correction.old_text_hash != correction.new_text_hash


def test_correct_requires_at_least_one_field(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    _publish(db_session, story)

    response = client.post(f"/v1/admin/stories/{story.id}/correct", json={"reason": "no actual change"}, headers=_auth(token))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_CHANGES"


def test_review_queue_lists_pending_tasks(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)

    response = client.get("/v1/admin/review-queue", headers=_auth(token))
    assert response.status_code == 200
    ids = [item["story_id"] for item in response.json()]
    assert str(story.id) in ids


def test_review_queue_shows_source_title_for_undrafted_story(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session, with_english=False)
    source = Source(name="S", feed_url=f"https://example.org/{uuid.uuid4()}.xml", rights_status="LINK_ONLY", active=True)
    db_session.add(source)
    db_session.flush()
    item = SourceItem(
        source_id=source.id, external_id="a", url="https://example.org/a", title="Agency updates travel advisory",
        raw_hash="hash-a", ingest_status="REVIEW",
    )
    db_session.add(item)
    db_session.flush()
    db_session.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=1))
    db_session.commit()

    response = client.get("/v1/admin/review-queue", headers=_auth(token))
    row = next(r for r in response.json() if r["story_id"] == str(story.id))
    assert row["headline"] is None
    assert row["source_title"] == "Agency updates travel advisory"


def test_auto_publish_disabled_routes_to_review_queue_not_publish(db_session, monkeypatch):
    monkeypatch.delenv("AUTO_PUBLISH_GLOBAL", raising=False)
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity="NONE")
    db_session.add(story)
    db_session.commit()

    processed = auto_publish_stories(db_session)
    assert processed == 1

    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"

    task = db_session.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).first()
    assert task is not None
    assert task.reason == "AUTO_PUBLISH_DISABLED"


def test_auto_publish_enabled_advances_to_scheduled_and_then_published(db_session, monkeypatch):
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity="NONE")
    db_session.add(story)
    db_session.commit()

    processed = auto_publish_stories(db_session)
    assert processed == 1
    db_session.refresh(story)
    assert story.status == "SCHEDULED"

    event = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == "STORY_AUTO_APPROVED")
    ).first()
    assert event is not None
    assert event.actor == "system:auto_publish"

    published = publish_due_stories(db_session)
    assert published == 1
    db_session.refresh(story)
    assert story.status == "PUBLISHED"
    assert story.published_at is not None


def test_auto_publish_never_advances_sensitive_story_even_if_flag_on(db_session, monkeypatch):
    """Defense in depth (NON_NEGOTIABLES #5): a sensitive story must never be
    auto-published even if it somehow reached AI_READY."""
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity="IMMIGRATION")
    db_session.add(story)
    db_session.commit()

    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"

    task = db_session.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).first()
    assert task.reason == "SENSITIVE_CATEGORY"


def test_auto_publish_disabled_by_monthly_budget_breach(db_session, monkeypatch):
    """T19 §19: AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH (defaults to enabled)
    must stop auto-publish once MONTHLY_AI_BUDGET_USD is crossed, even with
    AUTO_PUBLISH_GLOBAL on — falling back to the same review queue as the
    global switch being off, not silently continuing to auto-publish."""
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    monkeypatch.setenv("MONTHLY_AI_BUDGET_USD", "1.00")
    db_session.add(AiCallLog(task="SUMMARY", provider="openai", model="gpt-4o-mini", status="SUCCESS", cost_usd=5.00))
    db_session.commit()

    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity="NONE")
    db_session.add(story)
    db_session.commit()

    processed = auto_publish_stories(db_session)
    assert processed == 1
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"
    task = db_session.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).first()
    assert task.reason == "AUTO_PUBLISH_DISABLED"


def test_auto_publish_budget_breach_opt_out_keeps_publishing(db_session, monkeypatch):
    """An operator can explicitly opt out of the budget-breach safety
    behavior (accepting the cost overrun) via
    AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH=false."""
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    monkeypatch.setenv("MONTHLY_AI_BUDGET_USD", "1.00")
    monkeypatch.setenv("AUTO_PUBLISH_DISABLE_ON_BUDGET_BREACH", "false")
    db_session.add(AiCallLog(task="SUMMARY", provider="openai", model="gpt-4o-mini", status="SUCCESS", cost_usd=5.00))
    db_session.commit()

    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity="NONE")
    db_session.add(story)
    db_session.commit()

    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "SCHEDULED"


def test_kill_switch_immigration_flag_is_a_no_op(client, db_session, monkeypatch):
    """§15 acceptance criterion: AUTO_PUBLISH_CATEGORY_IMMIGRATION toggling
    has no effect either way, since immigration never reaches AI_READY."""
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    monkeypatch.setenv("AUTO_PUBLISH_CATEGORY_IMMIGRATION", "false")
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity="NONE")
    db_session.add(story)
    db_session.commit()

    auto_publish_stories(db_session)
    db_session.refresh(story)
    assert story.status == "SCHEDULED"  # unaffected by the immigration flag
