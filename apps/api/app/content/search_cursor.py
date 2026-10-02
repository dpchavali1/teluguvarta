"""Query-bound keyset cursors for the existing newest-first public search."""

import base64
import hashlib
import json
from datetime import datetime
from uuid import UUID

from app.errors import APIError


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def encode_search_cursor(query: str, published_at: datetime | None, story_id: UUID) -> str:
    payload = {"v": 1, "q": _query_hash(query), "at": published_at.isoformat() if published_at else None,
               "id": str(story_id)}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decode_search_cursor(cursor: str | None, query: str) -> tuple[datetime | None, UUID] | None:
    if cursor is None:
        return None
    try:
        if not cursor or len(cursor) > 512:
            raise ValueError
        payload = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if (not isinstance(payload, dict) or set(payload) != {"v", "q", "at", "id"}
                or type(payload["v"]) is not int or payload["v"] != 1
                or payload["q"] != _query_hash(query) or not isinstance(payload["id"], str)):
            raise ValueError
        story_id = UUID(payload["id"])
        at = payload["at"]
        if at is not None and not isinstance(at, str):
            raise ValueError
        published_at = datetime.fromisoformat(at) if at is not None else None
        if published_at is not None and published_at.utcoffset() is None:
            raise ValueError
        return published_at, story_id
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise APIError(422, "INVALID_SEARCH_CURSOR", "Search page is invalid for this query; start from the first results") from exc
