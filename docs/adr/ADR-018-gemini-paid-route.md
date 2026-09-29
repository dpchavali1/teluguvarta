# ADR-018: Paid Gemini route so AI drafts every story (amends ADR-001, ADR-015)

- **Status**: accepted (2026-09-29, owner)
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
   the story holds as it does today. Prices come from Google's pricing page
   (`PAID_GEMINI_PRICING`, 2026-09-29): 3.5 Flash-Lite is $0.30/$2.50 per 1M input/output
   tokens. 3.8 Flash uses its 2027 list price of $1.50/$7.50, not the lower 2026 promo,
   so the budget over-counts. At roughly 4 calls per story, that's about $0.006 per
   story. The owner lowered the budget to `MONTHLY_AI_BUDGET_USD=50` with
   `DAILY_AI_ALERT_USD=3` (ADR-007's 1/15 ratio). On a breach, generation degrades to
   classification-only, as before.
6. **No local limiter on the paid route.** Free-tier RPD and RPM counting
   (`ratelimit.py`) covers only `provider == "gemini"`. Paid limits are far above this
   volume, so `gemini_paid` relies on Google's own 429 (a deferral, as in ADR-015
   decision 6) and on the budget gate.
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
- Telugu quality: the owner accepted their earlier Spike 1 review (a blanket 4/5) as
  sufficient and declined a separate grading pass. The safeguard is unchanged: every
  Telugu variant goes through the automated Telugu QA gate and a human approval before
  it publishes. Revisit if reviewers keep rewriting paid-route Telugu.
- Unblocks automation plan step 3 (ADR-011 auto-publish lane), which needs real
  `sensitivity` values to exist.
- Implemented 2026-09-29:
  - `PaidGeminiProvider`, and route selection in `tasks.route_for`.
  - Provider-aware pricing: `pricing_for` and `cost_usd(..., provider=)`.
  - The gateway's fail-closed refusal.
  - Env vars in `.env.example` and the `deploy.sh` template (prod compose already
    loads `.env.prod` whole).
  - `tests/test_paid_gemini_route.py`.

  The escalation fields in `PAID_GEMINI_ROUTING` are declarative only, like every other
  route: the gateway doesn't escalate today.

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

## Owner decisions (2026-09-29)

1. Separate paid project: yes.
2. Monthly AI budget: $50 (daily alert $3).
3. Telugu grading: not required; the earlier Spike 1 review stands.
