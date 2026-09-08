# packages/ai

**Per ADR-001, the actual AI provider gateway is implemented in Python at
`apps/api/app/ai/`, not here.** Every AI-consuming caller (ingestion/dedup
pipeline, future story generation) is already Python code in `apps/api`, so
routing/schema-validation/cost-telemetry logic lives there — see
[ADR-001](../../docs/adr/ADR-001-ai-provider-selection.md) for the full
reasoning. `apps/api/app/ai/providers/{openai,anthropic}_provider.py` are
the only two files allowed to import a provider SDK, enforced by a CI grep
check (`.github/workflows/ci.yml`, `api` job).

This package is kept only as a TypeScript mirror of §7.3's structured
output contract (`GenerationResult`, in `index.ts`), for `apps/admin` to
type AI-generated fields it reads back over the API. It has no HTTP client
and never calls a provider.
