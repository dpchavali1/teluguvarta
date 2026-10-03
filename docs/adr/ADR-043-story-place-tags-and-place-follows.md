# ADR-043: Story place tags below country level, and multi-place follows

- **Status**: proposed (needs owner decision; blocks P03)
- **Date**: 2026-10-03
- **Ticket**: P03

## Context

P03 lets a reader follow several places (AP/Telangana districts, US
states/cities, a home town) and match stories and alerts against story
geography. ADR-027 only stores **country** geography (`story_countries`,
ISO alpha-2, `EVENT` role). Nothing stores a state, district or city for a
story, and no place list exists. `PROGRESS.md` already records that regional
tagging needs its own accepted decision. Building it inside P03 would invent
the data model, the place list and the tagging source (NON_NEGOTIABLES #11).

ADR-005 already has `home_state` / `home_city` as per-request ranking inputs.
ADR-040 keeps follows on-device, explicit-signal only, with a "why am I seeing
this?" reason. ADR-042 allows bounded client-synced lists for alerts.

## Decision (proposed)

1. **Place catalog**: a fixed, versioned list in `packages/domain`, each entry
   `{id, country, kind: STATE|DISTRICT|CITY, name_en, name_te, parent_id}`.
   V1 scope: AP and Telangana (states + districts), US states, and a short
   curated list of major US/Indian cities. Free-text places are not accepted.
   No GPS; the reader picks from the list.
2. **Story place tags**: new table `story_places(story_id, place_id, role)`,
   `role = EVENT` only, same rules as `story_countries`: the model may
   propose place ids from the catalog, unknown values are dropped, editors can
   replace the set in admin (audited). A story with no place tag never matches
   a place follow. A district/city tag implies its parent state/country for
   matching, so following "Telangana" matches a Warangal story.
3. **Follows**: up to 10 places, stored on-device with the other preferences.
   For alerts only, place ids sync through the existing preferences endpoint
   (ADR-042 pattern), with a per-place alert switch.
4. **Ranking and explanation**: a place match adds a bounded additive term to
   the deterministic score (ADR-040). The reason string names the place, e.g.
   "Because you follow Warangal".
5. **Empty state**: a followed place with no stories shows an explicit empty
   state, never a silent fallback to other places.

## Open questions for the owner

- Confirm catalog scope (which cities) and who maintains it.
- Is model-proposed tagging acceptable for place tags, or editor-only at first?
- Backfill: tag existing stories, or apply to new stories only?

## Consequences

One migration (table), a contract change, admin editing UI, generation-schema
change, and mobile/web follow UI. Coverage depends on tagging quality, so
sparse tags mean many empty states at first.

## Alternatives considered

- **Reuse `home_state`/`home_city` strings**: single place only, free text,
  no story-side data to match.
- **GPS/auto-detect**: rejected by the ticket (explicit choice, no GPS).
- **Keyword match on headline text**: unreliable for Telugu/English spellings
  and not auditable.
