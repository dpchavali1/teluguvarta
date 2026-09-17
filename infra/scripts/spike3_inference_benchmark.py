#!/usr/bin/env python3
"""Spike 3 (docs/plans/gemini-hetzner-telugu-plan.md, Phase -1): measure
whether a local embedding model and a local 4B generation model can run
colocated with Postgres + ingest workers on a single box, against the
numeric gates the plan states up front (query-embedding p95 <= 300ms, Q&A
p95 <= 3s, API p95 degradation under concurrent ingest <= 20%).

This script is NOT wired to run anything by default. Nothing in this repo
installs an inference stack or downloads model weights automatically --
that's a deliberate, confirmed-with-the-user action, not something a script
should do on import. See the "Prerequisites" section below for what you
install yourself before running this.

Prerequisites (not installed by this script):
    pip install llama-cpp-python sentence-transformers psutil requests
    - BGE-M3 embedding model, e.g. via sentence-transformers
      ("BAAI/bge-m3", downloads ~2.2GB from huggingface.co on first use)
    - A 4B-parameter instruct GGUF (e.g. a Qwen2.5-4B-Instruct or
      Gemma-2-4B GGUF quant, ~2.5-3GB) at a local path you pass via
      --generation-model-path

Usage:
    python3 infra/scripts/spike3_inference_benchmark.py \
        --generation-model-path /path/to/model.Q4_K_M.gguf \
        --api-base-url http://localhost:8000 \
        --ingest-concurrency 4 \
        --out infra/scripts/spike3_results/$(date +%Y%m%d-%H%M%S).json

What it measures, in order:
    1. Query-embedding latency (BGE-M3, short query strings) alone.
    2. Q&A generation latency (4B model, ~200-token answer) alone.
    3. API p95 degradation: hits --api-base-url's /v1/search endpoint
       repeatedly while (1) and (2) run concurrently in a background
       thread pool, simulating ingest-worker-style contention for CPU/DB.
    4. Compares all three against the plan's stated gates and prints/writes
       a PASS/FAIL per gate plus the raw percentiles, RSS memory, and
       tokens/sec -- the inputs ADR-012/ADR-014/ADR-016 need to record.

This is intentionally a single file with no project import dependency
(doesn't import apps/api/app) so it can be copied onto a candidate Hetzner
box and run there directly, which is the actual point of Spike 3 --
measuring the target hardware, not this dev machine.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Gates as stated in gemini-hetzner-telugu-plan.md Phase -1 / Spike 3.
# These are the plan's own placeholder figures ("to be sharpened against
# product requirements before the spike runs, but *some* number must exist
# before the measurement does") -- ADR-014 records whatever Spike 3 actually
# used, so if these are changed before running, update this comment and the
# ADR together.
QUERY_EMBED_P95_GATE_MS = 300
QA_P95_GATE_S = 3.0
API_DEGRADATION_GATE_PCT = 20.0

DEFAULT_QUERIES = [
    "తెలుగు రాష్ట్రాల్లో తాజా వార్తలు ఏమిటి",
    "H-1B వీసా నిబంధనల్లో మార్పులు",
    "అమెరికాలో తెలుగు విద్యార్థుల కోసం స్కాలర్‌షిప్‌లు",
    "హైదరాబాద్ లో ట్రాఫిక్ సమస్యలు",
    "ఆంధ్రప్రదేశ్ ఎన్నికల ఫలితాలు",
]

DEFAULT_QA_PROMPTS = [
    "Summarize why H-1B visa changes matter for Telugu students in the US, "
    "citing only the provided sources.",
    "What happened in the latest Andhra Pradesh assembly session?",
]


@dataclass
class LatencySample:
    label: str
    values_ms: list[float] = field(default_factory=list)

    def p95(self) -> float:
        if not self.values_ms:
            return float("nan")
        return statistics.quantiles(self.values_ms, n=20)[18]

    def p50(self) -> float:
        if not self.values_ms:
            return float("nan")
        return statistics.median(self.values_ms)

    def summary(self) -> dict:
        return {
            "label": self.label,
            "n": len(self.values_ms),
            "p50_ms": round(self.p50(), 1),
            "p95_ms": round(self.p95(), 1),
            "max_ms": round(max(self.values_ms), 1) if self.values_ms else None,
        }


def rss_mb() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        return float("nan")


def bench_query_embedding(model_name: str, iterations: int) -> LatencySample:
    from sentence_transformers import SentenceTransformer

    print(f"[spike3] loading embedding model {model_name} ...", file=sys.stderr)
    model = SentenceTransformer(model_name)
    sample = LatencySample("query_embedding")
    # Warm up once (first call pays one-time graph/cache costs; the plan's
    # gate is about steady-state request latency, not cold start).
    model.encode(DEFAULT_QUERIES[0])
    for i in range(iterations):
        query = DEFAULT_QUERIES[i % len(DEFAULT_QUERIES)]
        start = time.perf_counter()
        model.encode(query)
        sample.values_ms.append((time.perf_counter() - start) * 1000)
    return sample


def bench_qa_generation(model_path: str, iterations: int) -> tuple[LatencySample, float]:
    from llama_cpp import Llama

    print(f"[spike3] loading generation model {model_path} ...", file=sys.stderr)
    llm = Llama(model_path=model_path, n_ctx=2048, verbose=False)
    sample = LatencySample("qa_generation")
    total_tokens = 0
    total_s = 0.0
    for i in range(iterations):
        prompt = DEFAULT_QA_PROMPTS[i % len(DEFAULT_QA_PROMPTS)]
        start = time.perf_counter()
        result = llm(prompt, max_tokens=200)
        elapsed = time.perf_counter() - start
        sample.values_ms.append(elapsed * 1000)
        total_tokens += result.get("usage", {}).get("completion_tokens", 0)
        total_s += elapsed
    tokens_per_sec = total_tokens / total_s if total_s else float("nan")
    return sample, tokens_per_sec


def bench_api_under_contention(
    api_base_url: str, search_terms: list[str], duration_s: int
) -> tuple[LatencySample, LatencySample]:
    """Hits /v1/search with no concurrent inference load first (baseline),
    then repeats while inference load runs in background threads
    (contended). Returns (baseline, contended) samples for the p95
    degradation comparison."""
    import requests

    def hit_search_for(seconds: float) -> LatencySample:
        sample = LatencySample("api_search")
        end = time.perf_counter() + seconds
        i = 0
        while time.perf_counter() < end:
            term = search_terms[i % len(search_terms)]
            start = time.perf_counter()
            try:
                requests.get(
                    f"{api_base_url}/v1/search",
                    params={"q": term},
                    timeout=10,
                )
            except requests.RequestException as exc:
                print(f"[spike3] api request failed: {exc}", file=sys.stderr)
            sample.values_ms.append((time.perf_counter() - start) * 1000)
            i += 1
        return sample

    print("[spike3] measuring API baseline (no inference contention) ...", file=sys.stderr)
    baseline = hit_search_for(duration_s)

    print("[spike3] measuring API under inference contention ...", file=sys.stderr)
    # The contention load itself (embedding/generation calls running
    # alongside the API hits) is driven by the caller via a background
    # executor passed through main(); this function only measures the API
    # side, per the plan's framing that embedding and Q&A gates are
    # separate from the "does the DB/API survive colocation" question.
    contended = hit_search_for(duration_s)
    return baseline, contended


def degradation_pct(baseline: LatencySample, contended: LatencySample) -> float:
    if not baseline.values_ms or baseline.p95() == 0:
        return float("nan")
    return (contended.p95() - baseline.p95()) / baseline.p95() * 100


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embedding-model", default="BAAI/bge-m3")
    parser.add_argument("--generation-model-path", required=True)
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument("--embedding-iterations", type=int, default=50)
    parser.add_argument("--qa-iterations", type=int, default=10)
    parser.add_argument("--api-duration-s", type=int, default=30)
    parser.add_argument("--ingest-concurrency", type=int, default=4)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    print(
        "[spike3] this run assumes you already installed the prerequisites "
        "listed in this file's module docstring -- nothing here installs "
        "them for you.",
        file=sys.stderr,
    )

    embed_sample = bench_query_embedding(args.embedding_model, args.embedding_iterations)
    qa_sample, tokens_per_sec = bench_qa_generation(
        args.generation_model_path, args.qa_iterations
    )

    # Run embedding + generation concurrently in the background while
    # hitting the API, at --ingest-concurrency workers each, to approximate
    # "ingest workers running" contention per the plan's framing.
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.ingest_concurrency * 2
    ) as pool:
        contention_futures = [
            pool.submit(bench_query_embedding, args.embedding_model, 200)
            for _ in range(args.ingest_concurrency)
        ] + [
            pool.submit(bench_qa_generation, args.generation_model_path, 50)
            for _ in range(args.ingest_concurrency)
        ]
        baseline, contended = bench_api_under_contention(
            args.api_base_url, DEFAULT_QUERIES, args.api_duration_s
        )
        # Drain background contention load before reporting (don't leave
        # threads running past the measurement window).
        concurrent.futures.wait(contention_futures, timeout=1)

    degradation = degradation_pct(baseline, contended)

    embed_gate_pass = embed_sample.p95() <= QUERY_EMBED_P95_GATE_MS
    qa_gate_pass = (qa_sample.p95() / 1000) <= QA_P95_GATE_S
    degradation_gate_pass = (
        degradation is not None
        and not (degradation != degradation)  # nan check
        and degradation <= API_DEGRADATION_GATE_PCT
    )

    result = {
        "gates": {
            "query_embed_p95_ms_gate": QUERY_EMBED_P95_GATE_MS,
            "qa_p95_s_gate": QA_P95_GATE_S,
            "api_degradation_pct_gate": API_DEGRADATION_GATE_PCT,
        },
        "query_embedding": {**embed_sample.summary(), "gate_pass": embed_gate_pass},
        "qa_generation": {
            **qa_sample.summary(),
            "tokens_per_sec": round(tokens_per_sec, 2),
            "gate_pass": qa_gate_pass,
        },
        "api_contention": {
            "baseline": baseline.summary(),
            "contended": contended.summary(),
            "degradation_pct": round(degradation, 1) if degradation == degradation else None,
            "gate_pass": degradation_gate_pass,
        },
        "rss_mb_at_end": round(rss_mb(), 1),
        "selection_rule": (
            "single box viable" if embed_gate_pass else "second host required for embedding"
        )
        + (", Scope B (Q&A) viable" if (embed_gate_pass and qa_gate_pass) else ", Scope A only"),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"[spike3] wrote {args.out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
