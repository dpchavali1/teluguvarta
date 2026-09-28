"""ADR-015 decision 6: free-tier quota handling. RPM via an in-process token
bucket per model (the worker is a single process; a second process would need
a shared bucket); RPD counted from `ai_call_log` over the Pacific quota day so
it survives restarts and includes unavailable/deferred attempts.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.budget import quota_day_start
from app.models import AiCallLog


@dataclass(frozen=True)
class Limits:
    rpm: int
    rpd: int


# Confirmed 2026-09-28 (ADR-015). Keyed by model id as passed to the provider,
# so a pinned id set via AI_GEMINI_*_MODEL needs its own entry.
FREE_TIER_LIMITS: dict[str, Limits] = {
    "gemini-flash-latest": Limits(rpm=5, rpd=20),
    "gemini-flash-lite-latest": Limits(rpm=15, rpd=500),
}


class TokenBucket:
    def __init__(self, rpm: int, clock=time.monotonic):
        self._capacity = float(rpm)
        self._rate = rpm / 60.0
        self._tokens = float(rpm)
        self._clock = clock
        self._last = clock()
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        with self._lock:
            now = self._clock()
            self._tokens = min(self._capacity, self._tokens + (now - self._last) * self._rate)
            self._last = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


_buckets: dict[str, TokenBucket] = {}
_buckets_lock = threading.Lock()


def _bucket(model: str, limits: Limits) -> TokenBucket:
    with _buckets_lock:
        if model not in _buckets:
            _buckets[model] = TokenBucket(limits.rpm)
        return _buckets[model]


def requests_today(db: Session, model: str, now: datetime | None = None) -> int:
    from datetime import UTC

    now = now or datetime.now(UTC)
    count = db.scalar(
        select(func.count()).select_from(AiCallLog).where(
            AiCallLog.provider == "gemini",
            AiCallLog.model == model,
            AiCallLog.created_at >= quota_day_start(now),
        )
    )
    return int(count or 0)


def acquire(db: Session, model: str, now: datetime | None = None) -> bool:
    """True if a free-tier call to `model` may proceed now. Models with no
    configured limits are refused: an unknown model must not run unmetered."""
    limits = FREE_TIER_LIMITS.get(model)
    if limits is None:
        return False
    if requests_today(db, model, now) >= limits.rpd:
        return False
    return _bucket(model, limits).try_acquire()
