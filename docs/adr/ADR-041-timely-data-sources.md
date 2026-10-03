# ADR-041: Timely-data trackers and sources

- **Status**: accepted for visa bulletin and exam/deadline trackers (owner, 2026-10-03); prices/sports/movies still need a permitted feed
- **Date**: 2026-10-03
- **Ticket**: P07

## Context

P07 wants visa-bulletin, exam-result/deadline, price (gold/fuel/stocks) and
sports/movie trackers. These need external data. Non-negotiable: source rights
default `DISABLED` and never bypass the gate; no scraping fallback; AI only via
the gateway; immigration, legal and financial items are always human-reviewed.

## Decision

Each tracker is its own source with its own rights record and is built only
after the owner approves that source. Trackers ingest through the normal
source pipeline (jobs idempotent, observable, bounded retry), publish only
reviewed items for immigration/financial categories, and link back to the
primary source. Order: (1) visa bulletin (official public notice, immigration
review), (2) student exam/deadline reminders from official pages, (3) prices
and sports/movies only if a licensed/permitted feed exists. No tracker ships
on scraped data. Alerts reuse the P02 alert plumbing and daily cap.

## Consequences

Slower, legally safe. Some trackers may never ship if no permitted feed exists.

## Alternatives considered

Scraping aggregators (rejected: rights gate). A single generic tracker
framework first (rejected: premature before one source is approved).
