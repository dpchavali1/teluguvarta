# ADR-027: Story geography and importance, separated from publisher origin and model confidence

- **Status**: accepted (owner, 2026-09-30); implemented 2026-09-30
- **Date**: 2026-09-30
- **Ticket**: review 2026-09-29 finding #10 (`docs/reviews/2026-09-29-comprehensive-review.md`)

## Context

Two fields carry meanings they weren't designed for.

**Importance is model confidence.** `generate.py` sets
`story.importance = classification.confidence`, which measures how sure the
model is that the item is relevant, not how much the story matters. Readers of
the field disagree about what it means:

- `brief_lane.py` compares it to `MIN_CONFIDENCE`, and its comment says it holds
  confidence.
- `notifications.breaking_alert_eligible` compares it to
  `BREAKING_ALERT_MIN_CONFIDENCE`, which is also a confidence reading.
- `notifications.topic_alert_eligible` (`TOPIC_ALERT_MIN_IMPORTANCE = 0.5`) and
  ranking (`0.14 * importance`) treat it as editorial significance.
- Hand-drafted stories (both live ones) keep the column default `0`, so they
  rank lowest and never qualify for an alert.

A confident, minor story ranks and alerts like a major one, and an uncertain
major story doesn't.

**Countries are publisher origin.** `serialize.story_to_out` and
`story_to_rankable` list the `Source.country` of each linked source, and the
`?country=` filter joins on `Source.country`. A UK event reported by a US
publisher shows a US badge, ranks as "you live in US", and is missing from a UK
filter. The generation contract returns `countries`, but nothing stores them.

The spec defines the Story as `id, canonical_slug, status, sensitivity,
importance, published_at, updated_at` (§ data model) and gives the ranking
formula. It says nothing about how importance is computed or how geography is
modeled. `serialize.py` notes that a real country model is future work and was
left undecided on purpose. Choosing definitions means choosing product
behavior, so this needs an owner decision.

## Decision (proposed)

### 1. Confidence gets its own column

- Add nullable `stories.classification_confidence`. Generation writes the
  confidence there, not to `importance`.
- The brief lane and the breaking-alert confidence gate read
  `classification_confidence`. A story with no confidence (hand-drafted) is
  not eligible for the brief lane. For a breaking alert, the editor's
  existing breaking-alert approval is then the only gate (a hand-drafted
  story has no model confidence to check).
- Urgency was never stored, so generation now stores it on
  `stories.urgency` (`NORMAL` | `HIGH`) for the importance formula.
- Migration: copy `importance` into `classification_confidence` for stories
  with an AI-generated English variant, then recompute `importance` as in 2.

### 2. Importance is deterministic, and an editor can override it

No model call; ranking stays out of the LLM (the review's constraint):

```
importance = 0.4
           + 0.2  if urgency is HIGH
           + 0.1  per additional independent source in the story's cluster (max +0.3)
           + 0.1  if the story is in an audience-priority topic (immigration, students)
clamped to [0, 1]
```

The weights are a starting point, to be tuned against observed feeds.
Hand-drafted stories get the same formula (base 0.4 plus their sources), not
0. Admin gets a Low / Normal / High override (0.2 / 0.5 / 0.8), stored on
`stories.importance_override`. It is audited
like the other story edits and takes precedence over the formula.

### 3. Event geography is stored separately from publisher origin

- New table `story_countries(story_id, country_code, role)`. `role` is
  `EVENT` in V1; `AUDIENCE` is reserved for later and not written now.
- Generation writes the model's `countries` as `EVENT` rows, after
  normalizing each to an ISO 3166-1 alpha-2 code that is in
  the configured country list (the list clients offer in `packages/domain`:
  US, IN, CA, GB, AU, AE, SG, NZ, DE). Unknown values are dropped, not guessed.
- Editors can set event countries in admin, which replaces the set and is
  audited (the same pattern as `PUT /stories/{id}/topics`).
- Badges, the residence-country ranking signal and `?country=` use `EVENT`
  rows only. A story with none shows no country badge and gets no residence
  match. It **never falls back to the publisher's country**.
- `Source.country` stays as publisher metadata and a source-quality/diversity
  input. It is not shown as the story's location.

## Consequences

- The UK-event/US-publisher case shows UK, or nothing, and never US. Tests:
  that case, a high-confidence low-importance item, and a hand-drafted story
  with no confidence.
- The two live stories lose their US badge until an editor sets event
  countries, alongside the topic tagging already pending in admin.
- One migration (column plus table). The brief lane and alerts change which
  field they read. Their thresholds stay the same.
- Push alerts may fire for different stories than today: hand-drafted stories
  become eligible for topic alerts, and confident-but-minor ones stop being
  eligible.
- Revisit: `AUDIENCE` relevance (for example, a US visa rule that matters to
  readers in India) when there's inventory to justify it; the formula weights
  once there are a few weeks of feeds.

## Alternatives considered

- **Model-reported importance field.** Rejected: it makes ranking an LLM
  judgment, costs contract changes and retries, and can't be applied to
  hand-drafted stories without a paid call.
- **Editor-only importance.** Simple, but every auto-published story would
  sit at a default, so ranking would be flat for most of the feed.
- **Keep publisher country, just hide the badge.** Hides the symptom only.
  Ranking and the country filter would still be wrong.
- **Store the model's countries without normalization.** Free text ("USA",
  "United States", "America") would break filtering and matching.
