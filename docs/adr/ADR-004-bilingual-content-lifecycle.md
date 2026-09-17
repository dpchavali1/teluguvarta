# ADR-004: Bilingual content lifecycle

- **Status**: accepted
- **Date**: 2026-09-08
- **Ticket**: T13

## Context

NON_NEGOTIABLES #7: "English is canonical. Telugu is a derived, versioned
variant with explicit QA status; an approved English correction invalidates
the existing Telugu variant for regeneration." §4.2/§4.3 add three concrete
requirements this ADR has to settle before T13's code can be written:

1. What does "derived, versioned" actually mean for `story_variants` rows —
   one row per language that gets overwritten, or something append-only?
2. What happens when a Telugu variant doesn't exist yet, or exists but fails
   QA — does the API ever expose a broken/missing translation, or must it
   fall back to something?
3. What "invalidates... for regeneration" concretely does to the row T12
   already wired a deletion hook against (`app/routers/admin.py::correct_story`).

## Decision

**Storage/versioning**: one `StoryVariant` row per `(story_id, language)`
(T03's existing `uq_story_variants_story_language` unique constraint) — not
append-only history. "Versioned" is satisfied by `generated_at` +
`model_version` on that single row (already in T03's schema, unused until
this ticket), not by keeping every past translation attempt as a separate
row. A `Correction` row (T12) already carries the before/after hash for the
*English* side; nothing in §12 asks for a parallel history table on the
Telugu side, and adding one without a stated read need would be exactly the
kind of unrequested infrastructure NON_NEGOTIABLES tells this build to avoid.

**Fallback behavior**: `app/content/variants.py::resolve_display_variant`
is the single place this is decided. A request for `te` serves the `te`
variant only if it exists **and** `qa_status == 'PASSED'`; otherwise it
serves the `en` variant and reports `fallback=True`. A request for `en`
never falls back further — if no `en` variant exists the story has nothing
to serve, which shouldn't be reachable past T11 (every generated story gets
an `en` variant before anything else happens to it). This function is pure
(no DB access, no AI call) so both the admin detail view (T12, already
returns every variant + its `qa_status`) and the public API (T14) can call
the same fallback rule instead of each re-deciding it.

**QA gate**: `app/content/qa.py::find_qa_issues` compares the Telugu text
against the English text it was derived from and flags any dropped number,
date (month name), currency amount, URL, or negation. Any issue sets
`qa_status = 'FAILED'`; a failed variant is never treated as "the Telugu
version," per the fallback rule above — it stays in the table (useful for a
future admin QA-fix view) but is functionally identical to having no `te`
row at all from a reader's perspective.

**Glossary enforcement**: `app/content/glossary.py::apply_glossary` runs
*after* the AI gateway's translation call, correcting known proper
nouns/places/orgs to their canonical Telugu spelling. This is a
deterministic post-process over the model's raw output, not a prompt-only
instruction relied on to "just work" — the whole point of a glossary is
that it's enforced, not requested.

**Correction-invalidation mechanism**: unchanged from what T12 already
built — an approved English correction (`correct_story`) deletes the
existing `te` `StoryVariant` row outright rather than marking it stale.
"Regeneration" isn't a separate signal or flag: the T13 translation sweep
(`app/jobs/translate.py::translate_stories`) processes every story with an
`en` variant and no `te` variant, so a story that just had its `te` row
deleted is, by construction, back in that set on the very next sweep. This
mirrors T09's "don't invent a state for something a query can already
express" precedent (no `DEDUPED` status; no `te` status column here either).

**Early-launch review sampling**: `SAMPLED_SENSITIVITIES` (`IMMIGRATION`, `LEGAL`,
`FINANCIAL`) plus a `TELUGU_REVIEW_SAMPLE_RATE` env flag (default `0.2`)
routes a random subset of QA-passed translations in those categories into
the existing `review_tasks` queue — reusing T11/T12's `ReviewTask` model
rather than a new table, since this is exactly the same "an editor needs to
look at this before it's fully trusted" shape.

## Consequences

- No Telugu translation history is kept — only the current row per
  language. If a future ticket needs "show me the last 3 Telugu drafts,"
  that's a new table, not a retrofit of this one.
- A story can be fully published in English while its Telugu variant is
  still pending/failed — expected and desired, not a bug: Telugu readers
  see English rather than nothing, exactly per §4.2.
- The QA checks are deliberately narrow (number/date/currency/URL/negation
  substring presence) — they catch *omission*, not *mistranslation* of
  something that's syntactically still present. A fluent but factually
  wrong Telugu sentence that keeps every number intact would still pass.
  Broader semantic QA is out of scope until real translation volume shows
  it's needed.
- The glossary is a hand-maintained seed list (`GLOSSARY_EN_TE`), not a
  managed admin CRUD surface — expected to grow ad hoc as real translation
  output surfaces new terms worth pinning; a dedicated glossary-management
  UI is a candidate for a later ticket once the list is large enough to
  need one, not before.

## Alternatives considered

- **Append-only variant history** (one row per translation attempt):
  rejected — nothing in §12 or any consuming endpoint reads translation
  history; `generated_at`/`model_version` on the single current row already
  answers "when was this generated, by what."
- **A `story_variants.status` flag ('STALE'/'CURRENT') for invalidation**
  instead of deletion: rejected — T12 already implemented deletion before
  this ADR was written, and it composes for free with the translation
  sweep's "no `te` row yet" query; a status flag would need that query (and
  every other `te`-variant reader) to additionally filter it out.
- **Serving a failed-QA Telugu variant anyway, with a warning banner**:
  rejected — NON_NEGOTIABLES #7 and §4.2 are explicit that a broken
  translation must not be served; a silent, correct English fallback is
  the simpler and safer default for V1.
