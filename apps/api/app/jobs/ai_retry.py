"""Durable per-story retry state for the AI sweeps (review 2026-09-29 #1).

`ai_classify`/`ai_translate` are time-bucketed: every sweep is a new queue
job, so the queue's own bounded `attempts` never limited how many times one
story went back to the provider. This module keeps that bound per story and
stage in `ai_work_state`, so NON_NEGOTIABLES #10 ("bounded in retries")
holds across sweeps, not just within one job row:

- a transient outcome (quota deferral, provider unavailable, budget
  degradation) backs off exponentially and gives up after
  `MAX_TRANSIENT_FAILURES`;
- an invalid result (schema failure after the gateway's own retry, a
  fabricated citation) gives up after `MAX_INVALID_ATTEMPTS`;
- a change in the stage's input (new evidence, a corrected English variant)
  starts the count again, since it is new work.

What happens to an exhausted story is the caller's call (generation routes
it to editorial review; translation leaves the English fallback in place).
Resetting an exhausted row by hand is not implemented here — see the
held-story recovery ADR.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import GatewayStatus
from app.models import AiWorkState

STAGE_GENERATE = "GENERATE"
STAGE_TRANSLATE = "TRANSLATE"

BACKOFF_BASE = timedelta(minutes=2)  # one sweep interval
BACKOFF_MAX = timedelta(hours=6)
# 2+4+...+256 min, then 6h steps: roughly three days of transient failure.
MAX_TRANSIENT_FAILURES = 20
MAX_INVALID_ATTEMPTS = 3

# Review 2026-09-29 #8: one sweep job attempts at most this many stories,
# and starts no new story after the time budget, so a backlog can't hold the
# single worker (and publishing, push, alerts behind it) for long. Each story
# gets a fresh job lease (`queue.renew_lease`), so the lease only has to
# cover one story's worst case: two calls, each with one schema retry, at
# the provider's 60 s timeout.
SWEEP_BATCH_SIZE_ENV = "AI_SWEEP_BATCH_SIZE"
DEFAULT_SWEEP_BATCH_SIZE = 10
SWEEP_TIME_BUDGET = timedelta(seconds=120)


def sweep_batch_size() -> int:
    try:
        return max(1, int(os.environ.get(SWEEP_BATCH_SIZE_ENV, DEFAULT_SWEEP_BATCH_SIZE)))
    except ValueError:
        return DEFAULT_SWEEP_BATCH_SIZE


def monotonic() -> float:
    return time.monotonic()


TRANSIENT_STATUSES = frozenset(
    {GatewayStatus.DEFERRED, GatewayStatus.UNAVAILABLE, GatewayStatus.CLASSIFICATION_ONLY}
)


def _now() -> datetime:
    return datetime.now(UTC)


def input_version(payload: object) -> str:
    """A stable fingerprint of what the stage would send the model. Hash the
    inputs, not the prompt: prompts carry a random per-call boundary."""
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_state(db: Session, story_id, stage: str, version: str) -> AiWorkState | None:
    """The stage's state for this input version; a row left from an older
    version is reset, since the work it counted no longer applies."""
    state = db.scalars(
        select(AiWorkState).where(AiWorkState.story_id == story_id, AiWorkState.stage == stage)
    ).first()
    if state is not None and state.input_version != version:
        state.input_version = version
        state.invalid_attempts = 0
        state.transient_failures = 0
        state.next_attempt_at = None
        state.last_status = None
        state.failure_class = None
        state.cached_classification = None
        state.updated_at = _now()
        db.flush()
    return state


def is_due(state: AiWorkState | None, now: datetime | None = None) -> bool:
    if state is None:
        return True
    if state.failure_class == "EXHAUSTED":
        return False
    return state.next_attempt_at is None or state.next_attempt_at <= (now or _now())


def _get_or_create(db: Session, state: AiWorkState | None, story_id, stage: str, version: str) -> AiWorkState:
    if state is not None:
        return state
    state = AiWorkState(story_id=story_id, stage=stage, input_version=version, invalid_attempts=0, transient_failures=0)
    db.add(state)
    return state


def record_failure(
    db: Session,
    state: AiWorkState | None,
    *,
    story_id,
    stage: str,
    version: str,
    status: GatewayStatus,
    now: datetime | None = None,
) -> AiWorkState:
    """Counts one failed attempt and schedules the next. Returns the state;
    `failure_class == "EXHAUSTED"` means the caller must stop retrying."""
    now = now or _now()
    state = _get_or_create(db, state, story_id, stage, version)
    if status in TRANSIENT_STATUSES:
        state.transient_failures += 1
        failures, limit, failure_class = state.transient_failures, MAX_TRANSIENT_FAILURES, "TRANSIENT"
    else:
        state.invalid_attempts += 1
        failures, limit, failure_class = state.invalid_attempts, MAX_INVALID_ATTEMPTS, "INVALID_OUTPUT"
    state.last_status = status.value
    if failures >= limit:
        state.failure_class = "EXHAUSTED"
        state.next_attempt_at = None
    else:
        state.failure_class = failure_class
        state.next_attempt_at = now + min(BACKOFF_BASE * (2 ** (failures - 1)), BACKOFF_MAX)
    state.updated_at = now
    db.flush()
    return state


def cache_classification(
    db: Session, state: AiWorkState | None, *, story_id, version: str, status: GatewayStatus, result: dict
) -> AiWorkState:
    """Keeps a successful classification for this input version, so a later
    summary failure doesn't pay to classify the same evidence again."""
    state = _get_or_create(db, state, story_id, STAGE_GENERATE, version)
    state.cached_classification = {"status": status.value, "result": result}
    state.updated_at = _now()
    db.flush()
    return state


def clear(db: Session, state: AiWorkState | None) -> None:
    if state is not None:
        db.delete(state)
        db.flush()
