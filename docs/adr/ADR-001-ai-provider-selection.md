# ADR-001: AI provider selection

- **Status**: accepted
- **Date**: 2026-09-08
- **Ticket**: T10

## Context

§7.2 requires per-task model routing (default/escalation) through a single
internal gateway, never a provider SDK in product code (NON_NEGOTIABLES #8).
Two things had to be settled before any gateway code could be written:

1. **Which provider(s)**, since §10's "AI: internal provider gateway — avoid
   vendor lock-in" and §7.2's routing table ("English → Telugu: low-cost
   translation model, escalation: second provider / human sample review")
   both assume the answer is "more than one, behind one interface."
2. **Where the gateway lives.** §11's monorepo layout puts `packages/ai`
   (a TypeScript workspace package) as "provider gateway + task contracts."
   But every actual AI-consuming caller built so far — and every one
   `docs/BUILD_ORDER.md` schedules next (T09's dedup escalation stub, T11's
   story generation) — is Python code in `apps/api` (§10: "API: FastAPI +
   Python"). `apps/web`/`apps/admin`/`apps/mobile` never call AI providers
   directly (NON_NEGOTIABLES #8 is about keeping SDKs out of domain/app
   code generally, not about TS vs. Python specifically). Building the
   actual gateway in TS would mean either a second HTTP hop from
   `apps/api` into a Node process for every AI call, or duplicating the
   gateway logic in both languages — neither is in the spec and both add
   infrastructure (NON_NEGOTIABLES stop condition: don't add infra without
   a measured need). This is exactly the "repo already has conflicting
   architecture for the thing you're about to build" stop condition, so it
   gets settled here instead of guessed at in code.

## Decision

**Providers: OpenAI primary, Anthropic secondary/escalation.**

- OpenAI is the default provider for relevance/categorization, summary,
  "why this matters", and EN→TE translation's default (fast/cheap) leg —
  `gpt-4o-mini` as the default-tier model, `gpt-4o` as the escalation-tier
  model for the tasks §7.2 marks as escalating to "a higher-quality model."
- Anthropic (Claude) is: (a) the "second provider" leg of EN→TE
  translation escalation per §7.2, satisfying provider-agnosticism with an
  actual second vendor rather than a second model from the same vendor,
  and (b) the provider for sensitive-content validation, using
  `claude-3-5-sonnet` as the "higher-quality reasoning model" §7.2 calls
  for — chosen as a second vendor rather than OpenAI again so a
  single-provider outage or policy change can't silently take out both the
  main pipeline and sensitive-content handling at once.
- Language detection uses a deterministic Unicode-range check (Telugu
  script block vs. Latin), not a model call at all — §7.2 explicitly lists
  "small/cheap model **or deterministic library**" for this task, and
  NON_NEGOTIABLES' engineering defaults prefer deterministic code over an
  LLM call wherever one suffices. Telugu-vs-English script detection is
  exactly that case.
- Dedup/clustering escalation (the `_escalate_to_ai` stub T09 left) uses
  OpenAI's `text-embedding-3-small` for pairwise similarity on the
  ambiguous band only — fingerprint + lexical similarity (T09) still
  handles the common case with no AI call at all, per §7.2.
- Sensitive validation **always** routes to human review in V1 regardless
  of model output, per §7.2's explicit line — the model call still runs
  (so reviewers see a machine-assisted read), but the gateway never lets a
  sensitive-category result auto-publish.

No model call is hardcoded outside the routing table in
`apps/api/app/ai/tasks.py`; swapping either provider means changing that
table and the two provider adapter files, not product code — this is the
"no provider hardcoded into product logic" property.

**Gateway location: Python, at `apps/api/app/ai/`, not the TS
`packages/ai`.**

This diverges from the literal `packages/ai` file location in §11's
diagram, but not from its intent (NON_NEGOTIABLES #8's actual requirement:
"All AI calls go through the internal provider gateway. No provider SDK
may leak into domain or app code"). Only `openai_provider.py` and
`anthropic_provider.py` under `apps/api/app/ai/providers/` import their
respective SDKs (`openai`, `anthropic`); every other caller — job handlers,
routers, future story-generation code — imports `apps/api/app/ai/gateway.py`
and never touches a provider client directly. That is the actual chokepoint
the non-negotiable cares about, and it's enforced the same way
`packages/ai` would have been (see Consequences).

`packages/ai` (TypeScript) is kept, but narrowed to a thin type-contract
mirror of §7.3's structured output shape (`GenerationResult` etc.) for
`apps/admin` to type cost-telemetry/review-queue data it reads over the
API — it has no HTTP client, no SDK dependency, and cannot call a provider
even in principle. Its README and `docs/adr/README.md` are updated to
point here instead of implying it's the enforcement boundary.

## Consequences

- Every future ticket that adds an AI-consuming task (T11 story generation,
  T13 translation, etc.) calls `apps/api/app/ai/gateway.py::AiGateway`,
  not a provider SDK — enforced by a CI grep step (`api` job in
  `.github/workflows/ci.yml`) that fails the build if `import openai` /
  `import anthropic` (or `from openai`/`from anthropic`) appears anywhere
  under `apps/api/app` outside `apps/api/app/ai/providers/`.
- `AI_PROVIDER_API_KEY` (generic, provider-unspecified) in `.env.example`
  is replaced with `AI_OPENAI_API_KEY` and `AI_ANTHROPIC_API_KEY` — the
  gateway now needs to address a specific provider per task, so a single
  ambiguous key no longer fits.
- Adding a third provider, or swapping either one, touches only
  `apps/api/app/ai/providers/` (new adapter file) and the routing table in
  `apps/api/app/ai/tasks.py` — no caller changes.
- `packages/ai`'s scope is now smaller than §11 implies at a glance;
  anyone reading the monorepo layout table should read this ADR alongside
  it. Revisit if a TS-side AI caller ever legitimately appears (none does
  today — `apps/web`/`apps/admin` only ever read AI-generated fields back
  from the API, never generate them).
- Model names/pricing in `apps/api/app/ai/tasks.py::MODEL_PRICING` are
  current best-effort figures, not billed rates — cost telemetry (T10
  scope) is only as accurate as these; revisit when real invoices are
  available.

## Alternatives considered

- **Single provider (OpenAI only)**: rejected — fails §10's explicit
  "avoid vendor lock-in" goal and §7.2's "second provider" requirement for
  translation escalation; a provider outage or policy/pricing change would
  have no fallback anywhere in the pipeline.
- **Build the gateway in `packages/ai` (TS) and have `apps/api` call it
  over HTTP**: rejected — adds a second always-on service and an internal
  network hop for every AI call, which is exactly the kind of
  infrastructure NON_NEGOTIABLES' stop conditions say not to add without a
  measured need; V1 has no caller that isn't already Python.
- **Duplicate gateway logic in both `apps/api` (Python) and `packages/ai`
  (TS)**: rejected — two implementations of the same routing/validation/
  budget logic drift out of sync, and nothing in the spec currently needs
  a TS-side caller.
- **Local/open-weight model instead of a hosted provider**: rejected for
  V1 — no self-hosting infrastructure is budgeted (§19, §10's "avoid
  operational cost"), and hosted providers' structured-output/JSON-mode
  support is what makes §7.3's schema contract enforceable without extra
  parsing work.
