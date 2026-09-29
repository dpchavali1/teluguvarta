# ADR-018: Paid Gemini route so AI drafts every story (amends ADR-001, ADR-015)

- **Status**: proposed
- **Date**: 2026-09-29
- **Ticket**: automation plan step 2 (PROGRESS.md, "Automation plan agreed with owner")

## Context

Prod runs with `AI_FREE_TIER_ENABLED` set and no OpenAI/Anthropic key. Under ADR-015
decision 5, every story whose privacy decision isn't `FREE_TIER_ALLOWED` holds as
`NO_PAID_PROVIDER`. That is almost every story, because the allowlist is only
entertainment, sports and community events, and prod has no source in those categories.
These holds cause three problems:

- No draft is written, so an editor writes each story by hand.
- No classification runs, so sensitivity stays a default `NONE`. Admin now labels these
  holds `UNCLASSIFIED`, but a terror-plot story gets no always-human-reviewed friction.
- ADR-015's Consequences already expect "turning on paid Gemini billing" as the launch
  configuration, with a follow-up ADR to relax decision 2. This is that ADR.

The code assumes one Gemini tier. There is one `gemini` provider, and
`paid_provider_configured()` only looks at the OpenAI and Anthropic keys. Also,
`MODEL_PRICING` prices both Gemini aliases at $0, and `ratelimit.py` counts every
`provider == "gemini"` call against the free-tier limits. If billing were simply turned
on for the existing key, paid calls would be counted as free, and the
`MONTHLY_AI_BUDGET_USD` gate (ADR-007) would never trip.

Google applies billing per Cloud project. Once a project has billing, all of its calls
are paid-tier: they aren't used for training and they get paid limits. One key can't be
free for some stories and paid for others.

## Decision

1. **Two Gemini providers, two projects.** `gemini` keeps the existing free-tier key
   (`AI_GEMINI_API_KEY`, project `TheTeluguEdit`, no billing) and stays restricted to
   ADR-015. A new `gemini_paid` provider uses `AI_GEMINI_PAID_API_KEY` from a separate
   project with billing enabled. The `gemini_paid` adapter is the existing Gemini
   adapter with a different key and name, not a second SDK integration.
2. **`paid_provider_configured()` is also true when `AI_GEMINI_PAID_API_KEY` is set.**
   With it set, ADR-015 decision 5 stops holding stories, and `RESTRICTED`/`UNKNOWN`
   stories route to `gemini_paid`. Paid-tier data isn't used for training, which removes
   the reason ADR-015 kept them off Gemini. `FREE_TIER_ALLOWED` stories still go to the
   free tier first. Editor-authored text may go to `gemini_paid`, never to `gemini`.
3. **Paid routing table (`PAID_GEMINI_ROUTING` in `tasks.py`)**, used only when neither
   the OpenAI nor the Anthropic key is set, so ADR-001's routing wins whenever it is
   configured:
   - classification, summary, why-matters and translation: Flash Lite, escalating to
     Flash;
   - sensitive validation: Flash. It stays `always_human_review=True`.
   Dedup embeddings keep their current route. With no embedding provider, dedup stays
   deterministic, as it is today.
4. **Human review rules don't change.** Immigration, legal, financial, breaking and every
   other rule in `NON_NEGOTIABLES.md` still hold for a human. This ADR changes *who writes
   the draft and the classification*, not *who approves*. Once classification runs, a
   sensitive story reaches the queue with its real sensitivity, so the
   always-human-reviewed friction applies to it again.
5. **Cost accounting fails closed.** Pricing is looked up by `(provider, model)`, so
   `gemini_paid` calls can't inherit the free tier's $0. The gateway refuses a
   `gemini_paid` call that has no pricing entry. That call counts as unavailable, and
   the story holds as it does today. Prices are copied from Google's pricing page when
   billing is enabled, not guessed here. The existing `MONTHLY_AI_BUDGET_USD=150` /
   `DAILY_AI_ALERT_USD=10` gate applies unchanged.
6. **Separate rate-limit buckets.** `ratelimit.py` keys by provider, so free-tier RPD
   counting covers only `gemini`. `gemini_paid` limits are read from AI Studio after
   billing is enabled and set via env. A 429 is still a deferral, as in ADR-015
   decision 6.
7. **Pinned models on the paid route.** `AI_GEMINI_PAID_FLASH_MODEL` and
   `AI_GEMINI_PAID_FLASH_LITE_MODEL` must be pinned ids (for example `gemini-3.5-flash-lite`),
   not `-latest` aliases. This keeps pricing entries and Telugu-quality evidence tied to
   one model. The gateway refuses an alias on `gemini_paid`.

## Consequences

- Every story gets an AI draft and a real classification. The `NO_PAID_PROVIDER` hold
  and the `UNCLASSIFIED` admin label become rare fallbacks (key missing, budget
  breached, or outage).
- It costs money from day one, bounded by the existing budget gate. The owner confirms
  the monthly cap before acceptance.
- Single vendor: with only Gemini configured, a Google outage or policy change stops all
  drafting. That's acceptable because the fallback is the current behavior (hold for a
  human). Adding an OpenAI or Anthropic key restores ADR-001's two-vendor routing without
  code changes.
- Telugu quality evidence is weak. Spike 1's grade was a blanket 4/5 on a subset, and
  translation has a Telugu QA gate plus human review. Acceptance should include a
  row-by-row grade of at least 10 paid-route Telugu outputs, recorded in
  `infra/scripts/spike1_results.json`.
- Unblocks automation plan step 3 (ADR-011 auto-publish lane), which needs real
  `sensitivity` values to exist.
- Implementation work: `gemini_paid` provider registration, `(provider, model)` pricing
  keys, the `PAID_GEMINI_ROUTING` table and selection, the extended
  `paid_provider_configured()`, per-provider rate-limit keys, env vars in `.env.example`
  and `docker-compose.prod.yml`, and tests for each fail-closed path.

## Alternatives considered

- **Enable billing on the existing project.** It's one key, but it gives up the free
  quota. The more serious problem is that the $0 pricing and free-tier limits would
  silently apply to paid calls, unless decisions 5–6 were done anyway. Reasonable if the
  owner prefers one project; decisions 3–7 still apply, and the free route is then
  deleted.
- **Enable OpenAI/Anthropic keys (ADR-001 as written).** No new code, but it costs more
  per story than Flash Lite, and it needs two vendor accounts for the full routing.
- **Widen the free-tier allowlist.** Rejected: free-tier data can be used for training,
  which is the thing ADR-015 guards against.
- **Keep holding everything for humans.** This is the status quo. It doesn't scale, and
  it leaves stories unclassified.

## Owner decisions needed before acceptance

1. Separate paid project (recommended) or billing on the existing one.
2. Confirm or change `MONTHLY_AI_BUDGET_USD` for the paid route.
3. Who grades the 10 paid-route Telugu outputs.
