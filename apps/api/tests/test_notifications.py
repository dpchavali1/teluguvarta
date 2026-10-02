"""T17 acceptance tests:

1. A user subscribed only to "Money" never receives a topic alert for an
   unrelated "Entertainment" story, however high its importance.
2. Breaking-alert eligibility is a separate code path from topic-alert
   eligibility, and a sensitive-category story never triggers an auto-sent
   breaking alert.
3. Sending the same notification twice never produces two deliveries
   (dedupe by user_id + notification_key).
4. Quiet hours and daily caps are enforced and generate analytics events
   instead of silently dropping the send.
5. A deep link to a retracted story falls back gracefully (stays fetchable,
   not a 404/error).
"""

import logging
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.content.notifications import (
    NotifiableStory,
    UserNotificationPrefs,
    breaking_alert_eligible,
    daily_cap_reached,
    in_quiet_hours,
    topic_alert_eligible,
)
from app.jobs.notify import run_notification_dispatch
from app.models import (
    Job,
    Notification,
    Profile,
    PushToken,
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryTopic,
    StoryVariant,
    Topic,
    User,
    UserTopic,
)
from tests.conftest import requires_postgres

# --- 1/2: pure eligibility, no DB needed ---


def _story(**overrides) -> NotifiableStory:
    defaults = {
        "id": "story-1", "topics": (), "importance": 0.9, "classification_confidence": 0.9, "sensitivity": "NONE",
        "breaking_alert_approved": False, "avg_source_quality": 0.8,
    }
    defaults.update(overrides)
    return NotifiableStory(**defaults)


def _prefs(**overrides) -> UserNotificationPrefs:
    defaults = {
        "subscribed_topics": (), "breaking_alerts_enabled": True, "daily_briefing_enabled": True,
        "quiet_hours_start": None, "quiet_hours_end": None, "max_alerts_per_day": 5,
    }
    defaults.update(overrides)
    return UserNotificationPrefs(**defaults)


def test_topic_alert_never_fires_for_unsubscribed_topic_regardless_of_importance():
    entertainment_story = _story(topics=("entertainment",), importance=1.0)
    money_only_subscriber = _prefs(subscribed_topics=("money",))
    assert topic_alert_eligible(entertainment_story, money_only_subscriber) is False


def test_topic_alert_fires_for_subscribed_topic_above_threshold():
    money_story = _story(topics=("money",), importance=0.9)
    money_subscriber = _prefs(subscribed_topics=("money",))
    assert topic_alert_eligible(money_story, money_subscriber) is True


def test_breaking_alert_requires_explicit_editorial_approval_never_auto_sent():
    unapproved = _story(sensitivity="BREAKING", breaking_alert_approved=False, importance=0.95, avg_source_quality=0.9)
    approved = _story(sensitivity="BREAKING", breaking_alert_approved=True, importance=0.95, avg_source_quality=0.9)
    prefs = _prefs()
    assert breaking_alert_eligible(unapproved, prefs) is False
    assert breaking_alert_eligible(approved, prefs) is True


@pytest.mark.parametrize("sensitivity", ["IMMIGRATION", "LEGAL", "FINANCIAL", "OBITUARY_ACCUSATION", "NONE"])
def test_breaking_alert_never_fires_for_non_breaking_sensitivity(sensitivity):
    # Even if something upstream mistakenly set the approval timestamp, only
    # sensitivity == 'BREAKING' can ever reach an auto-sent breaking push.
    story = _story(sensitivity=sensitivity, breaking_alert_approved=True, importance=0.99, avg_source_quality=0.99)
    assert breaking_alert_eligible(story, _prefs()) is False


