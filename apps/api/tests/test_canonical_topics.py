"""ADR-056: the fixed topic taxonomy, retired-slug mapping, and the topic
alert floor that lets any matched story alert."""

from __future__ import annotations

import pytest

from app.content.notifications import topic_alert_eligible
from app.content.topics import (
    CANONICAL_SLUGS,
    TOPIC_ALIASES,
    canonical_topic_slug,
    canonical_topic_slugs,
    classifier_topic_ids,
)
from tests.conftest import requires_postgres
from tests.test_notifications import _story
from tests.test_smart_alerts import AUTH, _prefs


def test_canonical_slugs_map_to_themselves_and_appear_in_the_classifier_prompt():
    ids = classifier_topic_ids().split(", ")
    assert set(ids) == CANONICAL_SLUGS
    assert all(canonical_topic_slug(slug) == slug for slug in CANONICAL_SLUGS)


def test_aliases_point_only_at_canonical_topics():
    assert not set(TOPIC_ALIASES) & CANONICAL_SLUGS
    assert {target for target in TOPIC_ALIASES.values() if target is not None} <= CANONICAL_SLUGS


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Tollywood", "entertainment"),
        ("Crime & Safety", "crime-safety"),
        ("Law and Order", "crime-safety"),
        ("US Visas", "immigration"),
        ("STEM OPT", "stem-opt"),
        ("Local News", None),
        ("Immigration Policy", None),
    ],
)
def test_labels_and_retired_slugs_resolve_to_canonical(value, expected):
    assert canonical_topic_slug(value) == expected


def test_canonical_topic_slugs_dedupes_in_order():
    assert canonical_topic_slugs(["Cinema", "politics", "Tollywood", "Local News", "elections"]) == [
        "entertainment", "politics",
    ]


def test_single_source_story_alerts_but_editor_low_override_does_not():
    prefs = _prefs(subscribed_topics=("politics",))
    assert topic_alert_eligible(_story(topics=("politics",), importance=0.4), prefs) is True
    assert topic_alert_eligible(_story(topics=("politics",), importance=0.2), prefs) is False


@requires_postgres
def test_preferences_map_retired_slugs_and_keep_most_immediate_urgency(client):
    response = client.patch(
        "/v1/me/preferences",
        json={
            "topic_slugs": ["tollywood", "cinema", "crime", "local-news", "money"],
            "topic_urgency": {"tollywood": "DIGEST", "cinema": "INSTANT", "crime": "BREAKING_ONLY", "money": "DIGEST"},
        },
        headers=AUTH,
    )
    assert response.status_code == 200
    assert response.json()["topic_urgency"] == {
        "entertainment": "INSTANT", "crime-safety": "BREAKING_ONLY", "money": "DIGEST",
    }

