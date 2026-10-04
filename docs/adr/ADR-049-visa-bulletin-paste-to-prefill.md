# ADR-049 — Visa bulletin: paste-to-prefill (manual entry stays)

Status: accepted (owner, 2026-10-04: "proceed with manual update")

## Context
travel.state.gov returns a Cloudflare 403 to automated requests, including the
bulletin PDF (checked once, plain request, 2026-10-04). ADR-041 therefore has
editors enter each month by hand. Third-party aggregators and scraper repos are
rejected (rights gate, no scraping fallback, immigration data needs an official source).

## Decision
No fetching. An editor opens the official bulletin in a browser, copies its text
and pastes it into admin. `POST /v1/admin/visa-bulletins/parse` (read-only, saves
nothing) turns the text into the same entries the existing form takes, plus warnings
for any missing row. The editor checks them against the PDF, adds the source link,
saves a DRAFT and approves as before (separation of duties unchanged).

Only the 5 country columns for F1–F4/F2A/F2B and EB1–EB4, EB3 Other Workers and
EB5 Unreserved are read. Certain Religious Workers and the 5th set-aside rows are
not tracked categories and are skipped.

## Consequences
- Parser is tested against the real October 2026 bulletin text; a layout change
  yields warnings, never guessed values.
- Possible later: email-notification trigger, or a parser if the State Department
  permits automated access (ADR-041).
