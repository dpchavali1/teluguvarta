# ADR-040: Explicit-signal personalization for "My Edit"

- **Status**: accepted (owner, 2026-10-03)
- **Date**: 2026-10-03
- **Ticket**: P05

## Context

ADR-005 keeps ranking deterministic and explainable, keeps preferences
on-device until ADR-006 is accepted, and forbids inferring life stage from
reading behavior (SPEC §3.1). The owner wants a richer "My Edit" feed that
reacts to what the reader does. That is only allowed if it stays inside those
limits.

## Decision

Personalization may use **explicit signals only**: followed topics, places and
keywords; muted topics and sources; saved stories; and "show less like this".
Open/skip counts are **not** used in V1. Signals live on-device (same store as
onboarding preferences) and are applied as bounded, additive terms in the
existing deterministic score, or as a client-side re-order of the server page.
No model call, no randomness, no server-side behavior log. Every re-ranked
story exposes a "why am I seeing this?" reason naming the matching signal.
Persona presets (P01) set explicit choices; they never infer a persona.
Importance never drops below the breaking/immigration/legal/financial floor
because of a mute or a low personal score.

## Consequences

Explainable and private, with no consent flow. Less adaptive than behavioral
ranking. Revisit behavioral signals only after ADR-006 and a consent design.

## Alternatives considered

Behavioral ranking (rejected: breaks ADR-005 and §3.1). Server-side
preference sync (deferred to ADR-006).
