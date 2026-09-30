"""Review #11: topic navigation leads with populated topics, and editors can
tag the stories they draft by hand (AI classification is otherwise the only
thing that attaches topics)."""

import uuid

from sqlalchemy import select

from app.models import AuditEvent, StoryTopic, Topic
from tests.conftest import requires_postgres
from tests.test_editorial_workflow import (  # noqa: F401 (fixtures)
    _auth,
    _make_review_required_story,
    _publish,
    _token,
    client,
    db_session,
)

pytestmark = requires_postgres


def _topic(db, name, *, active=True):
    topic = Topic(slug=f"{name.lower()}-{uuid.uuid4().hex[:6]}", name=name, active=active)
    db.add(topic)
    db.flush()
    return topic


def _tag(db, story, *topics):
    for topic in topics:
        db.add(StoryTopic(story_id=story.id, topic_id=topic.id, weight=1))
    db.commit()


def test_config_lists_populated_topics_first_with_counts(client, db_session):
    empty_a = _topic(db_session, "Aaa empty")
    one = _topic(db_session, "Zzz one story")
    two = _topic(db_session, "Mmm two stories")
    hidden = _topic(db_session, "Inactive", active=False)
    for tags in ((one, two), (two, hidden)):
        story = _make_review_required_story(db_session)
        _tag(db_session, story, *tags)
        _publish(db_session, story)
    # An unpublished story doesn't count.
    _tag(db_session, _make_review_required_story(db_session), empty_a)

    topics = client.get("/v1/config").json()["topics"]
    slugs = [t["slug"] for t in topics]
    counts = {t["slug"]: t["story_count"] for t in topics}

    assert hidden.slug not in slugs
    assert counts[two.slug] == 2 and counts[one.slug] == 1 and counts[empty_a.slug] == 0
    assert slugs.index(two.slug) < slugs.index(one.slug) < slugs.index(empty_a.slug)
    assert client.get(f"/v1/topics/{two.slug}").json()["topic"]["story_count"] == 2


def test_editor_sets_topics_on_published_story(client, db_session):
    token = _token(client, db_session)
    visas, jobs = _topic(db_session, "Visas"), _topic(db_session, "Jobs")
    story = _make_review_required_story(db_session)
    _publish(db_session, story)

    response = client.put(
        f"/v1/admin/stories/{story.id}/topics", json={"topics": [visas.slug, jobs.slug, visas.slug]}, headers=_auth(token),
    )
    assert response.status_code == 200
    assert sorted(client.get(f"/v1/admin/stories/{story.id}", headers=_auth(token)).json()["topics"]) == sorted(
        [visas.slug, jobs.slug]
    )
    assert client.get(f"/v1/topics/{visas.slug}").json()["stories"][0]["id"] == str(story.id)

    # Replaces, not appends; an empty list clears.
    client.put(f"/v1/admin/stories/{story.id}/topics", json={"topics": [jobs.slug]}, headers=_auth(token))
    assert client.get(f"/v1/admin/stories/{story.id}", headers=_auth(token)).json()["topics"] == [jobs.slug]
    client.put(f"/v1/admin/stories/{story.id}/topics", json={"topics": []}, headers=_auth(token))
    assert client.get(f"/v1/admin/stories/{story.id}", headers=_auth(token)).json()["topics"] == []

    events = db_session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id == story.id, AuditEvent.action == "STORY_TOPICS_SET")
    ).all()
    assert len(events) == 3


def test_topics_must_be_existing_active_topics(client, db_session):
    token = _token(client, db_session)
    inactive = _topic(db_session, "Old", active=False)
    db_session.commit()
    story = _make_review_required_story(db_session)
    url = f"/v1/admin/stories/{story.id}/topics"

    for slug in ("no-such-topic", inactive.slug):
        response = client.put(url, json={"topics": [slug]}, headers=_auth(token))
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "UNKNOWN_TOPIC"

    assert client.put(url, json={"topics": ["a", "b", "c", "d", "e", "f"]}, headers=_auth(token)).status_code == 422
    assert client.put(url, json={"topics": ["x"]}).status_code == 401
