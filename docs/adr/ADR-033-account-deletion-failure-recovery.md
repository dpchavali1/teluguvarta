# ADR-033: Retryable account deletion on network failure

- **Status**: accepted (option A, owner 2026-10-01)
- **Date**: 2026-10-01
- **Ticket**: UI11

## Context

PrivacyScreen currently catches server-deletion failure, clears local data and
forgets the secure device identity, then says the account was deleted. The API
comment deliberately defines local clearing as best effort independent of server
availability. A network failure can therefore leave a server account whose token
is no longer available for retry. UI11 calls for truthful, retryable feedback,
but changing the offline/local deletion contract needs an explicit decision per
NON_NEGOTIABLES #11. No server account creation/privacy architecture is reopened.

## Decision (owner chose A)

A: "Delete account and clear data" must confirm server deletion
before clearing local state/identity. On server failure show an error and retain
identity and local choices so the same request can be retried. On local-clear
failure after confirmed server deletion show that distinction and allow retry.
Make in-flight requests exclusive; only confirmed completion says "deleted".

Alternative B: maintain independent offline local clearing as a separate,
explicitly labelled action, while retaining the old identity securely until a
bounded server-deletion retry completes. This requires durable job/identity
lifecycle rules, not merely a changed label.

## Consequences

A makes completion truthful and retryable with no new infrastructure, but local
clearing through this combined button waits for network availability. B preserves
offline clearing but adds deferred credential storage and retry/expiry policy.
Option A is accepted; option B is not implemented.

## Alternatives considered

Keep swallowing errors and claiming deletion: rejected as misleading.
Forget the token on failure but show a warning: improves wording but loses the
ability to retry server deletion and does not finish UI11's recovery scope.
