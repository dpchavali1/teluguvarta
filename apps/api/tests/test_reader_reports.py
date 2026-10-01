"""ADR-029: reader reports are stored privately, rate-limited, deduplicated,
resolved only through audited links to real corrections/retractions, and
their text is erased on schedule. Analytics never carries the text."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import analytics, rate_limit
from app.jobs.cleanup import READER_REPORT_PURGE, run_cleanup, schedule_cleanup
from app.models import AuditEvent, Correction, Job, ReaderReport, Story, StoryVariant
from app.reader_reports import client_hash, purge_descriptions

from .conftest import requires_postgres
from .test_observability import _auth, _token, client  # noqa: F401  (fixture)

pytestmark = requires_postgres


@pytest.fixture(autouse=True)
def _fresh_limits():
    rate_limit.reset()
    yield
    rate_limit.reset()


def _story(db, status="PUBLISHED"):
    story = Story(canonical_slug=f"s-{uuid.uuid4()}", status=status, published_at=datetime.now(UTC))
    db.add(story)
    db.flush()
    db.add(StoryVariant(story_id=story.id, language="en", headline="Visa rule changes", summary="s", qa_status="PASSED"))
    db.commit()
    return story


def _report(client, story_id, **body):  # noqa: F811
    payload = {"category": "FACTUAL_ERROR", "platform": "web", **body}
    return client.post(f"/v1/stories/{story_id}/reports", json=payload)


def test_report_is_stored_and_analytics_gets_no_text(client, db_session, monkeypatch):  # noqa: F811
    tracked = []
    monkeypatch.setattr(analytics, "track", lambda event, props=None, **kw: tracked.append((event, props)))
    story = _story(db_session)

    response = _report(client, story.id, description="  The date is wrong, call me 555-1234  ", language="te")

    assert response.status_code == 201
    report = db_session.scalars(select(ReaderReport).where(ReaderReport.story_id == story.id)).one()
    assert report.description == "The date is wrong, call me 555-1234"
    assert (report.status, report.category, report.language, report.platform) == ("OPEN", "FACTUAL_ERROR", "te", "web")
    assert len(report.client_hash) == 32
    assert tracked == [("report_issue", {"story_id": str(story.id), "category": "FACTUAL_ERROR", "platform": "web"})]


def test_report_rejects_unknown_or_non_public_story_and_bad_input(client, db_session):  # noqa: F811
    draft = _story(db_session, status="DRAFT")
    assert _report(client, uuid.uuid4()).status_code == 404
    assert _report(client, draft.id).status_code == 404

    live = _story(db_session)
    assert _report(client, live.id, category="NOPE").status_code == 422
    assert _report(client, live.id, description="x" * 2001).status_code == 422
    assert _report(client, live.id, email="me@example.com").status_code == 422


def test_same_sender_repeat_is_counted_not_stored_again(client, db_session):  # noqa: F811
    story = _story(db_session)
    for _ in range(3):
        assert _report(client, story.id).status_code == 201
    assert _report(client, story.id, category="TRANSLATION").status_code == 201

    rows = db_session.scalars(select(ReaderReport).where(ReaderReport.story_id == story.id)).all()
    by_category = {row.category: row.repeat_count for row in rows}
    assert by_category == {"FACTUAL_ERROR": 2, "TRANSLATION": 0}


def test_reports_are_rate_limited_per_client(client, db_session):  # noqa: F811
    stories = [_story(db_session) for _ in range(6)]
    statuses = [_report(client, story.id).status_code for story in stories]
    assert statuses == [201] * 5 + [429]


def test_client_hash_rotates_daily_and_hides_the_ip(monkeypatch):
    monkeypatch.setenv("ADMIN_JWT_SECRET", "test-secret")
    day = datetime(2026, 9, 30, 23, 59, tzinfo=UTC)
    same_day = client_hash("203.0.113.9", day)
    assert same_day == client_hash("203.0.113.9", day.replace(hour=0))
    assert same_day != client_hash("203.0.113.9", day + timedelta(minutes=1))
    assert same_day != client_hash("203.0.113.10", day)
    assert "203.0.113.9" not in same_day


def test_events_endpoint_drops_report_text_and_bounds_properties(client, monkeypatch):  # noqa: F811
    tracked = []
    monkeypatch.setattr(analytics, "track", lambda event, props=None, **kw: tracked.append((event, props)))

    old_app = {"event": "report_issue", "properties": {"story_id": "abc", "description": "x" * 5000}}
    assert client.post("/v1/events", json=old_app).status_code == 200
    assert tracked == [("report_issue", {"story_id": "abc"})]

    too_long = {"event": "search", "properties": {"query": "x" * 501}}
    too_many = {"event": "search", "properties": {f"k{i}": 1 for i in range(21)}}
    nested = {"event": "search", "properties": {"q": {"a": 1}}}
    for body in (too_long, too_many, nested):
        assert client.post("/v1/events", json=body).status_code == 422


def test_admin_lists_and_resolves_with_audited_links(client, db_session):  # noqa: F811
    editor = _auth(_token(client, db_session, role="EDITOR", email="editor@example.com"))
    story = _story(db_session)
    other = _story(db_session)
    _report(client, story.id, description="wrong date")
    _report(client, story.id, category="OTHER")

    assert client.get("/v1/admin/reports").status_code == 401
    listing = client.get("/v1/admin/reports", headers=editor).json()
    assert listing["open_count"] == 2 and listing["total"] == 2
    first = listing["items"][0]
    assert first["story_headline"] == "Visa rule changes" and first["description"] == "wrong date"
    assert len(first["sender"]) == 8

    url = f"/v1/admin/reports/{first['id']}/resolve"
    assert client.post(url, json={"resolution": "CORRECTED"}, headers=editor).json()["error"]["code"] == "CORRECTION_REQUIRED"
    foreign = Correction(story_id=other.id, reason="r", old_text_hash="a", new_text_hash="b")
    mine = Correction(story_id=story.id, reason="fixed date", old_text_hash="a", new_text_hash="c")
    db_session.add_all([foreign, mine])
    db_session.commit()
    bad = client.post(url, json={"resolution": "CORRECTED", "correction_id": str(foreign.id)}, headers=editor)
    assert bad.status_code == 422
    assert client.post(url, json={"resolution": "RETRACTED"}, headers=editor).json()["error"]["code"] == "STORY_NOT_RETRACTED"

    done = client.post(url, json={"resolution": "CORRECTED", "correction_id": str(mine.id), "note": "date fixed"}, headers=editor)
    assert done.status_code == 200
    body = done.json()
    assert (body["status"], body["resolution"], body["resolved_by_email"]) == ("RESOLVED", "CORRECTED", "editor@example.com")
    assert client.post(url, json={"resolution": "SPAM"}, headers=editor).status_code == 409

    second = listing["items"][1]["id"]
    spam = client.post(f"/v1/admin/reports/{second}/resolve", json={"resolution": "SPAM"}, headers=editor).json()
    assert spam["status"] == "DISMISSED"

    audits = db_session.scalars(select(AuditEvent).where(AuditEvent.action == "READER_REPORT_RESOLVED")).all()
    assert {a.metadata_["resolution"] for a in audits} == {"CORRECTED", "SPAM"}
    assert all(a.actor == "editor@example.com" for a in audits)

    assert client.get("/v1/admin/reports", headers=editor).json()["open_count"] == 0
    everything = client.get("/v1/admin/reports?status=ALL", headers=editor).json()
    assert everything["total"] == 2
    assert client.get("/v1/admin/pipeline", headers=editor).json()["reports_open"] == 0


def test_purge_erases_text_on_schedule_and_is_idempotent(db_session):
    now = datetime(2026, 9, 30, tzinfo=UTC)
    story = _story(db_session)

    def row(status, created_days, resolved_days=None, category="OTHER"):
        report = ReaderReport(
            story_id=story.id, category=category, description="text", client_hash=uuid.uuid4().hex,
            status=status, resolution=None if status == "OPEN" else "NO_CHANGE",
            created_at=now - timedelta(days=created_days),
            resolved_at=None if resolved_days is None else now - timedelta(days=resolved_days),
        )
        db_session.add(report)
        return report

    closed_old = row("DISMISSED", 200, resolved_days=91)
    closed_recent = row("DISMISSED", 200, resolved_days=89)
    open_old = row("OPEN", 181)
    open_recent = row("OPEN", 179)
    db_session.commit()

    assert purge_descriptions(db_session, now) == 2
    assert purge_descriptions(db_session, now) == 0
    for report in (closed_old, closed_recent, open_old, open_recent):
        db_session.refresh(report)
    assert (closed_old.description, open_old.description) == (None, None)
    assert closed_old.description_purged_at == now and open_old.status == "OPEN"
    assert (closed_recent.description, open_recent.description) == ("text", "text")


def test_cleanup_job_is_scheduled_once_a_day(db_session):
    assert schedule_cleanup(db_session) is not None
    assert schedule_cleanup(db_session) is None
    db_session.commit()
    job = db_session.scalars(select(Job).where(Job.type == "cleanup")).one()
    assert job.payload == {"task": READER_REPORT_PURGE}
    run_cleanup(db_session, job)
