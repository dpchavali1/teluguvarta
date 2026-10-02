# Two-day app/device check — 2026-10-02

Use the installed Android release app with production URLs. Record the device,
Android version, build/install date, connection type, date/time, and exact
screen whenever an issue appears. This is a manual acceptance record; it does
not replace the T19 security, backup or production performance gates.

| Journey | What to check | Evidence to record |
|---|---|---|
| Reading | Open Latest, a story, Topics, Search and Saved in light and dark mode; switch English/Telugu. | Missing or clipped text, wrong source link, page that fails to recover. |
| Larger text and screen reader | Try 1.5× and 2× system text; use TalkBack through tabs, story, source link, Settings and Alerts. | Clipped controls, unlabeled actions, illogical focus order. |
| Poor network | Open a story, turn on airplane mode, return to the app, then reconnect and retry. | Whether the cached copy is dated, Retry works, and the reading position is retained. |
| Alerts | Search for a topic, turn it on, set quiet hours and daily cap, restart the app, then verify saved values. Test a real push only if the production push service is enabled. | Saved values, permission state, delivery time and whether quiet hours/cap applied. |
| Background/deep link | Open a shared story link, background the app, and return after several minutes. | Correct destination, stale content handling, crash or lost position. |
| Responsiveness | On the same connection, repeat cold open → first visible story and Search → results five times. | Each elapsed time and any outlier; note Wi-Fi/cellular and signal quality. |

For web performance, collect mobile field LCP, INP and CLS when a reliable
source is available. The unauthenticated PageSpeed Insights API returned 429
on 2026-10-02, so no field-data claim is made here. Avoid comparing one local
load to the SPEC's P95 targets.

Please report the first reproducible issue with screen, steps, connection,
theme/language and observed behavior. Do not send credentials, tokens or
private account data in the report.