def test_topic_and_breaking_eligibility_are_independent_code_paths():
    # A story that would be topic-eligible is not automatically breaking-eligible,
    # and vice versa - no shared gate between the two functions.
    topic_only = _story(topics=("money",), importance=0.9, sensitivity="NONE")
    assert topic_alert_eligible(topic_only, _prefs(subscribed_topics=("money",))) is True
    assert breaking_alert_eligible(topic_only, _prefs(subscribed_topics=("money",))) is False

    breaking_only = _story(sensitivity="BREAKING", breaking_alert_approved=True, importance=0.9, avg_source_quality=0.9)
    assert breaking_alert_eligible(breaking_only, _prefs()) is True
    assert topic_alert_eligible(breaking_only, _prefs(subscribed_topics=("money",))) is False


# --- 4: quiet hours / daily cap, pure functions ---


def test_quiet_hours_wraps_midnight():
    assert in_quiet_hours(23, 22, 7) is True
    assert in_quiet_hours(3, 22, 7) is True
    assert in_quiet_hours(12, 22, 7) is False


def test_quiet_hours_same_day_window():
    assert in_quiet_hours(10, 9, 17) is True
    assert in_quiet_hours(20, 9, 17) is False


def test_quiet_hours_unset_never_suppresses():
    assert in_quiet_hours(3, None, None) is False


def test_daily_cap():
    assert daily_cap_reached(5, 5) is True
    assert daily_cap_reached(4, 5) is False


# --- 3/4/5: DB-backed dispatch integration ---

pytestmark = requires_postgres


@pytest.fixture
def db_session(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(migrated_database):
    from app.db import _engine_for
    from app.main import app

    _engine_for.cache_clear()
    yield TestClient(app)
    _engine_for.cache_clear()


@pytest.fixture(autouse=True)
def _reenable_analytics_logger(migrated_database):
    # `migrated_database` runs `alembic.command.upgrade`, which calls
    # `logging.config.fileConfig(alembic.ini)` — that disables every logger
    # not explicitly listed there (root/sqlalchemy/alembic), "analytics"
    # included, for the rest of the process. Harmless in production (real
    # migrations run out-of-process via `infra/scripts/migrate.sh`), but it
    # silently breaks `caplog` assertions here unless undone *after* the
    # fixture that triggers it (hence the explicit dependency, not just
    # autouse ordering).
    import logging

    logging.getLogger("analytics").disabled = False
    yield


def _job() -> Job:
    return Job(id=uuid.uuid4(), type="notification_dispatch")


def _make_topic(db: Session, slug: str) -> Topic:
    topic = Topic(slug=slug, name=slug.title())
    db.add(topic)
    db.flush()
    return topic


def _make_published_story(db: Session, *, topics: list[Topic] = (), sensitivity="NONE", importance=0.9, breaking_approved=False) -> Story:
    story = Story(
        canonical_slug=f"story-{uuid.uuid4()}", status="PUBLISHED", sensitivity=sensitivity,
        importance=importance, published_at=datetime.now(UTC),
    )
    if breaking_approved:
        story.breaking_alert_approved_at = datetime.now(UTC)
    db.add(story)
    db.flush()
    for topic in topics:
        db.add(StoryTopic(story_id=story.id, topic_id=topic.id))

    source = Source(name="Test Source", rights_status="LINK_ONLY", active=True, quality_score=0.8)
    db.add(source)
    db.flush()
    item = SourceItem(source_id=source.id, external_id=str(uuid.uuid4()), url="https://example.org/x", raw_hash="h")
    db.add(item)
    db.flush()
    db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY"))
    db.commit()
    db.refresh(story)
    return story


def _make_user_with_topic(db: Session, topic: Topic, *, breaking_alerts_enabled=True, quiet_hours=(None, None), max_alerts_per_day=5) -> User:
    user = User(id=uuid.uuid4())
    db.add(user)
    db.flush()
    db.add(UserTopic(user_id=user.id, topic_id=topic.id))
    db.add(Profile(
        user_id=user.id, breaking_alerts_enabled=breaking_alerts_enabled,
        quiet_hours_start=quiet_hours[0], quiet_hours_end=quiet_hours[1],
        max_alerts_per_day=max_alerts_per_day,
    ))
    db.add(PushToken(user_id=user.id, platform="ios", token=f"ExponentPushToken[{uuid.uuid4()}]"))
    db.commit()
    db.refresh(user)
    return user


def test_dispatch_dedupes_same_notification_across_repeated_runs(db_session):
    topic = _make_topic(db_session, "money")
    _make_published_story(db_session, topics=[topic], importance=0.9)
    user = _make_user_with_topic(db_session, topic)

    run_notification_dispatch(db_session, _job())
    run_notification_dispatch(db_session, _job())
    run_notification_dispatch(db_session, _job())

    rows = db_session.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.type == "TOPIC_ALERT")
    ).all()
    assert len(rows) == 1


