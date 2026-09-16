"""T14 acceptance tests: the public endpoints serve real published stories
(headline/summary/why-matters, source link, topics, countries), hide
non-public statuses, apply the T13 EN/Telugu fallback, and surface the
retracted/corrected indicator via `status`.
"""

import uuid

from sqlalchemy.orm import Session

from app.models import (
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryTopic,
    StoryVariant,
    Topic,
)
from tests.conftest import requires_postgres

pytestmark = requires_postgres


def _seed_published_story(
    db: Session, *, status: str = "PUBLISHED", te_qa: str | None = None, country: str = "US", topic_slug: str = "immigration"
) -> Story:
    source = Source(name="Example Wire", base_url="https://example.com", rights_status="LINK_ONLY", country=country)
    db.add(source)
    db.flush()
    item = SourceItem(
        source_id=source.id, external_id=str(uuid.uuid4()), url="https://example.com/article",
        title="Original source title", raw_hash="hash",
    )
    db.add(item)
    db.flush()

    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="DRAFT", sensitivity="NONE", importance=1.0)
    db.add(story)
    db.flush()
    db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY", evidence_rank=0))
    topic = Topic(slug=topic_slug, name=topic_slug.title())
    db.add(topic)
    db.flush()
    db.add(StoryTopic(story_id=story.id, topic_id=topic.id, weight=1))
    db.add(StoryVariant(story_id=story.id, language="en", headline="Original headline", summary="Original summary", why_matters="Why it matters"))
    if te_qa is not None:
        db.add(StoryVariant(story_id=story.id, language="te", headline="తెలుగు శీర్షిక", summary="తెలుగు సారాంశం", qa_status=te_qa))
    db.flush()

    for intermediate in ("AI_READY", "REVIEW_REQUIRED", "APPROVED", "SCHEDULED", "PUBLISHED"):
        story.status = intermediate
        db.flush()
    if status != "PUBLISHED":
        story.status = status
        db.flush()
    db.commit()
    db.refresh(story)
    return story


def test_home_lists_published_story(client, db_session):
    story = _seed_published_story(db_session)
    response = client.get("/v1/home")
    assert response.status_code == 200
    body = response.json()
    slugs = [s["canonical_slug"] for s in body["top_stories"]]
    assert story.canonical_slug in slugs
    assert any(t["slug"] == "immigration" for t in body["topics"])


def test_story_detail_has_source_link_and_topics_countries(client, db_session):
    story = _seed_published_story(db_session)
    response = client.get(f"/v1/stories/{story.canonical_slug}")
    assert response.status_code == 200
    body = response.json()
    assert body["sources"][0]["url"] == "https://example.com/article"
    assert body["topics"] == ["immigration"]
    assert body["countries"] == ["US"]
    assert body["variants"]["en"]["headline"] == "Original headline"


def test_unpublished_story_is_not_public(client, db_session):
    story = Story(canonical_slug=f"story-{uuid.uuid4()}", status="DRAFT")
    db_session.add(story)
    db_session.commit()
    response = client.get(f"/v1/stories/{story.canonical_slug}")
    assert response.status_code == 404


def test_failed_te_variant_falls_back_to_english_only(client, db_session):
    story = _seed_published_story(db_session, te_qa="FAILED")
    response = client.get(f"/v1/stories/{story.canonical_slug}")
    body = response.json()
    assert "te" not in body["variants"]
    assert body["variants"]["en"]["headline"] == "Original headline"


def test_passed_te_variant_is_served(client, db_session):
    story = _seed_published_story(db_session, te_qa="PASSED")
    response = client.get(f"/v1/stories/{story.canonical_slug}")
    body = response.json()
    assert body["variants"]["te"]["headline"] == "తెలుగు శీర్షిక"


def test_retracted_story_still_visible_with_retracted_status(client, db_session):
    story = _seed_published_story(db_session, status="RETRACTED")
    response = client.get(f"/v1/stories/{story.canonical_slug}")
    assert response.status_code == 200
    assert response.json()["status"] == "RETRACTED"


def test_corrected_story_shows_updated_status(client, db_session):
    story = _seed_published_story(db_session, status="UPDATED")
    response = client.get(f"/v1/stories/{story.canonical_slug}")
    assert response.status_code == 200
    assert response.json()["status"] == "UPDATED"


def test_topic_page_filters_by_topic(client, db_session):
    a = _seed_published_story(db_session, topic_slug="immigration")
    _seed_published_story(db_session, topic_slug="jobs")
    response = client.get("/v1/topics/immigration")
    assert response.status_code == 200
    body = response.json()
    slugs = [s["canonical_slug"] for s in body["stories"]]
    assert a.canonical_slug in slugs
    assert len(slugs) == 1


def test_country_filter_on_stories_list(client, db_session):
    us = _seed_published_story(db_session, country="US", topic_slug="immigration-us")
    _seed_published_story(db_session, country="IN", topic_slug="immigration-in")
    response = client.get("/v1/stories", params={"country": "US"})
    body = response.json()
    slugs = [s["canonical_slug"] for s in body["items"]]
    assert slugs == [us.canonical_slug]


def test_search_matches_headline(client, db_session):
    story = _seed_published_story(db_session)
    response = client.get("/v1/search", params={"q": "Original headline"})
    assert response.status_code == 200
    slugs = [s["canonical_slug"] for s in response.json()["items"]]
    assert story.canonical_slug in slugs


def test_share_meta_is_text_only(client, db_session):
    story = _seed_published_story(db_session)
    response = client.get(f"/v1/stories/{story.canonical_slug}/share-meta")
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Original headline"
    assert body["image_url"] is None
    assert body["canonical_url"].endswith(f"/story/{story.canonical_slug}")
