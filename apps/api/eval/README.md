# Golden AI regression set (T19 §18)

`golden_set.json` is a corpus of representative English source
headlines/summaries, each with a hand-written *good* Telugu rendering (must
pass `app/content/qa.py`) and a deliberately broken *bad* one (must fail
it) — spanning every category §18 lists (politics, money, immigration,
entertainment, AP, Telangana, US, common names, numbers, multilingual).

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

30 items (3 per category), well below §18's ">=300 representative
stories". Growing it to 300 real, individually-considered examples is
editorial/content work, not something to fabricate wholesale in one
session — treat this as the harness plus a real starting corpus, not the
finished set. Extend `golden_set.json` following the existing shape; no
code changes are needed for the harness to pick up new items.

## Running it

```
apps/api/.venv/bin/pytest apps/api/tests/test_golden_eval.py -v
```

or directly:

```
apps/api/.venv/bin/python apps/api/eval/run_golden_eval.py
```
