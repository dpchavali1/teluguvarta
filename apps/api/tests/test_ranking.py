"""T16 acceptance tests for the pure §8.2 ranking formula
(`app/content/ranking.py`) — no DB, no AI gateway, matching `test_qa.py`/
`test_glossary.py`'s style of testing pure content-layer functions directly.
"""

from datetime import UTC, datetime, timedelta

from app.content.ranking import Preferences, RankableStory, rank_stories


def _story(id_, *, countries=(), topics=(), importance=0.5, hours_old=0.0, source_quality=0.5):
    now = datetime(2026, 9, 8, tzinfo=UTC)
    return RankableStory(
        id=id_, countries=countries, topics=topics, importance=importance,
        published_at=now - timedelta(hours=hours_old), source_quality=source_quality,
    )


def _now():
    return datetime(2026, 9, 8, tzinfo=UTC)


def test_ranking_is_deterministic_and_reproducible():
    stories = [
        _story("a", countries=("US",), topics=("immigration",), hours_old=1),
        _story("b", countries=("IN",), topics=("money",), hours_old=10),
        _story("c", countries=("US",), topics=("jobs",), hours_old=5),
    ]
    prefs = Preferences(residence_country="US", topics=("immigration", "jobs"))

    first = rank_stories(stories, prefs, now=_now())
    second = rank_stories(stories, prefs, now=_now())

    assert [s.story_id for s in first] == [s.story_id for s in second]
    assert [s.score for s in first] == [s.score for s in second]


def test_residence_match_outranks_unrelated_story():
    stories = [
        _story("match", countries=("US",), hours_old=1),
        _story("nomatch", countries=("IN",), hours_old=1),
    ]
    prefs = Preferences(residence_country="US")

    ranked = rank_stories(stories, prefs, now=_now())

    assert [s.story_id for s in ranked] == ["match", "nomatch"]
    assert ranked[0].explanation == "Because you live in US."


def test_topic_match_explanation_names_the_matched_topic():
    stories = [_story("s1", topics=("immigration",), hours_old=1)]
    prefs = Preferences(topics=("immigration", "jobs"))

    ranked = rank_stories(stories, prefs, now=_now())

    assert ranked[0].explanation == "Because you follow Immigration."


def test_no_preferences_yields_no_explanation():
    stories = [_story("s1", countries=("US",), topics=("immigration",), hours_old=1)]
    prefs = Preferences()

    ranked = rank_stories(stories, prefs, now=_now())

    assert ranked[0].explanation is None


def test_multiple_matched_signals_combine_into_one_explanation():
    stories = [_story("s1", countries=("US",), topics=("telangana",), hours_old=1)]
    prefs = Preferences(residence_country="US", home_state="Telangana", topics=("telangana",))

    ranked = rank_stories(stories, prefs, now=_now())

    assert ranked[0].explanation == (
        "Because you live in US, you're connected to Telangana and you follow Telangana."
    )


def test_repetition_penalty_demotes_third_story_sharing_a_topic():
    # Three same-topic stories all tie on every other signal (freshness held
    # constant); without a penalty they'd stay in id order. The repetition
    # penalty should push at least one of the later ones down relative to a
    # differently-topicked story that would otherwise score lower.
    stories = [
        _story("t1", topics=("jobs",), importance=0.9, hours_old=1),
        _story("t2", topics=("jobs",), importance=0.9, hours_old=1),
        _story("t3", topics=("jobs",), importance=0.9, hours_old=1),
        _story("other", topics=("money",), importance=0.75, hours_old=1),
    ]
    prefs = Preferences(topics=("jobs", "money"))

    ranked = rank_stories(stories, prefs, now=_now())
    order = [s.story_id for s in ranked]

    # "other" (lower raw score) should still surface before the repetition
    # penalty has fully suppressed the third same-topic "jobs" story.
    assert order.index("other") < order.index("t3")


def test_freshness_decays_with_age():
    stories = [
        _story("fresh", hours_old=0),
        _story("stale", hours_old=200),
    ]
    prefs = Preferences(topics=("anything",))  # no topic match, isolates freshness+importance

    ranked = rank_stories(stories, prefs, now=_now())

    assert [s.story_id for s in ranked] == ["fresh", "stale"]
