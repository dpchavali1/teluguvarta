"""T14: turns real `Story` rows into the public `StoryOut` contract (final
shape since T04; only the data source changes here). Shared by every public
router so the fallback/QA rules ([[resolve_display_variant]]) and the
country/topic derivation are implemented once.

Countries are the story's event geography (ADR-027, `story_countries`
role EVENT), never its publishers' `Source.country`: a UK event reported by
a US outlet is a UK story. A story with no event countries has none.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.content.geography import event_countries_many
from app.content.ranking import RankableStory
from app.content.variants import resolve_display_variant
from app.models import (
    Source,
    SourceItem,
    Story,
    StorySource,
    StoryTopic,
    StoryVariant,
    Topic,
)
from app.schemas import Language, StoryOut, StorySourceOut, StoryVariantOut, TopicOut

# A story shows up to the public only once it has been published at least
# once (T12's status machine); UPDATED/RETRACTED/CORRECTION_PENDING are all
# post-publish states that must still be visibly reachable (retraction/
# correction indicator is the `status` field itself).
PUBLIC_STATUSES = ("PUBLISHED", "UPDATED", "RETRACTED", "CORRECTION_PENDING")


@dataclass
class StoryRelations:
    variants: dict = field(default_factory=lambda: defaultdict(list))
    links: dict = field(default_factory=lambda: defaultdict(list))
    topics: dict = field(default_factory=lambda: defaultdict(list))
    countries: dict = field(default_factory=lambda: defaultdict(list))
    items: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)


def load_story_relations(db: Session, ids: list[UUID]) -> StoryRelations:
    """Load a bounded page's associations in six queries, not per story."""
    loaded = StoryRelations()
    if not ids:
        return loaded
    for variant in db.scalars(select(StoryVariant).where(StoryVariant.story_id.in_(ids))):
        loaded.variants[variant.story_id].append(variant)
    for link in db.scalars(select(StorySource).where(StorySource.story_id.in_(ids)).order_by(StorySource.evidence_rank)):
        loaded.links[link.story_id].append(link)
    item_ids = [link.source_item_id for links in loaded.links.values() for link in links]
    loaded.items = {item.id: item for item in db.scalars(select(SourceItem).where(SourceItem.id.in_(item_ids)))}
    source_ids = {item.source_id for item in loaded.items.values()}
    loaded.sources = {source.id: source for source in db.scalars(select(Source).where(Source.id.in_(source_ids)))}
    for story_id, slug in db.execute(select(StoryTopic.story_id, Topic.slug).join(Topic, Topic.id == StoryTopic.topic_id).where(StoryTopic.story_id.in_(ids))):
        loaded.topics[story_id].append(slug)
    for story_id, codes in event_countries_many(db, ids).items():
        loaded.countries[story_id] = codes
    return loaded


def _variant_out(v: StoryVariant) -> StoryVariantOut:
    return StoryVariantOut(
        language=v.language, headline=v.headline, summary=v.summary,
        why_matters=v.why_matters, qa_status=v.qa_status,
    )


def story_to_out(db: Session, story: Story, loaded: StoryRelations | None = None) -> StoryOut:
    loaded = loaded or load_story_relations(db, [story.id])
    variants = loaded.variants[story.id]
    variants_by_lang = {v.language: v for v in variants}

    # Only expose variants a client may actually display: `en` always (when
    # present), `te` only once it clears QA — a client never sees a broken
    # translation to fall back from itself, matching resolve_display_variant.
    out_variants: dict[Language, StoryVariantOut] = {}
    for lang in ("en", "te"):
        resolved = resolve_display_variant(variants_by_lang, lang)  # type: ignore[arg-type]
        if resolved is not None and not resolved.fallback:
            out_variants[lang] = _variant_out(resolved.variant)  # type: ignore[arg-type]

    links = loaded.links[story.id]
    sources_out: list[StorySourceOut] = []
    for link in links:
        item = loaded.items.get(link.source_item_id)
        if item is None:
            continue
        sources_out.append(StorySourceOut(url=item.url, title=item.title, published_at=item.published_at))
    countries = list(loaded.countries[story.id])

    topics = loaded.topics[story.id]

    # Every publicly-listed status (see PUBLIC_STATUSES) is post-first-publish,
    # so `published_at` is always set by the time a story reaches here.
    updated_at = max((v.generated_at for v in variants), default=story.published_at)

    return StoryOut(
        id=story.id,
        canonical_slug=story.canonical_slug,
        status=story.status,
        sensitivity=story.sensitivity,
        format=story.format,
        importance=story.importance,
        published_at=story.published_at,
        updated_at=updated_at,  # type: ignore[arg-type]
        topics=topics,
        countries=countries,
        variants=out_variants,
        sources=sources_out,
    )


def topic_out(topic: Topic, story_count: int = 0) -> TopicOut:
    return TopicOut(slug=topic.slug, name=topic.name, active=topic.active, story_count=story_count)


def active_topics_out(db: Session) -> list[TopicOut]:
    """Every active topic with its published-story count, populated topics
    first (most stories first), then the empty ones by name, so navigation
    leads with what has content while the full taxonomy stays listed."""
    counts = dict(db.execute(
        select(StoryTopic.topic_id, func.count(func.distinct(StoryTopic.story_id)))
        .join(Story, Story.id == StoryTopic.story_id)
        .where(Story.status.in_(PUBLIC_STATUSES))
        .group_by(StoryTopic.topic_id)
    ).all())
    topics = db.scalars(select(Topic).where(Topic.active.is_(True))).all()
    ordered = sorted(topics, key=lambda t: (-counts.get(t.id, 0), t.name.casefold()))
    return [topic_out(t, counts.get(t.id, 0)) for t in ordered]


def story_to_rankable(db: Session, story: Story, loaded: StoryRelations | None = None) -> RankableStory:
    """T16: the same topics/countries derivation as `story_to_out`, plus the
    §8.2 `source_quality` input (average `quality_score` of every linked
    source) — kept separate from `StoryOut` since ranking inputs aren't part
    of the public response shape."""

    loaded = loaded or load_story_relations(db, [story.id])
    topics = tuple(loaded.topics[story.id])
    links = loaded.links[story.id]
    quality_scores: list[float] = []
    for link in links:
        item = loaded.items.get(link.source_item_id)
        if item is None:
            continue
        source = loaded.sources.get(item.source_id)
        if source is None:
            continue
        quality_scores.append(source.quality_score)

    source_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5

    return RankableStory(
        id=str(story.id),
        countries=tuple(loaded.countries[story.id]),
        topics=topics,
        importance=story.importance,
        published_at=story.published_at,
        source_quality=source_quality,
    )
