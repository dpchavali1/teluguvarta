# ruff: noqa: F811
"""P02 smart alerts: per-topic urgency, digests, keyword follows, dual-zone
quiet hours, saved-story update alerts, and the bounds on synced lists."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.content.notifications import (
    UserNotificationPrefs,
    digest_slots_due,
    digest_story_eligible,
    in_quiet_hours_any_zone,
    keyword_alert_eligible,
    topic_alert_eligible,
)
from app.jobs.notify import run_notification_dispatch
from app.models import (
    Correction,
    Notification,
    Profile,
    PushToken,
    StoryVariant,
    User,
    UserKeyword,
    UserSavedStory,
    UserTopic,
)
from tests.conftest import requires_postgres
from tests.test_notifications import (  # noqa: F401  (fixtures reused)
    _job,
    _make_published_story,
    _make_topic,
    _reenable_analytics_logger,
    _story,
    client,
    db_session,
)


def _prefs(**overrides) -> UserNotificationPrefs:
    defaults = {
        "subscribed_topics": (), "breaking_alerts_enabled": True, "daily_briefing_enabled": True,
        "quiet_hours_start": None, "quiet_hours_end": None, "max_alerts_per_day": 5,
    }
    defaults.update(overrides)
    return UserNotificationPrefs(**defaults)


# --- pure ---


@pytest.mark.parametrize("urgency", ["DIGEST", "BREAKING_ONLY"])
def test_non_instant_topics_never_produce_instant_topic_alert(urgency):
    prefs = _prefs(subscribed_topics=("money",), topic_urgency={"money": urgency})
    assert topic_alert_eligible(_story(topics=("money",)), prefs) is False


def test_mixed_urgency_only_instant_topic_alerts():
    prefs = _prefs(subscribed_topics=("money", "jobs"), topic_urgency={"money": "DIGEST"})
    assert topic_alert_eligible(_story(topics=("jobs",)), prefs) is True
    assert topic_alert_eligible(_story(topics=("money",)), prefs) is False


def test_digest_eligibility_only_for_digest_topics_and_approved_breaking():
    prefs = _prefs(subscribed_topics=("money", "jobs"), topic_urgency={"money": "DIGEST"})
    assert digest_story_eligible(_story(topics=("money",)), prefs) is True
    assert digest_story_eligible(_story(topics=("jobs",)), prefs) is False
    assert digest_story_eligible(_story(topics=("money",), sensitivity="BREAKING"), prefs) is False
    assert digest_story_eligible(
        _story(topics=("money",), sensitivity="BREAKING", breaking_alert_approved=True), prefs
    ) is True


def test_keyword_alert_matches_headline_but_never_sensitive_stories():
    prefs = _prefs(keywords=("opt",))
    assert keyword_alert_eligible(_story(headline="New OPT rule announced"), prefs) is True
    assert keyword_alert_eligible(_story(headline="Weather"), prefs) is False
    assert keyword_alert_eligible(_story(headline="OPT rule", sensitivity="IMMIGRATION"), prefs) is False


def test_digest_slot_uses_residence_zone_and_grace_window():
    prefs = _prefs(residence_tz="America/Chicago", digest_morning_hour=8)
    assert digest_slots_due(datetime(2026, 10, 3, 13, 30, tzinfo=UTC), prefs) == [("am", "2026-10-03")]
    assert digest_slots_due(datetime(2026, 10, 3, 12, 30, tzinfo=UTC), prefs) == []  # 07:30 local
    assert digest_slots_due(datetime(2026, 10, 3, 16, 0, tzinfo=UTC), prefs) == []  # past grace


def test_digest_off_when_hour_unset():
    assert digest_slots_due(datetime(2026, 10, 3, 13, 30, tzinfo=UTC), _prefs(residence_tz="America/Chicago")) == []


def test_quiet_hours_apply_when_either_zone_is_quiet():
    now = datetime(2026, 10, 3, 17, 0, tzinfo=UTC)  # 22:30 IST, 12:00 CDT
    both = _prefs(quiet_hours_start=22, quiet_hours_end=7, home_tz="Asia/Kolkata", residence_tz="America/Chicago")
    assert in_quiet_hours_any_zone(now, both) is True
    only_residence = _prefs(quiet_hours_start=22, quiet_hours_end=7, residence_tz="America/Chicago")
    assert in_quiet_hours_any_zone(now, only_residence) is False


def test_quiet_hours_without_zones_stay_utc():
    assert in_quiet_hours_any_zone(datetime(2026, 10, 3, 23, 0, tzinfo=UTC), _prefs(quiet_hours_start=22, quiet_hours_end=7)) is True


# --- API bounds ---

AUTH = {"Authorization": "Bearer " + "a" * 40}


@requires_postgres
@pytest.mark.parametrize(
    "payload",
    [
        {"keywords": [f"k{i}" for i in range(21)]},
        {"keywords": ["x" * 41]},
        {"keywords": [""]},
        {"saved_story_ids": [str(uuid.uuid4()) for _ in range(201)]},
        {"home_tz": "Mars/Olympus"},
        {"digest_morning_hour": 24},
        {"topic_urgency": {"money": "WHENEVER"}},
    ],
)
def test_preferences_reject_out_of_bounds(client, payload):
    assert client.patch("/v1/me/preferences", json=payload, headers=AUTH).status_code == 422


@requires_postgres
def test_preferences_round_trip_normalizes_and_clears(client, db_session):
    _make_topic(db_session, "money")
    db_session.commit()
    response = client.patch(
        "/v1/me/preferences",
        json={
            "topic_slugs": ["money"], "topic_urgency": {"money": "DIGEST"},
            "keywords": ["  OPT ", "opt", "H-1B"], "home_tz": "Asia/Kolkata",
            "residence_tz": "America/Chicago", "digest_morning_hour": 8, "digest_evening_hour": 18,
        },
        headers=AUTH,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["keywords"] == ["h-1b", "opt"]
    assert body["topic_urgency"] == {"money": "DIGEST"}
    assert (body["digest_morning_hour"], body["digest_evening_hour"]) == (8, 18)

    cleared = client.patch(
        "/v1/me/preferences", json={"digest_morning_hour": None, "keywords": []}, headers=AUTH
    ).json()
    assert cleared["digest_morning_hour"] is None
    assert cleared["digest_evening_hour"] == 18
    assert cleared["keywords"] == []
    assert cleared["topic_urgency"] == {"money": "DIGEST"}


# --- dispatch job ---


def _user(db, *, topic=None, urgency="INSTANT", **profile) -> User:
    user = User(id=uuid.uuid4())
    db.add(user)
    db.flush()
    if topic is not None:
        db.add(UserTopic(user_id=user.id, topic_id=topic.id, urgency=urgency))
    db.add(Profile(user_id=user.id, **profile))
    db.add(PushToken(user_id=user.id, platform="ios", token=f"tok-{uuid.uuid4()}"))
    db.commit()
    return user


def _rows(db, user, type_):
    return db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.type == type_)).all()


@requires_postgres
def test_digest_is_one_idempotent_notification_and_replaces_instant_alert(db_session):
    topic = _make_topic(db_session, "money")
    _make_published_story(db_session, topics=[topic])
    _make_published_story(db_session, topics=[topic])
    hour = datetime.now(UTC).hour
    user = _user(db_session, topic=topic, urgency="DIGEST", residence_tz="UTC", digest_morning_hour=hour,
                 digest_evening_hour=hour)

    for _ in range(3):
        run_notification_dispatch(db_session, _job())

    assert _rows(db_session, user, "TOPIC_ALERT") == []
    digests = _rows(db_session, user, "DIGEST")
    assert len(digests) == 2  # am and pm slots, one notification each
    assert {d.notification_key.rsplit(":", 1)[1] for d in digests} == {"am", "pm"}
    assert all(d.story_id is None for d in digests)


@requires_postgres
def test_digest_skips_stories_already_alerted_and_empty_digests(db_session):
    topic = _make_topic(db_session, "money")
    story = _make_published_story(db_session, topics=[topic])
    hour = datetime.now(UTC).hour
    user = _user(db_session, topic=topic, urgency="DIGEST", residence_tz="UTC", digest_morning_hour=hour)
    db_session.add(Notification(user_id=user.id, story_id=story.id, type="TOPIC_ALERT",
                                notification_key=f"topic_alert:{story.id}", status="SENT"))
    db_session.commit()

    run_notification_dispatch(db_session, _job())

    assert _rows(db_session, user, "DIGEST") == []


@requires_postgres
def test_keyword_follow_alerts_once_across_runs(db_session):
    story = _make_published_story(db_session)
    db_session.add(StoryVariant(story_id=story.id, language="en", headline="New OPT rule for students", summary="s"))
    user = _user(db_session)
    db_session.add(UserKeyword(user_id=user.id, keyword="opt"))
    db_session.commit()

    run_notification_dispatch(db_session, _job())
    run_notification_dispatch(db_session, _job())

    assert len(_rows(db_session, user, "TOPIC_ALERT")) == 1


@requires_postgres
def test_saved_story_correction_alerts_once(db_session):
    story = _make_published_story(db_session)
    user = _user(db_session)
    other = _user(db_session)
    db_session.add(UserSavedStory(user_id=user.id, story_id=story.id))
    db_session.add(Correction(story_id=story.id, reason="fix", old_text_hash="a", new_text_hash="b"))
    db_session.commit()

    run_notification_dispatch(db_session, _job())
    run_notification_dispatch(db_session, _job())

    updates = _rows(db_session, user, "STORY_UPDATE")
    assert len(updates) == 1 and updates[0].story_id == story.id
    assert _rows(db_session, other, "STORY_UPDATE") == []
