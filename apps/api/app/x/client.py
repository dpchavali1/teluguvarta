"""Thin wrapper around the official X API v2 user-posts timeline endpoint
(`GET /2/users/{id}/tweets`, current docs at docs.x.com/x-api/posts/
timelines) — X2's only network access point. Never scrapes x.com
(NON_NEGOTIABLES #14): if the API is unreachable or unauthorized, this
raises like any other adapter failure and the caller's job-queue retry/
backoff takes over instead of falling back to an unofficial data path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

BASE_URL = "https://api.x.com/2"
# Bounded pagination: a burst of activity from one account must not turn
# into an unbounded fetch loop within a single job run (NON_NEGOTIABLES #10
# — every job is bounded). 10 pages at 100 posts/page is far beyond what any
# incremental since_id-bounded window should ever return in practice.
MAX_PAGES = 10
PAGE_SIZE = 100


class XRateLimitedError(RuntimeError):
    """Raised on an HTTP 429 so the job queue's generic exponential backoff
    (`app.jobs.queue.fail_job`) handles retry timing — this client never
    retries a rate-limited request itself."""


@dataclass
class XFetchResult:
    tweets: list[dict] = field(default_factory=list)
    posts_read: int = 0


class XApiClient:
    def __init__(self, bearer_token: str):
        self.bearer_token = bearer_token

    def fetch_user_tweets(self, client: httpx.Client, user_id: str, since_id: str | None) -> XFetchResult:
        """Fetches only posts newer than `since_id` (never a full timeline
        re-fetch, §19), excluding retweets/replies, paginating forward
        until `next_token` runs out or `MAX_PAGES` is hit."""
        tweets: list[dict] = []
        pagination_token: str | None = None

        for _ in range(MAX_PAGES):
            params: dict[str, str | int] = {
                "max_results": PAGE_SIZE,
                "exclude": "retweets,replies",
                "tweet.fields": "created_at",
            }
            if since_id:
                params["since_id"] = since_id
            if pagination_token:
                params["pagination_token"] = pagination_token

            response = client.get(
                f"{BASE_URL}/users/{user_id}/tweets",
                params=params,
                headers={"Authorization": f"Bearer {self.bearer_token}"},
            )
            if response.status_code == 429:
                raise XRateLimitedError(f"rate limited fetching tweets for X user {user_id}")
            response.raise_for_status()

            body = response.json()
            page_tweets = body.get("data", [])
            tweets.extend(page_tweets)

            next_token = body.get("meta", {}).get("next_token")
            if not next_token or not page_tweets:
                break
            pagination_token = next_token

        return XFetchResult(tweets=tweets, posts_read=len(tweets))
