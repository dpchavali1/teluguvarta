"""Source-rights check at approval and publication (review 2026-09-29 #7).

Ingest already refuses items from a source that isn't `LINK_ONLY`, but a
source can be disabled after its item was emitted and before the story
publishes. Every approve/publish transition re-reads the current rights of
every source behind the story; one that is no longer permitted blocks the
transition (NON_NEGOTIABLES #4, #15).

Only `rights_status` counts: an inactive (not polled) source keeps its
rights. What revocation means for an already-published story, or for a
mixed-source story whose other sources are still permitted, is not decided
here — see ADR-023 (proposed).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Source, SourceItem, StorySource

# ADR-002: the only rights status a source may hold and still be published
# from in this build phase.
PUBLISHABLE_RIGHTS = frozenset({"LINK_ONLY"})

RIGHTS_REVOKED_REASON = "SOURCE_RIGHTS_REVOKED"


def unpermitted_sources(db: Session, story_id: uuid.UUID) -> list[Source]:
    """Sources behind `story_id` whose current rights no longer permit
    publication. Empty means the story may move on."""
    sources = db.scalars(
        select(Source)
        .join(SourceItem, SourceItem.source_id == Source.id)
        .join(StorySource, StorySource.source_item_id == SourceItem.id)
        .where(StorySource.story_id == story_id)
        .distinct()
    ).all()
    return [source for source in sources if source.rights_status not in PUBLISHABLE_RIGHTS]
