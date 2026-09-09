"""T19 §18 golden AI regression set. See eval/README.md for what this
proves (the deterministic QA/glossary harness catches what this corpus
expects it to) and what it doesn't (no live provider call — this sandbox
has never had one, same limitation every AI-gateway ticket since T10
documented). Parametrized per fixture so one bad item fails one test case,
not the whole module.
"""

import pytest

from eval.run_golden_eval import evaluate_item, load_items

ITEMS = load_items()


@pytest.mark.parametrize("item", ITEMS, ids=[i["id"] for i in ITEMS])
def test_golden_fixture(item):
    failures = evaluate_item(item)
    assert not failures, "; ".join(failures)


def test_golden_set_covers_every_18_category():
    categories = {item["category"] for item in ITEMS}
    expected = {
        "politics", "money", "immigration", "entertainment", "ap",
        "telangana", "us", "common_names", "numbers", "multilingual",
    }
    assert categories == expected
