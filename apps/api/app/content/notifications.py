"""§9.4 notification eligibility (T17) — pure, deterministic, no AI/model
call, same "prefer deterministic code" default as `app/content/ranking.py`.
Nothing here touches the database; `app/jobs/notify.py` is the only caller
and owns turning ORM rows into the plain values these functions take.

Topic-alert and breaking-alert eligibility are two separate functions with
no shared code path, by design (the ticket's explicit acceptance
criterion): a story can never earn a breaking push by being a popular/
high-engagement topic match, and a story can never earn a topic-alert push
just because it's flagged BREAKING. `daily_briefing_eligible` doesn't look
at any story at all — it's a per-user opt-in, one notification/day.

Thresholds below (`TOPIC_ALERT_MIN_IMPORTANCE`, `BREAKING_ALERT_MIN_*`) are
starting-point judgment calls with no spec-given number, same class as
T09's clustering thresholds and T16's ranking-formula constants — documented
here rather than a new ADR since they're tuning knobs, not an architecture
decision.
"""

from __future__ import annotations

from dataclasses import dataclass

TOPIC_ALERT_MIN_IMPORTANCE = 0.5
BREAKING_ALERT_MIN_CONFIDENCE = 0.7
BREAKING_ALERT_MIN_SOURCE_QUALITY = 0.5


@dataclass(frozen=True)
class NotifiableStory:
    id: str
    topics: tuple[str, ...]
    importance: float
    # ADR-027: None when no model classified the story (hand-drafted); the
    # editor's breaking-alert approval is then the only confidence signal.
    classification_confidence: float | None
    sensitivity: str
    breaking_alert_approved: bool
    avg_source_quality: float


@dataclass(frozen=True)
class UserNotificationPrefs:
    subscribed_topics: tuple[str, ...]
    breaking_alerts_enabled: bool
    daily_briefing_enabled: bool
    quiet_hours_start: int | None
    quiet_hours_end: int | None
    max_alerts_per_day: int


def topic_alert_eligible(story: NotifiableStory, prefs: UserNotificationPrefs) -> bool:
    """A story is eligible only if it matches at least one topic/geography
    the user actually selected (geography reuses the topic taxonomy, same
    as T16's ranking "home" reading) and clears the quality threshold.
    Never a function of engagement/popularity — those signals aren't even
    passed in."""

    if story.importance < TOPIC_ALERT_MIN_IMPORTANCE:
        return False
    if not prefs.subscribed_topics:
        return False
    return not set(story.topics).isdisjoint(prefs.subscribed_topics)


def breaking_alert_eligible(story: NotifiableStory, prefs: UserNotificationPrefs) -> bool:
    """Separate path per the ticket: no topic-subscription check at all.
    `story.breaking_alert_approved` is the "never auto-sent" gate — an
    editor must have explicitly approved *this* alert (distinct from the
    publish approval NON_NEGOTIABLES #5 already required to reach
    PUBLISHED); sensitivities other than 'BREAKING' (IMMIGRATION/LEGAL/
    FINANCIAL/OBITUARY_ACCUSATION) can never reach this branch at all."""

    if story.sensitivity != "BREAKING":
        return False
    if not story.breaking_alert_approved:
        return False
    if not prefs.breaking_alerts_enabled:
        return False
    if story.classification_confidence is not None and story.classification_confidence < BREAKING_ALERT_MIN_CONFIDENCE:
        return False
    return story.avg_source_quality >= BREAKING_ALERT_MIN_SOURCE_QUALITY


def daily_briefing_eligible(prefs: UserNotificationPrefs) -> bool:
    return prefs.daily_briefing_enabled


def in_quiet_hours(hour: int, start: int | None, end: int | None) -> bool:
    """UTC hour-of-day (0-23); no per-user timezone column exists in §12,
    so UTC is the deterministic reading until one is added. Handles a
    window that wraps midnight (e.g. 22 -> 7)."""

    if start is None or end is None:
        return False
    if start == end:
        return True  # a 24h window
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def daily_cap_reached(sent_today: int, max_alerts_per_day: int) -> bool:
    return sent_today >= max_alerts_per_day
