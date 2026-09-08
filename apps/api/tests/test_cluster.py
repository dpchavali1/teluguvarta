"""T09 acceptance tests: fingerprint + lexical-similarity dedup/clustering.

Uses directly-inserted `SourceItem` rows (not adapter fixtures) since
clustering operates purely on already-`NORMALIZED` rows regardless of which
adapter produced them.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.jobs.cluster import cluster_normalized_items
from app.models import Source, SourceItem, Story, StorySource

from .conftest import requires_postgres


def _make_source(db: Session) -> Source:
    source = Source(name="Test Source", feed_url="https://example.org/feed.xml", rights_status="LINK_ONLY", active=True)
    db.add(source)
    db.commit()
    return source


def _make_item(db: Session, source: Source, *, external_id: str, title: str, published_at: datetime) -> SourceItem:
    item = SourceItem(
        source_id=source.id,
        external_id=external_id,
        url=f"https://example.org/{external_id}",
        title=title,
        published_at=published_at,
        raw_hash=f"hash-{external_id}",
        ingest_status="NORMALIZED",
    )
    db.add(item)
    db.commit()
    return item


@requires_postgres
def test_similar_items_cluster_into_one_story(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        now = datetime.now(UTC)
        item_a = _make_item(db, source, external_id="a", title="Senate passes new immigration reform bill", published_at=now)
        item_b = _make_item(
            db, source, external_id="b", title="Senate passes immigration reform bill", published_at=now + timedelta(minutes=5)
        )

        processed = cluster_normalized_items(db)
        assert processed == 2

        stories = db.scalars(select(Story)).all()
        assert len(stories) == 1

        links = db.scalars(select(StorySource).where(StorySource.story_id == stories[0].id)).all()
        assert {link.source_item_id for link in links} == {item_a.id, item_b.id}
        roles = {link.source_item_id: link.role for link in links}
        assert roles[item_a.id] == "PRIMARY"
        assert roles[item_b.id] == "SUPPORTING"

        db.refresh(item_a)
        db.refresh(item_b)
        assert item_a.ingest_status == "CLUSTERED"
        assert item_b.ingest_status == "CLUSTERED"


@requires_postgres
def test_unrelated_items_do_not_cluster_together(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        now = datetime.now(UTC)
        _make_item(db, source, external_id="a", title="Fire breaks out at downtown warehouse in Springfield", published_at=now)
        _make_item(db, source, external_id="b", title="Massive earthquake hits northern California coast", published_at=now)

        processed = cluster_normalized_items(db)
        assert processed == 2

        stories = db.scalars(select(Story)).all()
        assert len(stories) == 2
        for story in stories:
            links = db.scalars(select(StorySource).where(StorySource.story_id == story.id)).all()
            assert len(links) == 1


@requires_postgres
def test_clustering_is_idempotent(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        now = datetime.now(UTC)
        _make_item(db, source, external_id="a", title="Senate passes new immigration reform bill", published_at=now)
        _make_item(
            db, source, external_id="b", title="Senate passes immigration reform bill", published_at=now + timedelta(minutes=5)
        )

        first_pass = cluster_normalized_items(db)
        second_pass = cluster_normalized_items(db)

        assert first_pass == 2
        assert second_pass == 0

        assert len(db.scalars(select(Story)).all()) == 1
        assert len(db.scalars(select(StorySource)).all()) == 2


@requires_postgres
def test_exact_title_fingerprint_clusters_across_punctuation_and_case(migrated_database):
    engine = create_engine(migrated_database)
    with Session(engine) as db:
        source = _make_source(db)
        now = datetime.now(UTC)
        _make_item(db, source, external_id="a", title="White House announces new immigration policy", published_at=now)
        _make_item(
            db,
            source,
            external_id="b",
            title="white house announces new immigration policy.",
            published_at=now + timedelta(minutes=1),
        )

        processed = cluster_normalized_items(db)
        assert processed == 2
        assert len(db.scalars(select(Story)).all()) == 1
