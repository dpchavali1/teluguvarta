// Type-only mirror of the §7.3 structured output contract, kept in sync by
// hand with apps/api/app/ai/contracts.py::GenerationResult. Read-only usage
// (apps/admin typing AI-generated fields read back over the API) — see
// README.md and ADR-001 for why the gateway itself lives in apps/api, not
// here.

export interface Claim {
  text: string;
  source_refs: string[];
}

export interface GenerationResult {
  relevant: boolean;
  confidence: number;
  categories: string[];
  countries: string[];
  places?: string[];
  entities: string[];
  sensitivity: string;
  urgency: string;
  summary_en: string;
  why_matters_en: string;
  claims: Claim[];
  source_refs: string[];
  publish_recommendation: string;
}
