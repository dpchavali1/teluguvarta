"""ADR-053: coverage monitor. Notices important Telugu/diaspora news we miss.

Every `COVERAGE_MONITOR_INTERVAL_MINUTES` the worker fetches a few REFERENCE
headline feeds (Google News RSS by default) and checks each recent headline
against what we already hold. A headline with no match is a MISS and raises one
deduped alert.

Reference headlines are monitor-only: never ingested, never a Story/SourceItem,
never republished or shown to readers. We keep only title/url/source/hash in
`audit_events` (`COVERAGE_MONITOR_SEEN`), deleted after 7 days. Off unless
`COVERAGE_MONITOR_INTERVAL_MINUTES` is set. No AI calls; no migration.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import unicodedata
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.adapters.feed_probe import MAX_BYTES
from app.adapters.rss import RssFeedAdapter
from app.adapters.safe_fetch import FeedFetchError, Resolver, fetch_public
from app.alerts import send_alert
from app.models import AuditEvent, Source, SourceItem, StoryVariant
from app.observability.logging import get_logger

logger = get_logger("coverage_monitor")

INTERVAL_ENV = "COVERAGE_MONITOR_INTERVAL_MINUTES"  # unset/0 = off
FEEDS_ENV = "COVERAGE_MONITOR_FEEDS"  # "name|url" entries separated by newlines
MAX_ALERTS_PER_RUN_ENV = "COVERAGE_MONITOR_MAX_ALERTS_PER_RUN"
MAX_ALERTS_PER_DAY_ENV = "COVERAGE_MONITOR_MAX_ALERTS_PER_DAY"

ACTOR = "system:coverage-monitor"
SEEN = "COVERAGE_MONITOR_SEEN"
ALERT_FAILED = "COVERAGE_MONITOR_ALERT_FAILED"
ENTITY_TYPE = "coverage_reference"

FRESH_WITHIN = timedelta(hours=3)
LOOKBACK = timedelta(hours=48)
RETENTION = timedelta(days=7)
MAX_ALERT_ATTEMPTS = 3
MAX_ITEMS_PER_FEED = 40
MIN_TOKEN_LEN = 3
MIN_SHARED = 2
MIN_COVERAGE = 0.5
TITLE_SIMILARITY = 0.72
TELUGU_PREFIX = 4  # Telugu words inflect; a shared 4-char stem counts as the same word

_NS = uuid.UUID("5f0b3f4e-53c6-4c1d-9a55-0d6f2c0f53a0")
_STOP = frozenset(
    ["the", "and", "for", "with", "from", "that", "this", "has", "have", "are", "was", "were", "will", "after", "over", "into", "about", "says", "said", "news", "live", "update", "updates", "new", "latest"]
)

# Monitoring queries only. `when:1d` keeps the result set to the last day.
DEFAULT_FEEDS: tuple[tuple[str, str], ...] = (
    ("Google News Telugu", "https://news.google.com/rss?hl=te&gl=IN&ceid=IN:te"),
    (
        "Google News AP/TS/Tollywood",
        "https://news.google.com/rss/search?q="
        + quote("Andhra Pradesh OR Telangana OR Tollywood OR Telugu when:1d")
        + "&hl=en-IN&gl=IN&ceid=IN:en",
    ),
)


def interval_minutes() -> int:
    try:
        return max(0, int(os.environ.get(INTERVAL_ENV, "0")))
    except ValueError:
        return 0


def enabled() -> bool:
    return interval_minutes() > 0


def configured_feeds() -> list[tuple[str, str]]:
    raw = os.environ.get(FEEDS_ENV, "").strip()
    if not raw:
        return list(DEFAULT_FEEDS)
    feeds = []
    for line in raw.splitlines():
        name, sep, url = line.partition("|")
        if sep and url.strip():
            feeds.append((name.strip() or url.strip(), url.strip()))
    return feeds


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


def tokens(text: str | None) -> set[str]:
    """Lowercase words with punctuation/symbols (by Unicode category, so Telugu
    vowel signs stay attached) turned to spaces; short tokens and stopwords dropped."""
    if not text:
        return set()
    cleaned = "".join(" " if unicodedata.category(ch)[0] in "PSZC" else ch for ch in text.lower())
    return {t for t in cleaned.split() if len(t) >= MIN_TOKEN_LEN and t not in _STOP}


def _is_telugu(token: str) -> bool:
    return any("ఀ" <= ch <= "౿" for ch in token)


def _same_word(a: str, b: str) -> bool:
    if a == b:
        return True
    return _is_telugu(a) and _is_telugu(b) and a[:TELUGU_PREFIX] == b[:TELUGU_PREFIX] and min(len(a), len(b)) >= TELUGU_PREFIX


def _norm(text: str) -> str:
    return " ".join(sorted(tokens(text)))


def matches(reference_title: str, candidate_texts: list[str]) -> bool:
    """Deterministic: token overlap (>= 2 shared words covering >= half the
    reference headline) or a difflib title ratio, against any candidate text."""
    ref = tokens(reference_title)
    if not ref:
        return True  # nothing meaningful to compare: never alert on it
    ref_norm = _norm(reference_title)
    for text in candidate_texts:
        cand = tokens(text)
        shared = sum(1 for r in ref if any(_same_word(r, c) for c in cand))
        if shared >= MIN_SHARED and shared / len(ref) >= MIN_COVERAGE:
            return True
        if difflib.SequenceMatcher(None, ref_norm, _norm(text)).ratio() >= TITLE_SIMILARITY:
            return True
    return False


def recent_story_texts(db: Session, now: datetime) -> list[str]:
    """Headlines/summaries of anything we hold from the last 48h, any status:
    story variants (en + te) and source-item titles (so a pipeline lag is not
    reported as a coverage miss)."""
    since = now - LOOKBACK
    texts: list[str] = []
    for headline, summary in db.execute(
        select(StoryVariant.headline, StoryVariant.summary).where(StoryVariant.generated_at >= since)
    ):
        texts.append(f"{headline} {summary}")
    texts += [t for (t,) in db.execute(select(SourceItem.title).where(SourceItem.published_at >= since)) if t]
    return texts


def reference_key(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}\n{title}".encode()).hexdigest()


def _entity_id(key: str) -> uuid.UUID:
    return uuid.uuid5(_NS, key)


def fetch_reference(
    client: httpx.Client, feeds: list[tuple[str, str]], now: datetime, resolve: Resolver | None = None
) -> list[dict[str, Any]]:
    """Fresh reference headlines as dicts (title/url/source/published_at). A feed
    that fails is logged and skipped; the other feeds still run."""
    found: list[dict[str, Any]] = []
    for name, url in feeds:
        try:
            body = fetch_public(client, url, max_bytes=MAX_BYTES, resolve=resolve)
            items = RssFeedAdapter(Source(name=name)).parse(body).items[:MAX_ITEMS_PER_FEED]
        except (FeedFetchError, httpx.HTTPError, ParseError, DefusedXmlException) as exc:
            logger.warning("coverage monitor feed %r failed: %s", name, type(exc).__name__)
            continue
        for item in items:
            if not item.title or not item.url or item.published_at is None:
                continue
            published = item.published_at if item.published_at.tzinfo else item.published_at.replace(tzinfo=UTC)
            if now - published > FRESH_WITHIN or published > now + timedelta(minutes=10):
                continue
            found.append({"title": item.title, "url": item.url, "source": name, "published_at": published})
    return found


def _alerts_sent_today(db: Session, now: datetime) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.action == SEEN,
                AuditEvent.metadata_["alerted"].astext == "true",
                AuditEvent.created_at >= now - timedelta(hours=24),
            )
        )
        or 0
    )


def run_coverage_monitor(
    db: Session,
    *,
    now: datetime | None = None,
    client: httpx.Client | None = None,
    feeds: list[tuple[str, str]] | None = None,
    resolve: Resolver | None = None,
    channel: Callable[[str, str], None] | None = None,
) -> dict[str, int]:
    """One monitor pass. Idempotent: a reference headline already recorded is
    skipped, so overlapping runs never double-alert."""
    now = now or datetime.now(UTC)
    owns_client = client is None
    client = client or httpx.Client()
    try:
        reference = fetch_reference(client, feeds if feeds is not None else configured_feeds(), now, resolve)
    finally:
        if owns_client:
            client.close()

    stats = {"seen": 0, "matched": 0, "missed": 0, "alerted": 0}
    candidates = recent_story_texts(db, now)
    per_run = _int_env(MAX_ALERTS_PER_RUN_ENV, 5)
    per_day_left = _int_env(MAX_ALERTS_PER_DAY_ENV, 20) - _alerts_sent_today(db, now)

    for ref in reference:
        key = reference_key(ref["url"], ref["title"])
        entity_id = _entity_id(key)
        if db.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.action == SEEN, AuditEvent.entity_type == ENTITY_TYPE, AuditEvent.entity_id == entity_id
            )
        ):
            continue
        stats["seen"] += 1
        matched = matches(ref["title"], candidates)
        meta: dict[str, Any] = {
            "title": ref["title"][:300], "url": ref["url"][:500], "source": ref["source"],
            "hash": key, "matched": matched, "alerted": False,
            "published_at": ref["published_at"].isoformat(),
        }
        if matched:
            stats["matched"] += 1
        else:
            stats["missed"] += 1
            failures = db.scalar(
                select(func.count()).select_from(AuditEvent).where(
                    AuditEvent.action == ALERT_FAILED, AuditEvent.entity_id == entity_id
                )
            ) or 0
            if stats["alerted"] < per_run and per_day_left > 0 and failures < MAX_ALERT_ATTEMPTS:
                try:
                    send_alert(
                        f"Possible coverage miss: \"{ref['title']}\" {ref['url']} (reference: {ref['source']})",
                        severity="WARNING", channel=channel,
                    )
                    meta["alerted"] = True
                    stats["alerted"] += 1
                    per_day_left -= 1
                except Exception as exc:  # noqa: BLE001 - a broken channel must not stop the sweep
                    logger.warning("coverage alert delivery failed: %s", exc)
                    db.add(AuditEvent(actor=ACTOR, action=ALERT_FAILED, entity_type=ENTITY_TYPE, entity_id=entity_id, metadata_={}))
                    db.flush()
                    continue  # retried next run (bounded), not recorded as seen yet
        db.add(AuditEvent(actor=ACTOR, action=SEEN, entity_type=ENTITY_TYPE, entity_id=entity_id, metadata_=meta))
        db.flush()

    db.execute(
        delete(AuditEvent).where(
            AuditEvent.actor == ACTOR, AuditEvent.entity_type == ENTITY_TYPE, AuditEvent.created_at < now - RETENTION
        )
    )
    db.commit()
    logger.info("coverage monitor: %s", stats)
    return stats


def miss_report(db: Session, now: datetime | None = None, limit: int = 50) -> dict[str, Any]:
    """Admin read-only view: last `limit` misses and the 24h matched/unmatched split."""
    now = now or datetime.now(UTC)
    since = now - timedelta(hours=24)
    matched_expr = AuditEvent.metadata_["matched"].astext.label("matched")
    rows = db.execute(
        select(matched_expr, func.count())
        .where(AuditEvent.action == SEEN, AuditEvent.created_at >= since)
        .group_by(matched_expr)
    ).all()
    counts = {k: v for k, v in rows}
    matched, missed = counts.get("true", 0), counts.get("false", 0)
    total = matched + missed
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == SEEN, AuditEvent.metadata_["matched"].astext == "false")
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "enabled": enabled(),
        "matched_24h": matched,
        "missed_24h": missed,
        "miss_rate_24h": round(missed / total, 3) if total else 0.0,
        "misses": [
            {
                "title": e.metadata_.get("title", ""), "url": e.metadata_.get("url", ""),
                "source": e.metadata_.get("source", ""), "seen_at": e.created_at, "alerted": bool(e.metadata_.get("alerted")),
            }
            for e in events
        ],
    }


_last_run: datetime | None = None


def maybe_run(db: Session, now: datetime | None = None) -> dict[str, int] | None:
    """Worker hook: runs at most once per interval (per process); a restart just
    runs once early, which dedupe by hash makes harmless."""
    global _last_run
    minutes = interval_minutes()
    now = now or datetime.now(UTC)
    if minutes <= 0 or (_last_run and now - _last_run < timedelta(minutes=minutes)):
        return None
    _last_run = now
    try:
        return run_coverage_monitor(db, now=now)
    except Exception as exc:  # noqa: BLE001 - monitoring must never take the worker down
        db.rollback()
        logger.warning("coverage monitor failed: %s", exc)
        return None
