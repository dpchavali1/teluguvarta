# ADR-021: Free-tier quota accounting for pinned Gemini models

- **Status**: proposed
- **Date**: 2026-09-29
- **Ticket**: automation plan follow-up ("pinned-model limiter and quota accounting"); amends ADR-015 decision 6

## Context

ADR-015 decision 6 meters the free tier per model id: `FREE_TIER_LIMITS` in
`app/ai/ratelimit.py` has entries only for the two aliases,
`gemini-flash-latest` (5 RPM / 20 RPD) and `gemini-flash-lite-latest` (15 RPM / 500 RPD).
`app/ai/tasks.py` lets an operator pin the free-tier model with
`AI_GEMINI_FLASH_MODEL` / `AI_GEMINI_FLASH_LITE_MODEL`, for example to freeze
a model for an eval.

The gaps:

1. **A pinned id has no limits, so every call is refused.** Until 2026-09-29 this was
   recorded as `DEFERRED`, which looks just like a normal quota wait, and allowlisted
   stories waited forever with no signal. **This part is fixed without an ADR:** the gateway now
   records `UNAVAILABLE` and logs an error, and `alerts.check_ai_model_refusal_alerts`
   fires once per model per worker alert pass.
2. **Alias and pinned id are counted separately.** `requests_today` filters on the
   exact `model` string. If Google counts an alias and the id it points to against
   one quota, switching between them mid-day, or adding a pinned-id entry next
   to the alias, lets us plan for up to twice the real RPD. The result is extra 429s,
   which ADR-015 already treats as deferrals, not failures. So the risk is wasted
   calls and slower drafting, not cost or data exposure.

We don't know how Google counts quota between an alias and a pinned id. The
current numbers came from the owner reading AI Studio on 2026-09-28. This ADR
does not assume either answer.

## Decision (proposed)

1. Key `FREE_TIER_LIMITS` by **quota family** (`flash`, `flash-lite`), not by
   model id, with an explicit map from each allowed model id (the alias plus any pinned
   ids the owner has confirmed) to its family.
   `requests_today` and the RPM bucket count every model in the family together.
   Pinned ids remain opt-in: an id not in the map is still refused (`UNAVAILABLE`
   + alert). Counting jointly is the conservative choice whichever way Google
   counts, because we can only under-use quota, never over-plan.
2. The owner confirms in AI Studio, for each pinned id added to the map, that its
   free-tier RPM/RPD match the family's limits. If they differ, that id gets its own
   family.
3. No env-var override of RPM/RPD. Limits stay in code, so a change is reviewed.

## Consequences

- Pinning a free-tier model for an eval takes a one-line code change (add the id
  to the map) rather than silently stopping the free tier.
- If Google actually counts quota per id, joint counting leaves some quota
  unused. At current volume (the paid route handles everything off the allowlist),
  that costs little.
- The paid route is unchanged: ADR-018 decision 6 (no local limiter) stands.

## Alternatives considered

- **Leave it as is (per-id limits; the new alert is the only guard).** This is the smallest
  change and is acceptable if nobody plans to pin free-tier models. It is rejected only
  because it leaves the double-counting trap in place for the first person who pins one.
- **Env-var RPM/RPD overrides.** These are flexible, but they let an unreviewed `.env.prod` edit
  raise limits past what AI Studio allows.
- **Read limits from the Gemini API at runtime.** No endpoint we have confirmed exposes
  per-project free-tier limits, so this is rejected until one does.

## Owner questions

1. Do you plan to pin free-tier models at all? If not, choose "leave it as is"
   and close this.
2. If yes, which pinned ids are needed, and what RPM/RPD does AI Studio show for each?
