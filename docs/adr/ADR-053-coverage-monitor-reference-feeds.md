# ADR-053: Coverage monitor using monitor-only reference headline feeds

- **Status**: proposed (owner request, 2026-10-04)
- **Date**: 2026-10-04
- **Ticket**: —
- **Relates to**: ADR-002 (source rights), ADR-052 (alerts via audit events)

## Context

Important Telugu/diaspora news can reach readers late or never because no approved source
carried it. We need a signal that a story exists elsewhere that we do not hold.

## Decision

1. Every `COVERAGE_MONITOR_INTERVAL_MINUTES` (off unless set; worker loop, `app/coverage_monitor.py`)
   fetch a small reference set: by default Google News RSS for Telugu (`hl=te&gl=IN&ceid=IN:te`)
   and a topic query (Andhra Pradesh / Telangana / Tollywood / Telugu). Override with
   `COVERAGE_MONITOR_FEEDS` (`name|url` per line).
2. **Monitor-only boundary.** Reference headlines are never ingested, never become a `Source`,
   `SourceItem` or `Story`, are never republished, drafted from, or shown to readers or in the
   reader API. Only title, url, reference source name, published time and a hash are kept, as
   `audit_events` rows (`COVERAGE_MONITOR_SEEN`), pruned after 7 days. The admin-only
   `GET /v1/admin/coverage/misses` lists the last 50 misses and the 24h matched/unmatched rate.
3. Matching is deterministic (no AI): headlines newer than 3h are compared with story variants
   (en/te headline + summary) and source-item titles from the last 48h, any status, by token
   overlap (>=2 shared words covering >=50% of the reference headline; Telugu words match on a
   shared 4-character stem) or difflib ratio >= 0.72 (as in `jobs/cluster.py`).
4. A miss sends one alert through the existing channel (log + `ALERT_WEBHOOK_URL`), deduped by
   headline hash, max 5 per run and 20 per day (`COVERAGE_MONITOR_MAX_ALERTS_PER_RUN/_PER_DAY`),
   3 attempts per headline on delivery failure. No migration, no new infrastructure.
5. Fetching reuses `adapters/safe_fetch.fetch_public` (public hosts only, no redirects, 10s
   timeout, 2 MB cap via `feed_probe.MAX_BYTES`) and the defusedxml RSS parser. A failing feed is
   skipped, never raised.

## Why Google News is monitor-only

Google News aggregates publishers' headlines under terms that do not grant redistribution, and
its feeds are not a licensed source (ADR-002 allows only `LINK_ONLY` sources with reviewed
rights). Treating it as an internal tripwire, like a human skimming it, keeps us inside the
rights gate: the output is an alert to an editor, who then finds an approved source.

## Consequences

- False negatives: transliteration and cross-language headlines (Telugu reference vs English-only
  story) can fail to match, causing extra alerts; generic overlap can wrongly match (a missed miss).
- Google may rate-limit or change the feed; the monitor degrades to nothing. Polling is 2 requests
  per interval. Owner should confirm the ToS reading before enabling in production.
- Enable in prod with `COVERAGE_MONITOR_INTERVAL_MINUTES=15` and `ALERT_WEBHOOK_URL`.
