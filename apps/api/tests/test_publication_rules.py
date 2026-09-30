"""ADR-026: minimum content for a FULL story, enforced at manual approve,
correction, auto-approve and final publication."""

import uuid

from sqlalchemy import select

from app.content.publication import (
    HEADLINE_COPIES_SOURCE,
    SUMMARY_REPEATS_HEADLINE,
    SUMMARY_TOO_SHORT,
    content_rule_failures,
)
from app.jobs.publish import (
    CONTENT_HOLD_ACTION,
    auto_publish_stories,
    publish_due_stories,
)
from app.models import (
    AuditEvent,
    ReviewTask,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryVariant,
)
from tests.conftest import requires_postgres
from tests.test_editorial_workflow import (  # noqa: F401  (fixtures)
    _auth,
    _make_review_required_story,
    _publish,
    _token,
    client,
    db_session,
)

GOOD_SUMMARY = "The agency raised its filing fee this week. Applicants who file after March pay the new amount."


# --- the rules (unit, no DB) ------------------------------------------------


def test_valid_full_story_passes():
    assert content_rule_failures("Filing fee goes up in March", GOOD_SUMMARY, ["USCIS publishes new fee schedule"]) == []


def test_summary_repeating_headline_fails():
    assert SUMMARY_REPEATS_HEADLINE in content_rule_failures("Fee rises in March", "Fee rises in March.", [])


def test_short_summary_fails_unless_two_sentences_or_25_words():
    assert content_rule_failures("Fee rises", "The agency raised its filing fee this week.", []) == [SUMMARY_TOO_SHORT]
    assert content_rule_failures("Fee rises", "The fee went up. It applies in March.", []) == []
    one_long_sentence = " ".join(["word"] * 25)
    assert content_rule_failures("Fee rises", one_long_sentence, []) == []


def test_headline_close_to_source_title_fails():
    failures = content_rule_failures("USCIS publishes new fee schedule", GOOD_SUMMARY, ["USCIS Publishes New Fee Schedule!"])
    assert failures == [HEADLINE_COPIES_SOURCE]


# --- enforcement ------------------------------------------------------------


def _set_english(db, story, headline, summary):
    en = db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "en")).one()
    en.headline, en.summary = headline, summary
    db.commit()


@requires_postgres
def test_manual_approve_rejects_with_failed_rule(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    _set_english(db_session, story, "Fee rises", "Fee rises.")

    response = client.post(f"/v1/admin/stories/{story.id}/approve", json={"reason": "ok"}, headers=_auth(token))

    assert response.status_code == 422
    body = response.json()
    assert "CONTENT_RULES_FAILED" in str(body)
    assert SUMMARY_REPEATS_HEADLINE in str(body)
    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"


@requires_postgres
def test_correction_must_meet_rules(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    _publish(db_session, story)
    url = f"/v1/admin/stories/{story.id}/correct"

    response = client.post(url, json={"summary": "Too short.", "reason": "fix"}, headers=_auth(token))
    assert response.status_code == 422
    db_session.expire_all()
    en = db_session.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id, StoryVariant.language == "en")).one()
    assert en.summary != "Too short."

    response = client.post(url, json={"summary": GOOD_SUMMARY, "reason": "fix"}, headers=_auth(token))
    assert response.status_code == 200


@requires_postgres
def test_auto_approve_sends_failing_draft_to_review(db_session, monkeypatch):  # noqa: F811
    monkeypatch.setenv("AUTO_PUBLISH_GLOBAL", "true")
    monkeypatch.delenv("MONTHLY_AI_BUDGET_USD", raising=False)
    source = Source(name=f"src-{uuid.uuid4()}", rights_status="LINK_ONLY", active=True)
    db_session.add(source)
    db_session.flush()
    item = SourceItem(source_id=source.id, external_id=str(uuid.uuid4()), url="https://example.org/x", title="USCIS publishes new fee schedule", raw_hash=uuid.uuid4().hex)
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="AI_READY", sensitivity="NONE")
    db_session.add_all([item, story])
    db_session.flush()
    db_session.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=1))
    db_session.add(StoryVariant(story_id=story.id, language="en", headline="USCIS publishes new fee schedule", summary=GOOD_SUMMARY))
    db_session.commit()

    auto_publish_stories(db_session)

    db_session.refresh(story)
    assert story.status == "REVIEW_REQUIRED"
    task = db_session.scalars(select(ReviewTask).where(ReviewTask.story_id == story.id)).one()
    assert task.reason == f"CONTENT_RULES_FAILED:{HEADLINE_COPIES_SOURCE}"


@requires_postgres
def test_scheduled_story_failing_rules_is_held_and_audited_once(db_session):  # noqa: F811
    story = _make_review_required_story(db_session)
    _set_english(db_session, story, "Fee rises", "Fee rises.")
    story.status = "APPROVED"
    db_session.flush()
    story.status = "SCHEDULED"
    db_session.commit()

    assert publish_due_stories(db_session) == 0
    assert publish_due_stories(db_session) == 0

    db_session.refresh(story)
    assert story.status == "SCHEDULED"
    holds = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == CONTENT_HOLD_ACTION)
    ).all()
    assert len(holds) == 1
