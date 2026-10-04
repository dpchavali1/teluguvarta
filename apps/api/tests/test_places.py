# ruff: noqa: F811
"""P03 / ADR-043: place catalog, story place tags, place follows, ranking,
place alerts, the public place filter and the admin editor."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.content.notifications import NotifiableStory, UserNotificationPrefs, place_alert_eligible
from app.content.places import (
    CATALOG,
    MAX_FOLLOWED_PLACES,
    ancestors,
    expand_with_ancestors,
    normalize_place_ids,
    render_typescript,
    subtree_ids,
)
from app.content.ranking import Preferences, RankableStory, rank_stories
from app.jobs.generate import generate_stories
from app.jobs.notify import run_notification_dispatch
from app.models import StoryPlace, UserPlace
from tests.conftest import requires_postgres
from tests.test_editorial_workflow import _auth, _make_review_required_story, _token
from tests.test_generate import (
    _classification,
    _generation,
    _make_clustered_story,
    _make_source,
    _use_fake_provider,
)
from tests.test_notifications import _job, _make_published_story, client, db_session
from tests.test_smart_alerts import AUTH, _rows, _user

# --- catalog (pure) ---


def test_catalog_is_consistent():
    ids = [p.id for p in CATALOG]
    assert len(ids) == len(set(ids))
    by_id = {p.id: p for p in CATALOG}
    for place in CATALOG:
        assert place.name_en and place.name_te
        assert place.kind in {"COUNTRY", "STATE", "DISTRICT", "CITY"}
        assert (place.parent_id is None) == (place.kind == "COUNTRY")
        if place.parent_id:
            assert place.parent_id in by_id
            assert by_id[place.parent_id].country == place.country
    # ADR-043 diaspora set: UK/CA/AU/DE/AE/SG/NZ at country level at least.
    assert {"US", "IN", "GB", "CA", "AU", "DE", "AE", "SG", "NZ"} <= set(ids)


def test_unknown_place_ids_are_dropped_and_parents_are_implied():
    assert normalize_place_ids(["IN-TG-warangal", "Narnia", " IN-TG-warangal ", None, ""]) == ["IN-TG-warangal"]
    assert ancestors("IN-TG-warangal") == ["IN-TG", "IN"]
    assert expand_with_ancestors(["US-TX-dallas"]) == {"US-TX-dallas", "US-TX", "US"}
    assert {"IN-TG", "IN-TG-warangal", "IN-TG-hyderabad"} <= set(subtree_ids("IN-TG"))
    assert subtree_ids("nope") == []


def test_typescript_catalog_is_not_stale():
    ts = Path(__file__).resolve().parents[3] / "packages" / "domain" / "places.ts"
    assert ts.read_text(encoding="utf-8") == render_typescript(), (
        "run: cd apps/api && python -m app.content.places > ../../packages/domain/places.ts"
    )


# --- ranking (pure) ---


def _rankable(id_, *, places=(), countries=()):
    now = datetime(2026, 9, 8, tzinfo=UTC)
    return RankableStory(
        id=id_, countries=countries, topics=(), importance=0.5, places=places,
        published_at=now - timedelta(hours=2), source_quality=0.5,
    )


def test_place_follow_matches_exact_and_ancestors_with_named_reason():
    now = datetime(2026, 9, 8, tzinfo=UTC)
    stories = [
        _rankable("none"),
        _rankable("state", places=("IN-TG",)),
        _rankable("exact", places=("IN-TG-warangal",)),
    ]
    ranked = {s.story_id: s for s in rank_stories(stories, Preferences(follow_places=("IN-TG-warangal",)), now=now)}
    assert ranked["exact"].explanation == "Because you follow Warangal."
    assert ranked["none"].explanation is None
    # A state-level story does not match a district follow (no descendant matching).
    assert ranked["state"].explanation is None

    ranked = {s.story_id: s for s in rank_stories(stories, Preferences(follow_places=("IN-TG",)), now=now)}
    assert ranked["exact"].explanation == "Because you follow Telangana."
    assert ranked["exact"].score < ranked["state"].score  # ancestor match scores below exact
    assert ranked["none"].score < ranked["exact"].score


def test_follow_alone_makes_preferences_non_empty():
    assert Preferences().is_empty()
    assert not Preferences(follow_places=("US-TX",)).is_empty()


# --- place alerts (pure) ---


def _notifiable(**kw):
    base = dict(id="s", topics=(), importance=0.9, classification_confidence=0.9, sensitivity="NONE",
                breaking_alert_approved=False, avg_source_quality=0.8, places=("IN-TG-warangal",))
    base.update(kw)
    return NotifiableStory(**base)


def _prefs(**kw):
    base = dict(subscribed_topics=(), breaking_alerts_enabled=True, daily_briefing_enabled=True,
                quiet_hours_start=None, quiet_hours_end=None, max_alerts_per_day=5)
    base.update(kw)
    return UserNotificationPrefs(**base)


def test_place_alert_requires_switch_tag_and_non_sensitive():
    assert place_alert_eligible(_notifiable(), _prefs(alert_places=("IN-TG",))) is True  # ancestor
    assert place_alert_eligible(_notifiable(), _prefs(alert_places=("US-TX",))) is False
    assert place_alert_eligible(_notifiable(), _prefs()) is False  # switch off -> not in alert_places
    assert place_alert_eligible(_notifiable(places=()), _prefs(alert_places=("IN",))) is False  # untagged
    assert place_alert_eligible(_notifiable(sensitivity="IMMIGRATION"), _prefs(alert_places=("IN",))) is False
    assert place_alert_eligible(_notifiable(importance=0.1), _prefs(alert_places=("IN",))) is False


# --- DB-backed ---


@requires_postgres
def test_place_follow_sync_round_trip_drops_unknown_and_caps(client, db_session):
    response = client.patch(
        "/v1/me/preferences",
        json={"follow_places": [
            {"place_id": "IN-TG-warangal", "alerts": True}, {"place_id": "Narnia", "alerts": True},
            {"place_id": "US-TX", "alerts": False}, {"place_id": "US-TX", "alerts": True},
        ]},
        headers=AUTH,
    )
    assert response.status_code == 200
    assert response.json()["follow_places"] == [
        {"place_id": "IN-TG-warangal", "alerts": True}, {"place_id": "US-TX", "alerts": False},
    ]
    # Omitted keeps; [] clears.
    assert client.patch("/v1/me/preferences", json={"max_alerts_per_day": 3}, headers=AUTH).json()["follow_places"]
    assert client.patch("/v1/me/preferences", json={"follow_places": []}, headers=AUTH).json()["follow_places"] == []
    too_many = [{"place_id": "US-TX"}] * (MAX_FOLLOWED_PLACES + 1)
    assert client.patch("/v1/me/preferences", json={"follow_places": too_many}, headers=AUTH).status_code == 422


@requires_postgres
def test_place_alert_dispatch_once_and_only_with_switch_on(db_session):
    story = _make_published_story(db_session)
    db_session.add(StoryPlace(story_id=story.id, place_id="IN-TG-warangal", role="EVENT"))
    on, off, other = _user(db_session), _user(db_session), _user(db_session)
    db_session.add_all([
        UserPlace(user_id=on.id, place_id="IN-TG", alerts=True),
        UserPlace(user_id=off.id, place_id="IN-TG", alerts=False),
        UserPlace(user_id=other.id, place_id="US-TX", alerts=True),
    ])
    db_session.commit()

    run_notification_dispatch(db_session, _job())
    run_notification_dispatch(db_session, _job())

    assert len(_rows(db_session, on, "TOPIC_ALERT")) == 1
    assert _rows(db_session, off, "TOPIC_ALERT") == []
    assert _rows(db_session, other, "TOPIC_ALERT") == []


@requires_postgres
def test_public_place_filter_matches_subtree_and_home_ranks_by_follow(client, db_session):
    tagged = _make_published_story(db_session)
    untagged = _make_published_story(db_session)
    db_session.add(StoryPlace(story_id=tagged.id, place_id="IN-TG-warangal", role="EVENT"))
    db_session.commit()

    ids = lambda r: {item["id"] for item in r.json()["items"]}  # noqa: E731
    assert ids(client.get("/v1/stories", params={"place": "IN-TG"})) == {str(tagged.id)}
    assert ids(client.get("/v1/stories", params={"place": "IN-TG-warangal"})) == {str(tagged.id)}
    assert ids(client.get("/v1/stories", params={"place": "US-TX"})) == set()  # explicit empty, no fallback
    assert client.get("/v1/stories", params={"place": "Narnia"}).status_code == 422

    top = client.get("/v1/home", params={"places": "IN-TG-warangal,Narnia"}).json()["top_stories"]
    assert top[0]["id"] == str(tagged.id)
    assert top[0]["personalization"]["explanation"] == "Because you follow Warangal."
    assert top[0]["places"] == ["IN-TG-warangal"]
    assert str(untagged.id) in {s["id"] for s in top}


@requires_postgres
def test_editor_sets_event_places_with_audit(client, db_session):
    token = _token(client, db_session)
    story = _make_review_required_story(db_session)
    url = f"/v1/admin/stories/{story.id}"

    bad = client.put(f"{url}/places", json={"places": ["US-TX", "Narnia"]}, headers=_auth(token))
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "UNKNOWN_PLACE"

    assert client.put(f"{url}/places", json={"places": ["US-TX-dallas"], "reason": "fix"}, headers=_auth(token)).status_code == 200
    assert client.get(url, headers=_auth(token)).json()["places"] == ["US-TX-dallas"]


@requires_postgres
def test_generation_stores_only_catalog_places(migrated_database, monkeypatch):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        db.commit()
        story, item = _make_clustered_story(db, source)
        _use_fake_provider(monkeypatch, [
            _classification(confidence=0.9, countries=["India"], places=["IN-TG-warangal", "Atlantis"]),
            _generation(item_id=item.id),
        ])
        assert generate_stories(db) == 1
        placed = db.scalars(select(StoryPlace.place_id).where(StoryPlace.story_id == story.id)).all()
        assert placed == ["IN-TG-warangal"]
