"""Review 2026-09-30 R5: the admin AI cost report and pipeline status must
reconcile to the rows they aggregate, and keep window spend apart from the
publication cohort's lifecycle cost."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.ai.cost_report import cost_report
from app.models import AiCallLog, AiWorkState, ReviewTask, Story, StoryVariant
from app.pipeline_status import pipeline_status

from .conftest import requires_postgres
from .test_observability import _auth, _token, client  # noqa: F401  (fixture)

pytestmark = requires_postgres

START, END = date(2026, 9, 10), date(2026, 9, 12)


def _at(day: date, hour: int = 12) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def _story(db, status="PUBLISHED", published_at=None, headline=None):
    story = Story(canonical_slug=f"s-{uuid.uuid4()}", status=status, published_at=published_at)
    db.add(story)
    db.flush()
    if headline:
        db.add(StoryVariant(story_id=story.id, language="en", headline=headline, summary="s", qa_status="PASSED"))
    return story


def _call(db, when, *, cost, status="SUCCESS", story=None, provider="openai", model="m1", task="generate", **tokens):
    db.add(AiCallLog(
        task=task, provider=provider, model=model, status=status, story_id=story.id if story else None,
        cost_usd=cost, created_at=when, tokens_in=tokens.get("tin", 100), tokens_out=tokens.get("tout", 50),
        tokens_thinking=tokens.get("think", 0), tokens_cached=tokens.get("cached", 0),
    ))


@pytest.fixture
def seeded(db_session):
    db = db_session
    published = _story(db, published_at=_at(date(2026, 9, 11)), headline="Published in window")
    held = _story(db, status="REVIEW_REQUIRED", headline="Held story")
    # Published in the window, but most of its cost was before it.
    _call(db, _at(date(2026, 9, 1)), cost=1.0, story=published)
    _call(db, _at(START), cost=0.5, story=published, think=20, cached=40)
    _call(db, _at(START, 13), cost=0.25, status="PARSE_ERROR", story=held)
    _call(db, _at(START, 14), cost=0.30, status="RETRY_SUCCESS", story=held)
    _call(db, _at(END, 23), cost=0.10, provider="gemini", model="flash", task="classify")
    _call(db, _at(END, 23), cost=0.0, status="DEFERRED", provider="gemini", model="flash", task="classify")
    # Outside the window on both sides.
    _call(db, datetime(2026, 9, 13, 0, 0, tzinfo=UTC), cost=9.0, story=held)
    _call(db, datetime(2026, 9, 9, 23, 59, tzinfo=UTC), cost=9.0)
    db.commit()
    return published, held


def test_totals_reconcile_to_window_rows(db_session, seeded):
    report = cost_report(db_session, START, END)
    totals = report["totals"]
    assert totals["calls"] == 5
    assert totals["cost_usd"] == pytest.approx(1.15)
    assert totals["unusable_calls"] == 2  # PARSE_ERROR, DEFERRED
    assert totals["unusable_cost_usd"] == pytest.approx(0.25)
    assert totals["retry_cost_usd"] == pytest.approx(0.30)
    assert totals["tokens_thinking"] == 20 and totals["tokens_cached"] == 40

    # Every view adds up to the same totals.
    assert [d["day"] for d in report["by_day"]] == ["2026-09-10", "2026-09-11", "2026-09-12"]
    assert report["by_day"][1]["calls"] == 0
    for view in (report["by_day"], report["breakdown"], report["outcomes"]):
        assert sum(r["calls"] for r in view) == totals["calls"]
        assert sum(r["cost_usd"] for r in view) == pytest.approx(totals["cost_usd"])
    linked = sum(r["cost_usd"] for r in report["by_story_status"])
    assert linked + report["unlinked"]["cost_usd"] == pytest.approx(totals["cost_usd"])
    assert report["unlinked"]["calls"] == 2


def test_breakdown_tiers_and_story_drilldown(db_session, seeded):
    published, held = seeded
    report = cost_report(db_session, START, END)
    tiers = {(r["provider"], r["task"]): r["tier"] for r in report["breakdown"]}
    assert tiers == {("openai", "generate"): "PAID", ("gemini", "classify"): "FREE"}

    by_status = {r["status"]: r for r in report["by_story_status"]}
    assert by_status["REVIEW_REQUIRED"]["cost_usd"] == pytest.approx(0.55)
    assert by_status["PUBLISHED"]["stories"] == 1

    top = report["top_stories"]
    assert [s["story_id"] for s in top] == [held.id, published.id]
    assert top[0]["headline"] == "Held story" and top[0]["unusable_calls"] == 1


def test_publication_cohort_is_lifecycle_cost_not_window_spend(db_session, seeded):
    cohort = cost_report(db_session, START, END)["publication_cohort"]
    # The 2026-09-01 call counts: it belongs to a story published in range.
    assert cohort == {"stories_published": 1, "lifecycle_calls": 2, "lifecycle_cost_usd": pytest.approx(1.5)}


def test_endpoint_defaults_and_bounds(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    body = client.get("/v1/admin/ai-costs", headers=_auth(token)).json()
    today = datetime.now(UTC).date()
    assert body["start"] == today.replace(day=1).isoformat() and body["end"] == today.isoformat()
    assert len(body["by_day"]) == today.day

    bad = client.get("/v1/admin/ai-costs?start=2026-09-12&end=2026-09-10", headers=_auth(token))
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_RANGE"
    long = client.get("/v1/admin/ai-costs?start=2026-01-01&end=2026-09-10", headers=_auth(token))
    assert long.status_code == 422 and long.json()["error"]["code"] == "RANGE_TOO_LONG"
    assert client.get("/v1/admin/ai-costs").status_code == 401
    assert client.get("/v1/admin/pipeline").status_code == 401


def test_pipeline_status_counts_and_ages(db_session):
    db = db_session
    now = datetime(2026, 9, 30, 12, tzinfo=UTC)
    english_only = _story(db, published_at=now - timedelta(hours=30), headline="EN only")
    failed_te = _story(db, status="UPDATED", published_at=now - timedelta(hours=2), headline="TE failed")
    db.add(StoryVariant(story_id=failed_te.id, language="te", headline="h", summary="s", qa_status="FAILED"))
    bilingual = _story(db, published_at=now - timedelta(hours=1), headline="Both")
    db.add(StoryVariant(story_id=bilingual.id, language="te", headline="h", summary="s", qa_status="PASSED"))
    review = _story(db, status="REVIEW_REQUIRED")
    db.add(ReviewTask(story_id=review.id, reason="LOW_CONFIDENCE", created_at=now - timedelta(hours=5)))
    draft = _story(db, status="DRAFT")
    db.add_all([
        AiWorkState(story_id=draft.id, stage="GENERATE", input_version="v", failure_class="TRANSIENT", updated_at=now),
        AiWorkState(story_id=english_only.id, stage="TRANSLATE", input_version="v", failure_class="EXHAUSTED",
                    updated_at=now - timedelta(hours=3)),
    ])
    db.commit()

    status = pipeline_status(db, now)
    assert status["stories_by_status"] == {"PUBLISHED": 2, "UPDATED": 1, "REVIEW_REQUIRED": 1, "DRAFT": 1}
    assert status["published_24h"] == 2
    assert status["review_pending"] == 1 and status["review_oldest_at"] == now - timedelta(hours=5)
    assert status["ai_work"] == [
        {"stage": "GENERATE", "retrying": 1, "exhausted": 0, "oldest_update_at": now},
        {"stage": "TRANSLATE", "retrying": 0, "exhausted": 1, "oldest_update_at": now - timedelta(hours=3)},
    ]
    assert status["telugu_missing"] == 2 and status["telugu_failed_qa"] == 1
    assert status["telugu_missing_oldest_published_at"] == now - timedelta(hours=30)
