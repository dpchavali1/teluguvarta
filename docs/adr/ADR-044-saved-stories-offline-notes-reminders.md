# ADR-044: Saved stories 2.0 — bookmarks with collections, notes, reminders

- **Status**: accepted (owner, 2026-10-04)
- **Date**: 2026-10-04
- **Ticket**: P06

## Context

P06 asks for collections, read-later reminders, per-story notes and offline
reading of saved stories. The owner decided (2026-10-04) that a save is only a
**bookmark**: no story text is stored on the device. That removes the expiry
and correction/retraction problem that persisted copies would create (review
R10), because Saved keeps resolving current data from the API. ADR-042 syncs
only saved IDs (no notes, no timestamps), so notes and collections stay off the
server.

## Decision (proposed)

1. **Offline reading is dropped from P06.** Saved stories load from the API as
   today; offline they show the existing "couldn't load, bookmarks kept" state.
   The in-memory story cache is unchanged. Offline reading would need its own
   ADR later.
2. **Storage**: on-device only (AsyncStorage), keyed by story ID. Notes,
   collections and reminder times never leave the device and are not added to
   ADR-042 sync.
3. **Collections**: reader-named lists, max 20, name max 40 chars; a story may
   be in several. **Notes**: plain text, max 500 chars per story. No sharing,
   no UGC surface.
4. **Reminders**: one local "read later" notification per saved story via
   `expo-notifications` local scheduling; no server involvement, respects the
   OS permission, cancelled on unsave/clear data.
5. **Retractions/corrections**: always current because nothing is copied. A
   story the API no longer serves is shown as "no longer available" with a
   Remove action; its note and collection membership are kept until removed.
6. **Deletion**: unsaving, "clear data" and account deletion remove the note,
   collection membership and reminder (new keys join `LOCAL_DATA_KEYS`).

## Consequences

Much smaller and safer than offline copies: no stale sensitive stories, no
storage growth beyond small text. Cost: Saved needs a connection to show
content. Needs device verification (restart persistence, reminder delivery).

## Alternatives considered

- **Offline copies of saved stories** (original proposal): rejected by owner.
- **Server-synced notes/collections**: needs ADR-006 amendment and privacy
  copy; rejected for V1 as the ticket says local-first.
