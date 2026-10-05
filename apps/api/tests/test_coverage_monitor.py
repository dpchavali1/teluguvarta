"""ADR-053: reference headlines are matched against what we hold, misses alert
once (capped), nothing from the reference feed is stored as a story."""

import uuid
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx

from app import coverage_monitor as cm
from app.models import AuditEvent, SourceItem, Story, StoryVariant

from .conftest import requires_postgres
from .test_observability import _auth, _token, client  # noqa: F401  (fixture)

NOW = datetime.now(UTC).replace(microsecond=0)  # events carry the DB's clock, so use real time


def _feed(*items: tuple[str, str, datetime]) -> bytes:
    body = "".join(
        f"<item><title>{t}</title><link>{u}</link><guid>{u}</guid><pubDate>{format_datetime(p)}</pubDate></item>"
        for t, u, p in items
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{body}</channel></rss>'.encode()


def _client(body: bytes) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)))


class _Chan:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def __call__(self, severity, message):
        if self.fail:
            raise RuntimeError("down")
        self.calls.append(message)


FEEDS = [("Ref", "https://ref.example/rss")]


def test_matching_english_and_telugu():
    held = ["Pawan Kalyan inaugurates new highway in Andhra Pradesh"]
    assert cm.matches("Pawan Kalyan opens highway, Andhra Pradesh", held)
    assert not cm.matches("Hyderabad metro fare hike announced", held)
    te = ["హైదరాబాద్ లో భారీ వర్షాలు కురుస్తున్నాయి రోడ్లు జలమయం"]
    assert cm.matches("హైదరాబాద్ భారీ వర్షాలు రోడ్లు జలమయం", te)
    assert not cm.matches("విశాఖ ఉక్కు ఫ్యాక్టరీ ప్రైవేటీకరణ నిరసన", te)


def test_env_defaults(monkeypatch):
    monkeypatch.delenv(cm.INTERVAL_ENV, raising=False)
    assert not cm.enabled() and cm.maybe_run(None) is None  # type: ignore[arg-type]
    monkeypatch.setenv(cm.FEEDS_ENV, "A|https://a.example/rss\nbad line")
    assert cm.configured_feeds() == [("A", "https://a.example/rss")]
    monkeypatch.delenv(cm.FEEDS_ENV)
    assert len(cm.configured_feeds()) == 2


def test_fetch_filters_stale_and_blocks_private(monkeypatch):
    body = _feed(("Fresh one here", "https://x/1", NOW - timedelta(hours=1)), ("Old story here", "https://x/2", NOW - timedelta(hours=9)))
    items = cm.fetch_reference(_client(body), FEEDS, NOW)
    assert [i["title"] for i in items] == ["Fresh one here"]
    monkeypatch.setattr("app.adapters.safe_fetch._resolve", lambda host: ["10.0.0.1"])
    assert cm.fetch_reference(_client(body), FEEDS, NOW) == []


@requires_postgres
def test_run_records_misses_alerts_once_and_stores_no_story(db_session):
    db = db_session
    story = Story(canonical_slug=f"s-{uuid.uuid4()}", status="REVIEW_REQUIRED")
    db.add(story)
    db.flush()
    db.add(StoryVariant(story_id=story.id, language="en", headline="Chiranjeevi film release date announced", summary="Tollywood star film", generated_at=NOW - timedelta(hours=5)))
    db.flush()
    tag = uuid.uuid4().hex[:6]
    body = _feed(
        ("Chiranjeevi film release date announced today", f"https://x/{tag}/1", NOW - timedelta(hours=1)),
        (f"Quake{tag} hits Godavari delta districts badly", f"https://x/{tag}/2", NOW - timedelta(hours=1)),
    )
    before_stories = db.query(Story).count()
    before_items = db.query(SourceItem).count()
    chan = _Chan()
    stats = cm.run_coverage_monitor(db, now=NOW, client=_client(body), feeds=FEEDS, channel=chan)
    assert stats == {"seen": 2, "matched": 1, "missed": 1, "alerted": 1}
    assert len(chan.calls) == 1 and "Godavari" in chan.calls[0] and f"https://x/{tag}/2" in chan.calls[0]
    again = cm.run_coverage_monitor(db, now=NOW, client=_client(body), feeds=FEEDS, channel=chan)
    assert again["seen"] == 0 and len(chan.calls) == 1
    assert db.query(Story).count() == before_stories and db.query(SourceItem).count() == before_items
    report = cm.miss_report(db, NOW)
    assert any(m["url"].endswith(f"{tag}/2") for m in report["misses"])
    assert report["missed_24h"] >= 1


@requires_postgres
def test_caps_failures_and_retention(db_session, monkeypatch):
    db = db_session
    monkeypatch.setenv(cm.MAX_ALERTS_PER_RUN_ENV, "2")
    tag = uuid.uuid4().hex[:6]
    body = _feed(*[(f"Zzq{tag}{i} unmatched headline words{i}", f"https://x/{tag}/{i}", NOW - timedelta(minutes=30)) for i in range(4)])
    chan = _Chan()
    stats = cm.run_coverage_monitor(db, now=NOW, client=_client(body), feeds=FEEDS, channel=chan)
    assert stats["missed"] == 4 and stats["alerted"] == 2
    # a broken channel: failure recorded, headline retried, bounded
    body2 = _feed((f"Qqx{tag} another unmatched headline", f"https://x/{tag}/f", NOW - timedelta(minutes=30)))
    bad = _Chan(fail=True)
    for _ in range(5):
        cm.run_coverage_monitor(db, now=NOW, client=_client(body2), feeds=FEEDS, channel=bad)
    failed = db.query(AuditEvent).filter(AuditEvent.action == cm.ALERT_FAILED, AuditEvent.entity_id == cm._entity_id(cm.reference_key(f"https://x/{tag}/f", f"Qqx{tag} another unmatched headline"))).count()
    assert failed == cm.MAX_ALERT_ATTEMPTS
    # retention: old events are pruned
    old = AuditEvent(actor=cm.ACTOR, action=cm.SEEN, entity_type=cm.ENTITY_TYPE, entity_id=uuid.uuid4(), metadata_={"matched": False})
    db.add(old)
    db.flush()
    old.created_at = NOW - timedelta(days=8)
    db.flush()
    cm.run_coverage_monitor(db, now=NOW, client=_client(_feed()), feeds=FEEDS, channel=chan)
    assert db.get(AuditEvent, old.id) is None


@requires_postgres
def test_endpoint(client, db_session):  # noqa: F811
    token = _token(client, db_session)
    body = client.get("/v1/admin/coverage/misses", headers=_auth(token)).json()
    assert {"enabled", "matched_24h", "missed_24h", "miss_rate_24h", "misses"} <= body.keys()
    assert client.get("/v1/admin/coverage/misses").status_code == 401
