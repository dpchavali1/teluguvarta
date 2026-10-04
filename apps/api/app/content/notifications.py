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

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.content.places import expand_with_ancestors

TOPIC_ALERT_MIN_IMPORTANCE = 0.5
BREAKING_ALERT_MIN_CONFIDENCE = 0.7
BREAKING_ALERT_MIN_SOURCE_QUALITY = 0.5
# P02: a digest covers stories published in this many hours before its slot.
DIGEST_WINDOW_HOURS = 12
# P02: a digest still goes out if the worker was down for up to this many
# local hours after the chosen hour, then the slot is skipped.
DIGEST_GRACE_HOURS = 2


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
    headline: str = ""
    # ADR-043: event place tags (ancestors are expanded at match time).
    places: tuple[str, ...] = ()


@dataclass(frozen=True)
class UserNotificationPrefs:
    subscribed_topics: tuple[str, ...]
    breaking_alerts_enabled: bool
    daily_briefing_enabled: bool
    quiet_hours_start: int | None
    quiet_hours_end: int | None
    max_alerts_per_day: int
    # P02 / ADR-042. Topics absent from `topic_urgency` are INSTANT.
    topic_urgency: Mapping[str, str] = field(default_factory=dict)
    keywords: tuple[str, ...] = ()
    # ADR-043: followed places whose per-place alert switch is on.
    alert_places: tuple[str, ...] = ()
    home_tz: str | None = None
    residence_tz: str | None = None
    digest_morning_hour: int | None = None
    digest_evening_hour: int | None = None


def _topics_with(prefs: UserNotificationPrefs, urgency: str) -> set[str]:
    return {t for t in prefs.subscribed_topics if prefs.topic_urgency.get(t, "INSTANT") == urgency}


def topic_alert_eligible(story: NotifiableStory, prefs: UserNotificationPrefs) -> bool:
    """A story is eligible only if it matches at least one topic/geography
    the user actually selected (geography reuses the topic taxonomy, same
    as T16's ranking "home" reading) and clears the quality threshold.
    Never a function of engagement/popularity — those signals aren't even
    passed in."""

    if story.importance < TOPIC_ALERT_MIN_IMPORTANCE:
        return False
    # DIGEST and BREAKING_ONLY topics never produce an instant topic alert.
    instant = _topics_with(prefs, "INSTANT")
    if not instant:
        return False
    return not set(story.topics).isdisjoint(instant)


def _reviewed_for_alerts(story: NotifiableStory) -> bool:
    """Digest and keyword paths never carry a BREAKING story that an editor
    has not approved for alerting (human review stays the gate)."""

    return story.sensitivity != "BREAKING" or story.breaking_alert_approved


def keyword_alert_eligible(story: NotifiableStory, prefs: UserNotificationPrefs) -> bool:
    """The reader explicitly followed a keyword that appears in the headline.
    Same importance floor as topic alerts; sensitive categories alert only on
    the approved breaking path, never here."""

    if story.importance < TOPIC_ALERT_MIN_IMPORTANCE or not prefs.keywords:
        return False
    if story.sensitivity not in ("NONE",):
        return False
    headline = story.headline.lower()
    return any(keyword in headline for keyword in prefs.keywords)


def place_alert_eligible(story: NotifiableStory, prefs: UserNotificationPrefs) -> bool:
    """The reader follows a place with its alert switch on and the story is
    tagged at or beneath it. Same floors as keyword alerts; an untagged story
    never matches, and sensitive categories use only the approved breaking path."""

    if story.importance < TOPIC_ALERT_MIN_IMPORTANCE or not prefs.alert_places or not story.places:
        return False
    if story.sensitivity not in ("NONE",):
        return False
    return not set(prefs.alert_places).isdisjoint(expand_with_ancestors(story.places))


def digest_story_eligible(story: NotifiableStory, prefs: UserNotificationPrefs) -> bool:
    if story.importance < TOPIC_ALERT_MIN_IMPORTANCE or not _reviewed_for_alerts(story):
        return False
    return not set(story.topics).isdisjoint(_topics_with(prefs, "DIGEST"))


def _zone(name: str | None) -> ZoneInfo | None:
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def digest_slots_due(now: datetime, prefs: UserNotificationPrefs) -> list[tuple[str, str]]:
    """(`am`|`pm`, local ISO date) for each digest whose chosen local hour has
    arrived (within the grace window). The reader's zone is where they live
    now (`residence_tz`), then home, then UTC."""

    zone = _zone(prefs.residence_tz) or _zone(prefs.home_tz) or ZoneInfo("UTC")
    local = now.astimezone(zone)
    due: list[tuple[str, str]] = []
    for slot, hour in (("am", prefs.digest_morning_hour), ("pm", prefs.digest_evening_hour)):
        if hour is not None and 0 <= local.hour - hour < DIGEST_GRACE_HOURS:
            due.append((slot, local.date().isoformat()))
    return due


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


def in_quiet_hours_any_zone(now: datetime, prefs: UserNotificationPrefs) -> bool:
    """Quiet when the window covers the local time in *either* the home or the
    residence zone (a family call at 2am India time is as unwelcome as one at
    2am Texas time). With no zone set this is the original UTC reading."""

    zones = [z for z in (_zone(prefs.home_tz), _zone(prefs.residence_tz)) if z is not None] or [ZoneInfo("UTC")]
    return any(
        in_quiet_hours(now.astimezone(z).hour, prefs.quiet_hours_start, prefs.quiet_hours_end) for z in zones
    )


def daily_cap_reached(sent_today: int, max_alerts_per_day: int) -> bool:
    return sent_today >= max_alerts_per_day