def test_dispatch_never_alerts_unsubscribed_topic(db_session):
    money = _make_topic(db_session, "money")
    entertainment = _make_topic(db_session, "entertainment")
    _make_published_story(db_session, topics=[entertainment], importance=1.0)
    user = _make_user_with_topic(db_session, money)

    run_notification_dispatch(db_session, _job())

    rows = db_session.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.type == "TOPIC_ALERT")
    ).all()
    assert rows == []


def test_dispatch_delivers_student_topic_alert_through_same_worker_no_parallel_path(db_session):
    """S2 (docs/tickets/S2.md): a student topic (e.g. "f1", part of
    `infra/scripts/seed.py`'s STUDENT_SEED_TOPICS) is a plain `Topic` row
    with zero special-casing anywhere in `app/content/notifications.py` or
    `app/jobs/notify.py` — this is the same `run_notification_dispatch` call
    as `test_dispatch_dedupes_same_notification_across_repeated_runs`
    above, just with a student-taxonomy slug instead of "money"."""

    f1_topic = _make_topic(db_session, "f1")
    _make_published_story(db_session, topics=[f1_topic], importance=0.9)
    user = _make_user_with_topic(db_session, f1_topic)

    run_notification_dispatch(db_session, _job())

    rows = db_session.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.type == "TOPIC_ALERT")
    ).all()
    assert len(rows) == 1


def test_unsubscribing_student_topic_leaves_general_topic_subscription_untouched(db_session):
    """S2 acceptance criterion: unsubscribing from all student topics
    doesn't affect general topic notification settings, and vice versa.
    Both are just rows in `user_topics` — removing one topic's row never
    touches another's, proven here via the same dispatch path both topics
    go through."""

    money = _make_topic(db_session, "money")
    opt = _make_topic(db_session, "opt")
    money_story = _make_published_story(db_session, topics=[money], importance=0.9)
    opt_story = _make_published_story(db_session, topics=[opt], importance=0.9)
    user = _make_user_with_topic(db_session, money)
    db_session.add(UserTopic(user_id=user.id, topic_id=opt.id))
    db_session.commit()

    # Unsubscribe from the student topic only.
    db_session.query(UserTopic).filter(UserTopic.user_id == user.id, UserTopic.topic_id == opt.id).delete()
    db_session.commit()

    run_notification_dispatch(db_session, _job())

    money_alerts = db_session.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.type == "TOPIC_ALERT",
                                    Notification.story_id == money_story.id)
    ).all()
    opt_alerts = db_session.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.type == "TOPIC_ALERT",
                                    Notification.story_id == opt_story.id)
    ).all()
    assert len(money_alerts) == 1
    assert opt_alerts == []


def test_quiet_hours_suppresses_and_emits_analytics_event(db_session, caplog):
    topic = _make_topic(db_session, "money")
    _make_published_story(db_session, topics=[topic], importance=0.9)
    now_hour = datetime.now(UTC).hour
    # A 24h quiet window (start == end) guarantees suppression regardless of
    # what hour the test runs at.
    user = _make_user_with_topic(db_session, topic, quiet_hours=(now_hour, now_hour))

    with caplog.at_level(logging.INFO, logger="analytics"):
        run_notification_dispatch(db_session, _job())

    notification = db_session.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.type == "TOPIC_ALERT")
    ).one()
    assert notification.status == "SUPPRESSED"
    assert notification.suppressed_reason == "QUIET_HOURS"
    assert any("notification_skipped_due_to_quiet_hours" in r.message for r in caplog.records)


