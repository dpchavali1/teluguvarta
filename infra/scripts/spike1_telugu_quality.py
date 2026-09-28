"""Spike 1 harness (docs/plans/gemini-hetzner-telugu-plan.md, Phase -1):
run stories through Gemini for classify + summary + why-matters + EN->TE
translation, record latency and *actual requests per story*, and write a
grading sheet for a native Telugu speaker.

Input is the 30 human-reviewed golden-set items (this machine has no real
story DB); each carries a reviewed Telugu reference (`te_good`) to compare
against. Paced to the free-tier RPM; 30 stories x 4 calls = 120 requests,
inside Flash Lite's 500 RPD. Run from apps/api:

    AI_GEMINI_API_KEY=... .venv/bin/python ../../infra/scripts/spike1_telugu_quality.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.ai.providers.base import ProviderUnavailableError
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.tasks import GEMINI_FLASH_LITE, Task

GOLDEN = ROOT / "apps" / "api" / "eval" / "golden_set.json"
OUT = ROOT / "infra" / "scripts" / "spike1_results.json"
RPM = 12  # under Flash Lite's 15 RPM
MIN_GAP = 60.0 / RPM

CALLS = {
    "classify": (
        Task.RELEVANCE_CATEGORIZATION,
        'Classify this news story for a Telugu diaspora audience. Return JSON '
        '{{"category": str, "sensitivity": "NONE"|"IMMIGRATION"|"LEGAL"|"FINANCIAL"|"BREAKING"}}.\n'
        "Headline: {h}\nSummary: {s}",
    ),
    "summary": (
        Task.SUMMARY,
        'Write a 2-sentence English summary using only facts below. Return JSON {{"summary_en": str}}.\n'
        "Headline: {h}\nFacts: {s}",
    ),
    "why_matters": (
        Task.WHY_MATTERS,
        'In one sentence, say why this matters to Telugu readers abroad, using only the facts '
        'below. Return JSON {{"why_matters_en": str}}.\nHeadline: {h}\nFacts: {s}',
    ),
    "translate": (
        Task.TRANSLATION_EN_TE,
        "Translate this English news story into Telugu. Preserve every number, date, currency "
        "amount and negation exactly. Use standard Telugu spelling for well-known proper nouns. "
        'Return JSON {{"headline_te": str, "summary_te": str}}.\nHeadline: {h}\nSummary: {s}',
    ),
}


class Pacer:
    def __init__(self) -> None:
        self.last = 0.0
        self.requests = 0
        self.retries_429 = 0

    def call(self, provider, model, task, prompt):
        for attempt in range(3):
            wait = MIN_GAP - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            self.requests += 1
            start = time.monotonic()
            try:
                resp = provider.complete(model=model, task=task, prompt=prompt)
                return resp, time.monotonic() - start
            except ProviderUnavailableError:
                self.retries_429 += 1
                time.sleep(30 * (attempt + 1))  # quota/5xx: back off, retry
        return None, 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--model", default=GEMINI_FLASH_LITE)
    args = ap.parse_args()

    items = json.loads(GOLDEN.read_text())["items"][: args.limit]
    provider, pacer = GeminiProvider(), Pacer()
    rows, latencies, tok_in, tok_out = [], [], 0, 0

    for n, item in enumerate(items, 1):
        h, s = item["en_headline"], item["en_summary"]
        row = {"id": item["id"], "en_headline": h, "en_summary": s,
               "te_reference": item["te_good"], "gemini": {}, "grade": None, "notes": ""}
        before = pacer.requests
        for name, (task, tmpl) in CALLS.items():
            resp, secs = pacer.call(provider, args.model, task, tmpl.format(h=h, s=s))
            if resp is None:
                row["gemini"][name] = None
                continue
            row["gemini"][name] = resp.output
            latencies.append(secs)
            tok_in += resp.tokens_in
            tok_out += resp.tokens_out
        row["requests"] = pacer.requests - before
        rows.append(row)
        print(f"[{n}/{len(items)}] {item['id']} requests={row['requests']}", flush=True)

    latencies.sort()
    summary = {
        "model": args.model,
        "stories": len(rows),
        "total_requests": pacer.requests,
        "requests_per_story": round(pacer.requests / max(len(rows), 1), 2),
        "retries_after_failure": pacer.retries_429,
        "failed_calls": sum(v is None for r in rows for v in r["gemini"].values()),
        "latency_p50_s": round(statistics.median(latencies), 2) if latencies else None,
        "latency_p95_s": round(latencies[int(len(latencies) * 0.95) - 1], 2) if latencies else None,
        "tokens_in": tok_in,
        "tokens_out": tok_out,
    }
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"grading sheet: {OUT} (fill `grade` 1-5 and `notes` per row)")


if __name__ == "__main__":
    main()
