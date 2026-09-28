# ADR-015: Gemini free tier as an AI provider (amends ADR-001)

- **Status**: proposed
- **Date**: 2026-09-28
- **Ticket**: Phase −1 / T22 prerequisite (`docs/plans/gemini-hetzner-telugu-plan.md` calls this "ADR-011"; that number is taken by the claim-evidence ADR, so it is ADR-015 here)

## Context

ADR-001 made OpenAI primary and Anthropic secondary. A Gemini adapter now exists
(`app/ai/providers/gemini_provider.py`, commit `0d69a87`) but is deliberately not in
`ROUTING`. Two facts decide whether it may be:

1. **Free-tier data terms.** Free-tier prompts/responses may be used by Google to
   improve its products. Paid tier does not. `NON_NEGOTIABLES.md` treats
   immigration/legal/financial/breaking as always human-reviewed, and editor
   corrections are unpublished staff copy.
2. **Confirmed limits** (AI Studio, project `TheTeluguEdit`, 2026-09-28, per project,
   RPD resets midnight Pacific):

   | Model | RPM | TPM | RPD |
   |---|---|---|---|
   | Gemini 3.8 Flash | 5 | 250K | 20 |
   | Gemini 3.5 Flash Lite | 15 | 250K | 500 |
   | Gemma 4 26B/31B | 30 | 16K | 14.4K |

   Spike 1 smoke test: 4.0 requests/story (classify, summary, why-matters,
   translate), ~0.8 s median latency. So Flash Lite carries **≈125 stories/day at
   best** before retries.

## Decision

1. **Free tier is for bulk, public, non-sensitive work only**, on Flash Lite
   (`GEMINI_FLASH_LITE`). 3.8 Flash is opt-in for spot checks, never a pipeline default.
2. **Three-state per-story privacy decision**, computed once before the first call,
   persisted, and consulted by every dispatch including escalations:
   `FREE_TIER_ALLOWED | RESTRICTED | UNKNOWN`. It starts at `UNKNOWN`; a story reaches
   `FREE_TIER_ALLOWED` only if its source category is on the allowlist below **and** no
   restricted keyword/entity/source signal fires. `RESTRICTED` and `UNKNOWN` never go to
   the free tier. Model-reported sensitivity may tighten, never loosen.
3. **Category allowlist v1** (keyed off the source's configured category, not inferred
   per story): `entertainment`, `sports`, `community_events`. Everything else — including
   politics, AP, Telangana, US, money, immigration, travel, jobs, education, students —
   is `UNKNOWN` until a later ADR extends the list with an owner's sign-off.
4. **Editor-authored text** (corrections, staff copy) never goes to the free tier.
5. **No paid provider configured ⇒ non-allowed stories hold for human triage**; they are
   never sent to free tier as a fallback.
6. **Quota handling**: token bucket per model at the confirmed RPM; RPD counted in the
   Pacific quota day (`budget.quota_day_start`); a 429 is a deferral, not a job failure
   and not a circuit-breaker trip; unavailable calls are still recorded.
7. **Routing changes only via `tasks.py`** and only after Spike 1 accepts Telugu
   quality (native-speaker grade of the 20-item sample, results in
   `infra/scripts/spike1_results.json`).

## Consequences

- Free tier covers only a narrow slice of content today; most stories need a paid
  tier. Turning on paid Gemini billing (same key/project) lifts both the training
  concern and the limits and is the expected launch configuration — a follow-up ADR
  would relax decision 2 accordingly.
- Requires new work: persisted privacy decision column, pre-classifier, rate limiter,
  and a Pacific-day request counter — T22.
- Revisit if Google changes free-tier limits or terms; re-read the AI Studio page before
  acceptance.

## Alternatives considered

- **Route everything to free tier** — rejected: sensitive and unpublished text would be
  eligible for training.
- **Blocklist-only pre-classifier** — rejected: false negatives send sensitive stories out
  by default; allow must be earned.
- **Claude/ChatGPT subscriptions as runtime** — not API access and against their consumer
  terms.
- **Stay on OpenAI/Anthropic only** — remains the fallback; costs money from day one.
