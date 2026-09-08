"""Deterministic fingerprint + lexical-similarity dedup/clustering (T09).

Turns NORMALIZED `SourceItem`s into `Story` clusters without an AI call for
the common case, per §7.2's model-routing table: "Dedup/clustering:
fingerprint + lexical similarity first; embedding/model only for ambiguous
pairs." The AI gateway itself doesn't exist until T10, so `_escalate_to_ai`
is a stub other tickets fill in — a pair whose similarity falls between the
two thresholds is conservatively treated as *not* matching until then
(two separate stories is a safer default than wrongly merging unrelated
ones).

Fingerprinting and clustering happen in one deterministic pass here, so the
§6.4 `DEDUPED` state is never persisted on its own — a `SourceItem` goes
straight from `NORMALIZED` to `CLUSTERED`.
"""

from __future__ import annotations

import difflib
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.queue import enqueue_job
from app.models import Job, SourceItem, Story, StorySource

# How often the worker re-triggers a clustering pass. Time-bucketed like
# `source_fetch.schedule_due_source_fetches`, so repeated scheduler calls
# within one window are a no-op (the `dedupe_key` unique constraint) and a
# fresh key is available next window.
DEDUP_CLUSTER_INTERVAL_MINUTES = 2

# Two normalized titles at or above this difflib ratio (0..1) are treated as
# the same underlying event without an AI call.
SIMILARITY_MATCH_THRESHOLD = 0.72
# At or below this, treat as definitely different stories.
SIMILARITY_NO_MATCH_THRESHOLD = 0.4
# Only compare against items published within this window of each other —
# an unbounded comparison would eventually false-match unrelated stories
# that happen to share generic wording, and would make each pass scan every
# `CLUSTERED` item ever seen.
CLUSTER_WINDOW = timedelta(hours=72)

_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalized_title_key(title: str) -> str:
    """Lowercased, punctuation-stripped, whitespace-collapsed title text —
    the fingerprint text. Two items with an equal, non-empty key are
    definite duplicates, no similarity scoring needed."""
    key = title.lower()
    key = _PUNCTUATION_RE.sub("", key)
    key = _WHITESPACE_RE.sub(" ", key).strip()
    return key


def _escalate_to_ai(item_a: SourceItem, item_b: SourceItem) -> bool:
    """TODO(T10/T11): route ambiguous pairs (similarity between the two
    thresholds) through the AI gateway's embedding/model comparison once it
    exists. Until then, ambiguous pairs are treated as not matching."""
    return False


def _same_story(a: SourceItem, b: SourceItem) -> bool:
    key_a, key_b = normalized_title_key(a.title or ""), normalized_title_key(b.title or "")
    if key_a and key_a == key_b:
        return True
    similarity = difflib.SequenceMatcher(None, key_a, key_b).ratio()
    if similarity >= SIMILARITY_MATCH_THRESHOLD:
        return True
    if similarity <= SIMILARITY_NO_MATCH_THRESHOLD:
        return False
    return _escalate_to_ai(a, b)


def _within_window(a: SourceItem, b: SourceItem) -> bool:
    if a.published_at is None or b.published_at is None:
        return True
    return abs(a.published_at - b.published_at) <= CLUSTER_WINDOW


def _slug_for(item: SourceItem) -> str:
    key = normalized_title_key(item.title or "") or "story"
    slug = re.sub(r"\s+", "-", key)[:150]
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def _find_matching_story(db: Session, item: SourceItem) -> uuid.UUID | None:
    """Looks for an already-`CLUSTERED` item close enough to `item` to share
    its `Story`. Only ever compares against items already attached to a
    story, so clustering a batch of N new items in order naturally groups
    ones that match each other too — the first of a group creates the
    `Story`, the rest attach to it."""
    clustered = db.scalars(
        select(SourceItem).where(SourceItem.ingest_status == "CLUSTERED", SourceItem.id != item.id)
    ).all()
    for candidate in clustered:
        if not _within_window(item, candidate):
            continue
        if _same_story(item, candidate):
            story_source = db.scalars(
                select(StorySource).where(StorySource.source_item_id == candidate.id)
            ).first()
            if story_source is not None:
                return story_source.story_id
    return None


def cluster_normalized_items(db: Session) -> int:
    """Processes every `SourceItem` currently `NORMALIZED`, attaching each
    to a matching `Story` (existing or newly created) via `StorySource`, and
    advances it to `CLUSTERED`. Idempotent: only `NORMALIZED` items are ever
    considered, and each leaves that state as it's placed, so a re-run with
    no new `NORMALIZED` items is a no-op — no duplicate `Story` rows or
    `StorySource` links.

    Processes in a stable order (oldest `published_at` first, nulls last)
    so that within one pass, an earlier item in a matching pair creates the
    `Story` and a later one attaches to it deterministically.
    """
    pending = db.scalars(
        select(SourceItem)
        .where(SourceItem.ingest_status == "NORMALIZED")
        .order_by(SourceItem.published_at.is_(None), SourceItem.published_at, SourceItem.id)
    ).all()

    processed = 0
    for item in pending:
        story_id = _find_matching_story(db, item)
        if story_id is None:
            story = Story(canonical_slug=_slug_for(item))
            db.add(story)
            db.flush()
            story_id = story.id
            role, evidence_rank = "PRIMARY", 1
        else:
            existing_links = db.scalars(
                select(StorySource).where(StorySource.story_id == story_id)
            ).all()
            role = "SUPPORTING"
            evidence_rank = len(existing_links) + 1

        db.add(StorySource(story_id=story_id, source_item_id=item.id, role=role, evidence_rank=evidence_rank))
        item.ingest_status = "CLUSTERED"
        processed += 1

    db.commit()
    return processed


def run_dedup_cluster(db: Session, job: Job) -> None:
    """Job handler wrapping `cluster_normalized_items` for the worker."""
    cluster_normalized_items(db)


def _cluster_window(now: datetime) -> datetime:
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    elapsed_minutes = int((now - epoch).total_seconds() // 60)
    bucket_start_minutes = (elapsed_minutes // DEDUP_CLUSTER_INTERVAL_MINUTES) * DEDUP_CLUSTER_INTERVAL_MINUTES
    return epoch + timedelta(minutes=bucket_start_minutes)


def schedule_dedup_cluster(db: Session) -> Job | None:
    """Enqueues one `dedup_cluster` job per `DEDUP_CLUSTER_INTERVAL_MINUTES`
    window, so the worker keeps sweeping `NORMALIZED` items into `Story`
    clusters on its own cadence without a caller having to track state."""
    now = datetime.now(UTC)
    dedupe_key = f"dedup_cluster:{_cluster_window(now).isoformat()}"
    return enqueue_job(db, "dedup_cluster", {}, dedupe_key=dedupe_key)
