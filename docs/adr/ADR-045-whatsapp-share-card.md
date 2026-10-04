# ADR-045: WhatsApp share card (image) vs. ADR-002 link-only content

- **Status**: accepted (owner 2026-10-04, Option A)
- **Date**: 2026-10-04
- **Ticket**: P08

## Context

`docs/tickets/P08.md` asks for an image card (headline, source attribution,
theteluguedit.com link, Telugu/English per reader language) plus a text
fallback. NON_NEGOTIABLES #15 / ADR-002 say the branded "Share Card" image
feature is deferred until a new ADR revisits it, and that stories never
reproduce source headline text, article text or images. Only `LINK_ONLY`
sources are enabled. Rendering a card image is therefore a content-republishing
question, which is a stop condition.

## Decision (proposed — owner to pick)

**Option A (recommended): card from TTE-authored text only.** Card contains our
own AI-drafted headline/summary line (never the source's headline or image),
the source name as attribution, and the canonical link. Source-headline
fallback is disallowed; ADR-019 link-first briefs (which carry the original
headline) get the text-only share instead of an image. Retracted/unpublished
stories return 404 for the card and cannot be shared. Telugu uses a bundled
Noto Sans Telugu font, rendered server-side.

**Option B: text-only share** (canonical URL + attribution line) via the native
share sheet on web and app; no image. Satisfies the ticket's fallback only.

## Consequences

A supersedes the "deferred" clause of ADR-002 for TTE-authored text only; it
does not enable `LICENSED_*` rights. It adds a renderer (web OG-style image
route) but no new infrastructure. B needs no rights change but drops the
card acceptance criterion.

## Alternatives considered

Client-side card rendering in the app (rejected: duplicate Telugu font/layout
logic, no web parity).
