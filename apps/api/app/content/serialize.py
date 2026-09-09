"""T14: turns real `Story` rows into the public `StoryOut` contract (final
shape since T04; only the data source changes here). Shared by every public
router so the fallback/QA rules ([[resolve_display_variant]]) and the
country/topic derivation are implemented once.

Countries are not a first-class column on `Story` (§12 has no
`story_countries` table) — deriving them from `Source.country` of every
linked source is the deterministic, no-new-migration reading of "countries
this story is about" per NON_NEGOTIABLES' "prefer deterministic code" and
"don't invent requirements" (a real country/region taxonomy is future
scope, not blocking T14's acceptance criteria).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

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


def _variant_out(v: StoryVariant) -> StoryVariantOut:
    return StoryVariantOut(
        language=v.language, headline=v.headline, summary=v.summary,
        why_matters=v.why_matters, qa_status=v.qa_status,
    )


def story_to_out(db: Session, story: Story) -> StoryOut:
    variants = db.scalars(select(StoryVariant).where(StoryVariant.story_id == story.id)).all()
    variants_by_lang = {v.language: v for v in variants}

    # Only expose variants a client may actually display: `en` always (when
    # present), `te` only once it clears QA — a client never sees a broken
    # translation to fall back from itself, matching resolve_display_variant.
    out_variants: dict[Language, StoryVariantOut] = {}
    for lang in ("en", "te"):
        resolved = resolve_display_variant(variants_by_lang, lang)  # type: ignore[arg-type]
        if resolved is not None and not resolved.fallback:
            out_variants[lang] = _variant_out(resolved.variant)  # type: ignore[arg-type]

    links = db.scalars(
        select(StorySource).where(StorySource.story_id == story.id).order_by(StorySource.evidence_rank)
    ).all()
    sources_out: list[StorySourceOut] = []
    countries: list[str] = []
    for link in links:
        item = db.get(SourceItem, link.source_item_id)
        if item is None:
            continue
        sources_out.append(StorySourceOut(url=item.url, title=item.title, published_at=item.published_at))
        source = db.get(Source, item.source_id)
        if source and source.country and source.country not in countries:
            countries.append(source.country)

    topic_rows = db.execute(
        select(Topic.slug).join(StoryTopic, StoryTopic.topic_id == Topic.id).where(StoryTopic.story_id == story.id)
    ).all()
    topics = [row[0] for row in topic_rows]

    # Every publicly-listed status (see PUBLIC_STATUSES) is post-first-publish,
    # so `published_at` is always set by the time a story reaches here.
    updated_at = max((v.generated_at for v in variants), default=story.published_at)

    return StoryOut(
        id=story.id,
        canonical_slug=story.canonical_slug,
        status=story.status,
        sensitivity=story.sensitivity,
        importance=story.importance,
        published_at=story.published_at,
        updated_at=updated_at,  # type: ignore[arg-type]
        topics=topics,
        countries=countries,
        variants=out_variants,
        sources=sources_out,
    )


def topic_out(topic: Topic) -> TopicOut:
    return TopicOut(slug=topic.slug, name=topic.name, active=topic.active)


def story_to_rankable(db: Session, story: Story) -> RankableStory:
    """T16: the same topics/countries derivation as `story_to_out`, plus the
    §8.2 `source_quality` input (average `quality_score` of every linked
    source) — kept separate from `StoryOut` since ranking inputs aren't part
    of the public response shape."""

    topic_rows = db.execute(
        select(Topic.slug).join(StoryTopic, StoryTopic.topic_id == Topic.id).where(StoryTopic.story_id == story.id)
    ).all()
    topics = tuple(row[0] for row in topic_rows)

    links = db.scalars(select(StorySource).where(StorySource.story_id == story.id)).all()
    countries: list[str] = []
    quality_scores: list[float] = []
    for link in links:
        item = db.get(SourceItem, link.source_item_id)
        if item is None:
            continue
        source = db.get(Source, item.source_id)
        if source is None:
            continue
        if source.country and source.country not in countries:
            countries.append(source.country)
        quality_scores.append(source.quality_score)

    source_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5

    return RankableStory(
        id=str(story.id),
        countries=tuple(countries),
        topics=topics,
        importance=story.importance,
        published_at=story.published_at,
        source_quality=source_quality,
    )
