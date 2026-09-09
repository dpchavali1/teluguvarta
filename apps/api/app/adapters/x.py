"""X official-account adapter (X2). Same `fetch -> normalize -> validate ->
emit` contract as every other `SourceAdapter` (`app/adapters/base.py`) —
only `fetch()`'s wire format (the X API v2 tweet JSON shape, via
`app/x/client.py`) differs.
"""

from __future__ import annotations

import json
from datetime import datetime

import httpx

from app.models import XAccount
from app.x.client import XApiClient

from .base import RawItem, RawItems, SourceAdapter


class XAdapter(SourceAdapter):
    def __init__(self, source, x_account: XAccount, bearer_token: str, x_client: XApiClient | None = None):
        super().__init__(source)
        self.x_account = x_account
        self._x_client = x_client or XApiClient(bearer_token)
        # Populated by fetch(): how many posts this run actually read (for
        # cost telemetry) and the highest post id seen, which becomes the
        # account's new `since_id` — never re-fetching a full timeline (§19).
        self.posts_read = 0
        self.newest_id: str | None = x_account.since_id

    def fetch(self, client: httpx.Client) -> RawItems:
        result = self._x_client.fetch_user_tweets(client, self.x_account.x_user_id, self.x_account.since_id)
        self.posts_read = result.posts_read
        if result.tweets:
            seen_ids = [tweet["id"] for tweet in result.tweets]
            if self.x_account.since_id:
                seen_ids.append(self.x_account.since_id)
            self.newest_id = max(seen_ids, key=int)
        return RawItems(items=[_raw_item_from_tweet(tweet, self.x_account.handle) for tweet in result.tweets])


def _raw_item_from_tweet(tweet: dict, handle: str) -> RawItem:
    tweet_id = tweet["id"]
    text = (tweet.get("text") or "").strip()
    return RawItem(
        external_id=tweet_id,
        url=f"https://x.com/{handle}/status/{tweet_id}",
        title=text or None,
        published_at=_parse_created_at(tweet.get("created_at")),
        raw_bytes=json.dumps(tweet).encode("utf-8"),
    )


def _parse_created_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
