# Golden AI regression set (T19 §18)

`golden_set.json` is a corpus of representative English source
headlines/summaries, each with a *good* Telugu rendering (must pass
`app/content/qa.py`) and a deliberately broken *bad* one (must fail it) —
spanning every category §18 lists (politics, money, immigration,
entertainment, AP, Telangana, US, common names, numbers, multilingual).
Every item is hand-written and human-reviewed — see "Corpus size" below.

## What this proves, and what it doesn't

`run_golden_eval.py` (wired into `tests/test_golden_eval.py`, runs in CI on
every push, no network/provider key needed) checks the **deterministic**
parts of the bilingual pipeline against this corpus:

- every "good" Telugu rendering passes `qa.find_qa_issues` (no false
  positives in the QA harness),
- every "bad" rendering — with exactly one invariant (a number, date,
  currency amount, URL, or negation) removed — is caught,
- every glossary-relevant entity's canonical Telugu spelling
  (`app/content/glossary.py`) survives `apply_glossary` even starting from
  a naive/untranslated rendering.

This is a real regression suite: it fails the moment `qa.py` or
`glossary.py` change in a way that stops catching what this corpus expects
them to catch — which is the actual value of "run on every prompt or model
change" for the parts of this pipeline that aren't a live model call.

**What it does not do**, and why: it does not call a real AI provider.
Every AI-gateway ticket since T10 has documented the same sandbox
limitation (no outbound network/provider key here) — this eval inherits
it. `expected_sensitivity`/`expected_entities` on each item describe what a
*correctly behaving* classification call should produce for that input;
nothing here currently drives a live classification call and diffs its
output against those fields, because there is no live call to make in this
environment. Wiring that comparison in is a straight extension once a real
provider key exists (loop `golden_set.json` through
`AiGateway.run_task(Task.RELEVANCE_CATEGORIZATION, ...)` with a real
provider and assert `result.sensitivity`/`result.entities` against the
fixture) — tracked as a follow-up, not attempted blind against a
`FakeProvider` that would just echo the expected answer back and prove
nothing.

## Corpus size

30 items (3 per category), meeting §18's "≥30 human-reviewed
representative stories" bar — a single tier, all hand-written and
human-reviewed, listed in full in `_meta.human_reviewed_ids` in
`golden_set.json`.

A 270-item bulk-generated expansion (product-owner-approved 2026-09-09,
after the 50-100-user pilot requirement was waived and full development
resumed — see PROGRESS.md) existed from 2026-09-09 through 2026-09-16. It
was mechanically verified to pass/fail `qa.find_qa_issues`/`apply_glossary`
exactly as this harness expects, but the English news copy and Telugu
translations themselves never had a native-Telugu-speaker or editorial
review. Per **ADR-013** (accepted 2026-09-16), it has been removed rather
than kept as unverified filler — a small honest set beats a large
fictional one. See
`docs/adr/ADR-013-golden-eval-set-trust-tier.md` for the full reasoning.

Growing this set past 30 requires the same bar every time: each new item
is native-Telugu-speaker reviewed *before* it's committed, added to
`_meta.human_reviewed_ids`, and only then counted toward the total. No
tooling/process for that review exists yet (ADR-013 doesn't propose one) —
just the rule that unreviewed items don't count. Extend `golden_set.json`
following the existing shape once that review has happened; no code
changes are needed for the harness to pick up new items.

## Running it

```
apps/api/.venv/bin/pytest apps/api/tests/test_golden_eval.py -v
```

or directly:

```
apps/api/.venv/bin/python apps/api/eval/run_golden_eval.py
```
