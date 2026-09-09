# ADR-005: Personalization model

- **Status**: accepted
- **Date**: 2026-09-08
- **Ticket**: T16

## Context

§8 gives an exact ranking formula and requires it to be deterministic and
explainable in V1 (no black-box ML). It names the formula's inputs
(`residence, home, topic, freshness, importance, source_quality,
repetition_penalty`) but doesn't define how each is computed from this
repo's actual schema, and three things are genuinely open:

1. **Where do preferences come from?** §8.1's preference model
   (`residence_country, residence_region, home_state, home_city, topics[],
   language, notification_mode`) is the same shape T04 already stubbed at
   `/v1/me/preferences`. But ADR-006 (account/privacy architecture) is still
   **proposed, not accepted** — T14/T15 both deliberately kept onboarding
   preferences on-device (`localStorage`/`AsyncStorage`) rather than
   persisting them server-side, specifically because that ADR hadn't landed.
   T16 must not unilaterally decide to persist preferences server-side just
   to have something to rank against — that would be deciding ADR-006's
   question inside a ticket that isn't ADR-006, which NON_NEGOTIABLES #11
   forbids.
2. **`source_quality`** has no backing column anywhere in §12's schema or
   this repo's `sources` table (T06/§6.2's field list).
3. **`repetition_penalty`** has no defined formula in §8.2 — only that it's
   subtracted.
4. **"Why this matters" per audience segment** (§8.3) needs a segment value,
   and §3.1's life-stage values are explicitly "preferences only; never
   infer... from reading behavior" — so a segment can't be derived from
   anything the server observes, only from what the client states.

## Decision

**The ranking formula is implemented exactly as §8.2 states, as pure
deterministic code in `app/content/ranking.py`** — no model call, no
randomness. Given the same preferences and the same story set, the score
and therefore the order are byte-identical across runs.

**Preferences are explicit per-request input, not server-persisted state.**
`GET /v1/home` accepts optional query parameters
(`residence_country, residence_region, home_state, home_city, topics,
language`) mirroring §8.1's model; when supplied, the feed is ranked against
them, with each item's contributing signals surfaced back for
explainability. When omitted, `/v1/home` returns its existing T14
chronological order unchanged — personalization is additive, never a
requirement to browse (NON_NEGOTIABLES #9). `PATCH /v1/me/preferences`
stays exactly as T04 stubbed it (validates and echoes the body) — there is
still no account row to persist against until ADR-006 is accepted; the
client (already holding these values on-device per T14/T15) is expected to
pass them on each personalized `/v1/home` request until that ADR lands.
Once ADR-006 is accepted, wiring `/v1/home` to read persisted preferences
instead of query params is a small, additive follow-up — the ranking
function itself (`rank_stories(stories, preferences)`) doesn't change, only
where `preferences` comes from.

**`source_quality`**: new `sources.quality_score` column (float, `0..1`,
default `0.5`), added by this ticket's migration. Not yet admin-editable —
every source starts at the same neutral default until a later ticket
exposes it in the source-registry CRUD (T06's territory). A story's
`source_quality` input is the average `quality_score` of every source it
cites.

**`repetition_penalty`**: a within-batch, per-topic diminishing-returns
penalty. Stories are first ordered by their raw (pre-penalty) score; walking
that stable order, each story's penalty is `0.05 * min(4,
already_ranked_same_topic_count)` (capped at `0.2`) — the 2nd+ story sharing
a topic with a higher-raw-scored story already placed loses a little
ground, so one topic can't fill the whole feed. Because the base order
before applying penalties is itself deterministic (score, then story id as
a stable tiebreaker), the penalized order is reproducible across runs for
the same input, satisfying the acceptance criterion.

**Audience segment**: an explicit, small enum mirroring §3.1's life-stage
values — `general | international_student | graduate_opt | professional |
family_parent | other` — passed by the client as an optional `segment` query
parameter, defaulting to `general`. It is never inferred from any signal
the server observes (matches §3.1's explicit "never infer... status or
other sensitive attributes from reading behavior" for the student case,
generalized to every segment here for the same reason).

**"Why this matters" caching**: new `story_why_matters_cache` table, unique
on `(story_id, segment)`. `app/content/why_matters.py::get_or_generate`
reads the cache first; only on a miss does it call `AiGateway.run_task`
(`Task.WHY_MATTERS`, already routed by T10 but never actually invoked until
this ticket — T11 covers the generic English `why_matters` as part of its
one `SUMMARY` call) with a new minimal `WhyMattersResult` contract, then
writes the cache row. A second request for the same `(story_id, segment)`
never calls the gateway again — verified via T10's `ai_call_log` telemetry
(one row per story/segment, not per request).

**Explainability**: the explanation string is built only from the signals
that actually contributed non-zero score for that story/preference pair
(e.g. residence match, home match, matched topic names) — never a canned
template unconditionally filled in.

## Consequences

- Ranking and "why this matters" both work today, without waiting on
  ADR-006 — the cost is that a personalized `/v1/home` request must carry
  the caller's preferences each time (a few short query params, already
  held on-device by T14/T15) rather than the server remembering them.
- `sources.quality_score` starts uniform (`0.5` for everyone) — the
  `0.04*source_quality` term is a live but currently-flat input until a
  later ticket differentiates it; revisit if source quality turns out to
  matter more than the spec's own small weight suggests.
- The repetition-penalty formula's constants (`0.05` step, `0.2` cap, `4`
  same-topic cap) are a judgment call with no spec-given numbers, same class
  of decision as T09's clustering thresholds — reasonable starting points,
  worth tuning once real feed usage exists.
- Once ADR-006 is accepted, `/v1/home` should switch to reading persisted
  preferences server-side (dropping the query-param requirement for a
  logged/anonymous-identified client) without changing `rank_stories`
  itself.

## Alternatives considered

- **Persist preferences server-side against an ad-hoc anonymous identity
  inside this ticket**: rejected — that's ADR-006's exact open question
  (device-scoped anonymous identity vs. something else), and T14/T15 already
  chose not to decide it themselves. Deciding it as a side effect of T16
  would pre-empt ADR-006 without going through it.
- **An ML/learned ranking model**: rejected — §8.2 explicitly requires V1 to
  be deterministic and explainable; the ticket itself calls out not
  substituting a model without a superseding ADR.
- **Generate "why this matters" fresh per feed request**: rejected — §8.3
  explicitly requires generate-once-and-cache; a per-request LLM call is
  also a direct, avoidable AI-budget cost multiplied by every viewer.
