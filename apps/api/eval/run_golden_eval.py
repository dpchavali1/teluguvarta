#!/usr/bin/env python3
"""T19 §18 golden AI regression set — CLI runner. See eval/README.md for
what this does and doesn't prove. `tests/test_golden_eval.py` runs the same
checks per-fixture under pytest (parametrized, so a single bad fixture
fails one test case, not the whole suite) — this script is the
human-readable "run the whole corpus and print a summary" entry point.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.content.glossary import GLOSSARY_EN_TE, apply_glossary
from app.content.qa import find_qa_issues

GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_set.json"


def load_items() -> list[dict]:
    return json.loads(GOLDEN_SET_PATH.read_text())["items"]


def evaluate_item(item: dict) -> list[str]:
    """Returns a list of failure descriptions; empty means the item passed
    every deterministic check this eval runs (see eval/README.md)."""
    failures: list[str] = []

    good_issues = find_qa_issues(item["en_summary"], item["te_good"])
    if good_issues:
        failures.append(f"'te_good' unexpectedly failed QA: {good_issues}")

    bad_issues = find_qa_issues(item["en_summary"], item["te_bad"])
    if not bad_issues:
        failures.append("'te_bad' unexpectedly passed QA — the QA harness would miss this regression")

    en_full_text = f"{item['en_headline']} {item['en_summary']}"
    for entity in item.get("expected_entities", []):
        if entity not in GLOSSARY_EN_TE:
            continue
        canonical = GLOSSARY_EN_TE[entity].canonical_te
        if canonical not in item["te_good"]:
            # This fixture's Telugu rendering never restates the entity by
            # name (natural — not every sentence repeats the country/org
            # name) — nothing to test the glossary correction against here.
            continue
        naive = GLOSSARY_EN_TE[entity].naive_variants[0] if GLOSSARY_EN_TE[entity].naive_variants else entity
        corrected = apply_glossary(en_full_text, item["te_good"].replace(canonical, naive))
        if canonical not in corrected:
            failures.append(f"glossary correction failed to restore canonical spelling of '{entity}'")

    return failures


def main() -> int:
    items = load_items()
    failed = 0
    for item in items:
        failures = evaluate_item(item)
        if failures:
            failed += 1
            print(f"FAIL {item['id']} ({item['category']}):")
            for f in failures:
                print(f"     - {f}")
        else:
            print(f"OK   {item['id']} ({item['category']})")

    print(f"\n{len(items) - failed}/{len(items)} passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
