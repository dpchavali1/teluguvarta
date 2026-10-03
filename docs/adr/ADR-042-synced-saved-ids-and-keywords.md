# ADR-042: Sync saved story IDs and followed keywords for alerts

- **Status**: accepted (owner, 2026-10-03)
- **Date**: 2026-10-03
- **Ticket**: P02

## Context

ADR-006 keeps reader preferences and saved stories on the device. Push is sent
by the server, so "this saved story was corrected" and "a story matched your
keyword" cannot be decided without the server knowing the story IDs and
keywords involved.

## Decision

Amend ADR-006 for **only** these two lists, plus IANA timezone names and
digest hours. The client sends them with `PATCH /v1/me/preferences`:

- saved story IDs: at most 200, opaque UUIDs, no timestamps or notes;
- followed keywords: at most 20, 1-40 characters, lowercased and de-duplicated;
- `home_tz` / `residence_tz`: IANA names; `digest_morning_hour` /
  `digest_evening_hour`: whole hours 0-23 or null (off).

Nothing is inferred and no reading behaviour is logged. Rows are keyed to the
anonymous user and cascade-delete with the account. Alerts still go through
the existing deduped, capped, bounded-retry push path; immigration, legal,
financial and breaking stories still alert only after human approval.

## Consequences

Enables update alerts, keyword follows and local-time digests. The server now
holds a small amount of reader choice data, which the privacy copy must
mention. Everything else in ADR-006 is unchanged.

## Alternatives considered

On-device evaluation only (no push possible) and deferring the feature; both
rejected by the owner.
