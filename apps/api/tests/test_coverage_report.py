"""Review 2026-09-30 R8: the coverage report must put every source item in
exactly one outcome, credit each published story to its PRIMARY item's
publisher, roll section feeds up to one publisher, and list topics that
published nothing."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.coverage_report import coverage_report, publisher_of
from app.models import Source, SourceItem, Story, StorySource, StoryTopic, Topic

from .conftest import requires_postgres
from .test_observability import _auth, _token, client  # noqa: F401  (fixture)

pytestmark = requires_postgres

# A window no other test writes items or stories into.
START, END = date(2031, 3, 10), date(2031, 3, 12)


def _at(day: date, hour: int = 12) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def _source(db, name, base_url, *, active=True):
    source = Source(name=f"{name} {uuid.uuid4()}", base_url=base_url, rights_status="LINK_ONLY", active=active)
    db.add(source)
    db.flush()
    return source


def _item(db, source, published_at, status="CLUSTERED"):
    item = SourceItem(
        source_id=source.id, external_id=str(uuid.uuid4()), url="https://example.test/a",
        title="t", published_at=published_at, raw_hash=str(uuid.uuid4()), ingest_status=status,
    )
    db.add(item)
    db.flush()
    return item


def _story(db, items, status="PUBLISHED", published_at=None, topics=()):
    story = Story(canonical_slug=f"s-{uuid.uuid4()}", status=status, published_at=published_at)
    db.add(story)
    db.flush()
    for rank, item in enumerate(items, start=1):
        db.add(StorySource(story_id=story.id, source_item_id=item.id, role="PRIMARY" if rank == 1 else "SUPPORTING", evidence_rank=rank))
    for topic in topics:
        db.add(StoryTopic(story_id=story.id, topic_id=topic.id, weight=1))
    db.flush()
    return story


@pytest.fixture
def seeded(db_session):
    db = db_session
    suffix = uuid.uuid4().hex[:8]
    politics = Topic(slug=f"politics-{suffix}", name="Politics")
    students = Topic(slug=f"students-{suffix}", name="Students")
    db.add_all([politics, students])
    db.flush()

    # One paper, two section feeds; one other publisher; one blocked feed.
    paper_main = _source(db, "Paper", "https://www.paper-r8.test/")
    paper_city = _source(db, "Paper City", "https://paper-r8.test/city")
    other = _source(db, "Other", "https://other-r8.test")
    blocked = _source(db, "Blocked", "https://blocked-r8.test")

    day = date(2031, 3, 11)
    # Paper: two stories live, one in review, one not relevant, one backlog.
    lead = _item(db, paper_main, _at(day, 8))
    support = _item(db, other, _at(day, 9))
    _story(db, [lead, support], published_at=_at(day, 10), topics=[politics])  # 2h lag
    _story(db, [_item(db, paper_city, _at(day, 1))], published_at=_at(day, 20), topics=[politics])  # 19h lag
    _story(db, [_item(db, paper_main, _at(day))], status="REVIEW_REQUIRED", topics=[students])
    _story(db, [_item(db, paper_main, _at(day), status="ARCHIVED")], status="DRAFT")
    _item(db, paper_main, _at(day), status="ARCHIVED")
    # Other: one live story of its own, one still waiting to cluster.
    _story(db, [_item(db, other, _at(END, 23))], published_at=_at(END, 23) + timedelta(minutes=30))
    _item(db, other, _at(START), status="NORMALIZED")
    _item(db, blocked, _at(START), status="RIGHTS_BLOCKED")
    # Outside the window on both sides: not counted.
    _item(db, other, datetime(2031, 3, 13, 0, 0, tzinfo=UTC))
    _item(db, other, datetime(2031, 3, 9, 23, 59, tzinfo=UTC))
    db.commit()
    return {"paper_main": paper_main, "paper_city": paper_city, "other": other, "blocked": blocked,
            "politics": politics, "students": students}


def test_every_item_lands_in_one_outcome(db_session, seeded):
    report = coverage_report(db_session, START, END)
    items = report["items"]
    assert items == {"items": 9, "rights_blocked": 1, "backlog_skipped": 1, "not_relevant": 1,
                     "live": 4, "in_review": 1, "other": 1}
    outcomes = sum(v for k, v in items.items() if k != "items")
    assert outcomes == items["items"]

    rows = {row["source_id"]: row for row in report["sources"]}
    main = rows[seeded["paper_main"].id]
    assert (main["items"], main["live"], main["in_review"], main["not_relevant"], main["backlog_skipped"]) == (4, 1, 1, 1, 1)
    # The supporting item counts as live for its feed, but the story is the PRIMARY publisher's.
    other = rows[seeded["other"].id]
    assert (other["items"], other["live"], other["published"], other["other"]) == (3, 2, 1, 1)
    assert sum(row["items"] for row in rows.values() if row["source_id"] in {s.id for s in seeded.values() if isinstance(s, Source)}) == 9


def test_publishers_roll_up_section_feeds_and_report_concentration(db_session, seeded):
    report = coverage_report(db_session, START, END)
    assert publisher_of(seeded["paper_main"]) == publisher_of(seeded["paper_city"]) == "paper-r8.test"
    assert report["published"] == 3 and report["published_without_source"] == 0
    publishers = {row["publisher"]: row for row in report["publishers"]}
    assert publishers["paper-r8.test"]["feeds"] == 2
    assert publishers["paper-r8.test"]["published"] == 2 and publishers["paper-r8.test"]["share"] == pytest.approx(0.667)
    assert report["top_publisher"] == "paper-r8.test" and report["publishers_published"] == 2

    rows = {row["source_id"]: row for row in report["sources"]}
    assert rows[seeded["paper_main"].id]["median_lag_hours"] == 2.0
    assert report["lag"] == {"under_1h": 1, "under_3h": 1, "under_12h": 0, "under_24h": 1, "over_24h": 0, "unknown": 0}
    assert [(d["day"], d["published"], d["publishers"]) for d in report["by_day"]] == [
        (START, 0, 0), (date(2031, 3, 11), 2, 1), (END, 1, 1),
    ]


def test_topics_are_zero_filled_and_untagged_counted(db_session, seeded):
    report = coverage_report(db_session, START, END)
    topics = {row["slug"]: row for row in report["topics"]}
    assert topics[seeded["politics"].slug]["published"] == 2
    # Nothing published, but one waiting in review: the gap shows.
    assert topics[seeded["students"].slug] == {**topics[seeded["students"].slug], "published": 0, "in_review": 1}
    assert report["published_untagged"] == 1


def test_endpoint_defaults_and_bounds(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    body = client.get("/v1/admin/coverage", headers=_auth(token)).json()
    today = datetime.now(UTC).date()
    assert body["end"] == today.isoformat() and len(body["by_day"]) == 7
    bad = client.get("/v1/admin/coverage?start=2031-03-12&end=2031-03-10", headers=_auth(token))
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_RANGE"
    long = client.get("/v1/admin/coverage?start=2030-01-01&end=2031-03-10", headers=_auth(token))
    assert long.status_code == 422 and long.json()["error"]["code"] == "RANGE_TOO_LONG"
    assert client.get("/v1/admin/coverage").status_code == 401
