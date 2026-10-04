# ADR-048: Server-side mutes (topics and sources) — decision needed

- **Status**: proposed (needs owner decision; nothing built)
- **Date**: 2026-10-04
- **Ticket**: P05

## Context

ADR-040 keeps personalization signals on-device with "no server-side behavior
log" and defers preference sync to ADR-006. Mutes (hidden topics, and since
2026-10-04 muted source domains) are therefore applied client-side to the page
the server returned. Consequences of that: a page can come back mostly muted
(short or empty Home until the client fetches more), the web site has no mutes
at all, and push alerts ignore mutes. ADR-042 already syncs saved IDs and
keywords (bounded) for alerts, so syncing mutes would be a small extension, but
it is still a new class of stored reader data.

## Decision needed

1. **Do nothing** (recommended until feeds feel thin): mutes stay on-device,
   mobile only.
2. **Send mutes with the feed request** (not stored): `/home?mute_topics=&mute_sources=`
   so the server can fill the page after exclusion. No new storage; protected
   sensitivities (breaking/immigration/legal/financial) are still never excluded
   server-side. Bounded (e.g. 20 topics, 20 domains).
3. **Sync mutes like ADR-042** (stored per device/user): also lets push alerts
   skip muted topics/sources and lets web share the list. Needs privacy copy,
   deletion/"clear data" coverage, and an ADR-006 position on identity.

## Consequences

Option 2 fixes thin pages with no retention; option 3 is needed only if alerts
or web must honor mutes. Either way the protected-news floor in ADR-040 stays.
