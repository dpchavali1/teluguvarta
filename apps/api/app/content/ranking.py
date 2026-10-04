"""§8.2 ranking formula (T16/ADR-005) — pure, deterministic, no AI/model
call: `score = 0.28*residence + 0.20*home + 0.18*topic + 0.16*freshness +
0.14*importance + 0.04*source_quality - repetition_penalty`.

`residence`/`home` both key off `RankableStory.countries`/`topics` — a
`Story` has no dedicated home-region column or table (§12), so "home"
reuses the same topic taxonomy §3.1 already lists AP/Telangana/Hyderabad
under: a story tagged with a topic matching the caller's `home_state`/
`home_city` counts as a home match. This is a judgment call (ADR-005 covers
the ones with no deterministic reading at all; this one follows directly
from the existing topic list, so it's documented here rather than in the
ADR itself).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.content.places import expand_with_ancestors, get_place

FRESHNESS_HALF_LIFE_HOURS = 24.0
PLACE_WEIGHT = 0.15  # bounded additive term; the base weights are unchanged
PLACE_EXACT_SCORE = 1.0
PLACE_ANCESTOR_SCORE = 0.6
REPETITION_PENALTY_STEP = 0.05
REPETITION_PENALTY_CAP = 0.2
REPETITION_PENALTY_TOPIC_CAP = 4


@dataclass(frozen=True)
class Preferences:
    residence_country: str | None = None
    residence_region: str | None = None
    home_state: str | None = None
    home_city: str | None = None
    topics: tuple[str, ...] = ()
    # ADR-043: followed catalog place ids (explicit signal, at most 10).
    follow_places: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not any(
            (self.residence_country, self.residence_region, self.home_state, self.home_city,
             self.topics, self.follow_places)
        )


@dataclass(frozen=True)
class RankableStory:
    id: str
    countries: tuple[str, ...]
    topics: tuple[str, ...]
    importance: float
    published_at: datetime | None
    source_quality: float
    places: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScoredStory:
    story_id: str
    score: float
    explanation: str | None
    signals: tuple[str, ...]


def _slugify(value: str) -> str:
    return value.strip().lower().replace(" ", "-")


def _topic_label(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def _residence_signal(story: RankableStory, prefs: Preferences) -> tuple[float, str | None]:
    if prefs.residence_country and prefs.residence_country in story.countries:
        return 1.0, f"you live in {prefs.residence_country}"
    return 0.0, None


def _home_signal(story: RankableStory, prefs: Preferences) -> tuple[float, str | None]:
    for value in (prefs.home_state, prefs.home_city, prefs.residence_region):
        if value and _slugify(value) in story.topics:
            return 1.0, f"you're connected to {value}"
    return 0.0, None


def _topic_signal(story: RankableStory, prefs: Preferences) -> tuple[float, str | None]:
    if not prefs.topics:
        return 0.0, None
    matched = [t for t in prefs.topics if t in story.topics]
    if not matched:
        return 0.0, None
    score = min(1.0, len(matched) / len(prefs.topics))
    labels = ", ".join(_topic_label(t) for t in matched)
    return score, f"you follow {labels}"


def _place_signal(story: RankableStory, prefs: Preferences) -> tuple[float, str | None]:
    """ADR-043: a story tagged Warangal matches a follow of Warangal exactly
    and a follow of Telangana/India through its ancestors. A story with no
    place tag never matches. The reason names the most specific followed place."""
    if not prefs.follow_places or not story.places:
        return 0.0, None
    exact = [p for p in prefs.follow_places if p in story.places]
    implied = [p for p in prefs.follow_places if p not in exact and p in expand_with_ancestors(story.places)]
    if exact:
        matched, score = exact, PLACE_EXACT_SCORE
    elif implied:
        matched, score = implied, PLACE_ANCESTOR_SCORE
    else:
        return 0.0, None
    names = ", ".join(place.name_en if (place := get_place(p)) else p for p in matched[:2])
    return score, f"you follow {names}"


def _freshness_signal(story: RankableStory, now: datetime) -> float:
    if story.published_at is None:
        return 0.0
    published_at = story.published_at
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
    return 0.5 ** (hours / FRESHNESS_HALF_LIFE_HOURS)


def _raw_score_and_signals(
    story: RankableStory, prefs: Preferences, now: datetime
) -> tuple[float, tuple[str, ...]]:
    residence_score, residence_signal = _residence_signal(story, prefs)
    home_score, home_signal = _home_signal(story, prefs)
    topic_score, topic_signal = _topic_signal(story, prefs)
    place_score, place_signal = _place_signal(story, prefs)
    freshness_score = _freshness_signal(story, now)
    importance_score = max(0.0, min(1.0, story.importance))
    source_quality_score = max(0.0, min(1.0, story.source_quality))

    raw = (
        0.28 * residence_score
        + 0.20 * home_score
        + 0.18 * topic_score
        + PLACE_WEIGHT * place_score
        + 0.16 * freshness_score
        + 0.14 * importance_score
        + 0.04 * source_quality_score
    )
    signals = tuple(s for s in (residence_signal, home_signal, place_signal, topic_signal) if s)
    return raw, signals


def _repetition_penalty(topics: tuple[str, ...], topic_counts: dict[str, int]) -> float:
    contribution = max((topic_counts.get(t, 0) for t in topics), default=0)
    return min(REPETITION_PENALTY_CAP, REPETITION_PENALTY_STEP * min(REPETITION_PENALTY_TOPIC_CAP, contribution))


def _build_explanation(signals: tuple[str, ...]) -> str | None:
    if not signals:
        return None
    if len(signals) == 1:
        return f"Because {signals[0]}."
    return f"Because {', '.join(signals[:-1])} and {signals[-1]}."


def rank_stories(
    stories: list[RankableStory], prefs: Preferences, *, now: datetime | None = None
) -> list[ScoredStory]:
    """Deterministic §8.2 ranking. Same `stories`/`prefs`/`now` always
    produces the same order — no randomness, no model call. Repetition
    penalty is applied greedily: at each step the highest-(raw score minus
    penalty-so-far) remaining story is picked next, then topic counts used
    for the penalty are updated — a stable, single well-defined tiebreak
    (story id) keeps ties reproducible."""

    now = now or datetime.now(UTC)
    scored = [(story, *_raw_score_and_signals(story, prefs, now)) for story in stories]
    remaining = sorted(scored, key=lambda t: (-t[1], t[0].id))

    topic_counts: dict[str, int] = {}
    ranked: list[ScoredStory] = []
    while remaining:
        best_pos = 0
        best_key = None
        best_final_score = 0.0
        for pos, (story, raw, _signals) in enumerate(remaining):
            penalty = _repetition_penalty(story.topics, topic_counts)
            final_score = raw - penalty
            key = (-final_score, story.id)
            if best_key is None or key < best_key:
                best_key = key
                best_pos = pos
                best_final_score = final_score

        story, _raw, signals = remaining.pop(best_pos)
        for topic in story.topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        ranked.append(
            ScoredStory(
                story_id=story.id,
                score=round(best_final_score, 6),
                explanation=_build_explanation(signals),
                signals=signals,
            )
        )
    return ranked