def test_daily_cap_suppresses_and_emits_analytics_event(db_session, caplog):
    topic = _make_topic(db_session, "money")
    user = _make_user_with_topic(db_session, topic, max_alerts_per_day=1)
    # Pre-fill today's cap with an already-SENT notification.
    db_session.add(Notification(
        user_id=user.id, type="TOPIC_ALERT", notification_key="already-sent",
        status="SENT", sent_at=datetime.now(UTC),
    ))
    db_session.commit()

    story = _make_published_story(db_session, topics=[topic], importance=0.9)

    with caplog.at_level(logging.INFO, logger="analytics"):
        run_notification_dispatch(db_session, _job())

    notification = db_session.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.story_id == story.id)
    ).one()
    assert notification.status == "SUPPRESSED"
    assert notification.suppressed_reason == "DAILY_CAP"
    assert any("notification_suppressed_by_daily_cap" in r.message for r in caplog.records)


def test_breaking_alert_requires_admin_approval_endpoint(client, db_session, monkeypatch):
    # Mints a full-session token directly rather than via /login: this test
    # exercises the breaking-alert approval endpoint, not P0-3/ADR-012's
    # MFA-enrollment gate.
    from app.security import hash_password
    from tests.admin_session_helpers import admin_auth, admin_session_token

    admin = User(id=uuid.uuid4(), email="admin@example.com", role="ADMIN", password_hash=hash_password("pw"))
    db_session.add(admin)
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="PUBLISHED", sensitivity="BREAKING", importance=0.9, published_at=datetime.now(UTC))
    db_session.add(story)
    db_session.commit()

    token = admin_session_token(db_session, admin.id)

    response = client.post(
        f"/v1/admin/stories/{story.id}/approve-breaking-alert",
        json={"reason": "verified with two independent sources"},
        headers=admin_auth(token),
    )
    assert response.status_code == 200
    db_session.refresh(story)
    assert story.breaking_alert_approved_at is not None


def test_retracted_story_stays_fetchable_deep_link_fallback(client, db_session):
    story = Story(canonical_slug="retracted-slug", status="PUBLISHED", published_at=datetime.now(UTC))
    db_session.add(story)
    db_session.flush()
    story.status = "RETRACTED"
    db_session.commit()

    response = client.get("/v1/stories/retracted-slug")
    assert response.status_code == 200
    assert response.json()["status"] == "RETRACTED"


def test_unavailable_story_deep_link_returns_standard_error_envelope_not_a_crash(client):
    response = client.get("/v1/stories/does-not-exist-at-all")
    assert response.status_code == 404
    assert set(response.json()["error"].keys()) == {"code", "message", "request_id"}


def test_story_alert_push_body_is_the_story_headline(db_session):
    from app.jobs.notify import _push_copy

    topic = _make_topic(db_session, "headline-topic")
    story = _make_published_story(db_session, topics=[topic])
    db_session.add(StoryVariant(story_id=story.id, language="en", headline="Headline EN", summary="s"))
    db_session.add(StoryVariant(story_id=story.id, language="te", headline="Headline TE", summary="s", qa_status="PENDING"))
    user = _make_user_with_topic(db_session, topic)
    db_session.commit()

    alert = Notification(user_id=user.id, story_id=story.id, type="TOPIC_ALERT", notification_key="k")
    # Telugu is hidden until QA passes, so the English headline is used.
    assert _push_copy(db_session, alert)[1] == "Headline EN"
    no_story = Notification(user_id=user.id, story_id=None, type="TOPIC_ALERT", notification_key="k2")
    assert _push_copy(db_session, no_story)[1] == "Open to read the full story."
