"""Shared adapter contract types and the normalize/validate/emit steps that
are identical across every LINK_ONLY feed source — only `fetch()`'s wire
format parsing differs per source/adapter subclass (§6.3).
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Source, SourceItem

# ADR-020: stored description text is capped; the full text stays at the link.
DESCRIPTION_MAX_CHARS = 4000
_TAG_RE = re.compile(r"<[^>]*>")


@dataclass
class RawItem:
    external_id: str
    url: str
    title: str | None
    published_at: datetime | None
    raw_bytes: bytes
    description: str | None = None


@dataclass
class RawItems:
    items: list[RawItem] = field(default_factory=list)


@dataclass
class NormalizedItem:
    external_id: str
    url: str
    title: str | None
    published_at: datetime | None
    raw_hash: str
    description: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


class SourceAdapter:
    """Base adapter. Subclasses implement `fetch()` for one wire format;
    `normalize`/`validate`/`emit` are shared here since every LINK_ONLY
    source needs the same identity/shape checks and the same idempotent
    write to `source_items`.
    """

    def __init__(self, source: Source):
        self.source = source

    def fetch(self, client: httpx.Client) -> RawItems:
        raise NotImplementedError

    def normalize(self, raw_item: RawItem) -> NormalizedItem:
        title = (raw_item.title or "").strip() or None
        return NormalizedItem(
            external_id=raw_item.external_id.strip(),
            url=raw_item.url.strip(),
            title=title,
            published_at=raw_item.published_at,
            # Hash of the *normalized title text*, not the raw fetch bytes:
            # two sources reporting the same underlying event never share
            # raw bytes (different feed XML/formatting), but T09's dedup
            # fingerprint needs a hash that can match across sources when
            # they happen to report an identical headline. Near-duplicates
            # with differently worded headlines are still caught by T09's
            # lexical-similarity pass, not this exact hash.
            raw_hash=hashlib.sha256((title or "").strip().lower().encode("utf-8")).hexdigest(),
            description=clean_description(raw_item.description),
        )

    def validate(self, item: NormalizedItem) -> ValidationResult:
        errors: list[str] = []
        if not item.external_id:
            errors.append("missing external_id")
        if not item.url or not item.url.startswith(("http://", "https://")):
            errors.append("missing or invalid url")
        if not item.title:
            errors.append("missing title")
        elif item.title.isdigit():
            # FEMA's RSS feed sent bare disaster numbers ("1", "100") as titles.
            errors.append("title is only digits")
        return ValidationResult(valid=not errors, errors=errors)

    def emit(self, db: Session, item: NormalizedItem, *, archive: bool = False) -> SourceItem:
        """Idempotent on (source_id, external_id) so re-running fetch on an
        already-seen item updates it in place instead of duplicating it,
        per §6's "never duplicate a story when the same source item
        reappears".

        The rights gate is enforced here, not by callers: only a source
        currently `LINK_ONLY` (the sole enabled tier per ADR-002) reaches
        `NORMALIZED`; anything else — including `DISABLED` — is recorded as
        `RIGHTS_BLOCKED`, per NON_NEGOTIABLES #4 ("never bypass the rights
        gate"). `ingest_status` is set only on first insert: a later
        re-fetch must not regress an item a downstream ticket has already
        advanced past NORMALIZED (dedup/cluster/...).

        `archive=True` records a permitted item as `ARCHIVED` instead of
        `NORMALIZED` — kept for dedupe but never processed (the first-fetch
        backlog cutoff in `source_fetch`). It never lifts `RIGHTS_BLOCKED`.
        """
        if self.source.rights_status != "LINK_ONLY":
            ingest_status = "RIGHTS_BLOCKED"
        else:
            ingest_status = "ARCHIVED" if archive else "NORMALIZED"
        # ADR-020: the description is kept only for a flagged LINK_ONLY source.
        store_description = self.source.description_evidence and self.source.rights_status == "LINK_ONLY"
        description = item.description if store_description else None
        stmt = (
            pg_insert(SourceItem)
            .values(
                source_id=self.source.id,
                external_id=item.external_id,
                url=item.url,
                title=item.title,
                published_at=item.published_at,
                raw_hash=item.raw_hash,
                description=description,
                ingest_status=ingest_status,
            )
            .on_conflict_do_update(
                index_elements=[SourceItem.source_id, SourceItem.external_id],
                set_={
                    "url": item.url,
                    "title": item.title,
                    "published_at": item.published_at,
                    "raw_hash": item.raw_hash,
                    "description": description,
                },
            )
            .returning(SourceItem.id)
        )
        source_item_id = db.execute(stmt).scalar_one()
        db.flush()
        source_item = db.get(SourceItem, source_item_id)
        assert source_item is not None  # just inserted/updated above
        return source_item


def clean_description(value: str | None) -> str | None:
    """ADR-020: strips tags, decodes entities, collapses whitespace, and caps
    the text at DESCRIPTION_MAX_CHARS on a word boundary. Tags are stripped
    before and after decoding so escaped markup (`&lt;p&gt;`) goes too."""
    if not value:
        return None
    text = _TAG_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value)))
    text = " ".join(text.split())
    if len(text) > DESCRIPTION_MAX_CHARS:
        cut = text[: DESCRIPTION_MAX_CHARS + 1]
        text = cut[: cut.rfind(" ")] if " " in cut else cut[:DESCRIPTION_MAX_CHARS]
    return text or None
