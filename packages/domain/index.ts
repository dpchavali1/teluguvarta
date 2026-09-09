/**
 * §17's core analytics event list — the single source of truth so
 * apps/web, apps/admin, and apps/mobile's analytics clients (and the T18
 * smoke test) all reference the same event names instead of each
 * hand-typing a copy that can drift.
 */
export const ANALYTICS_EVENTS = [
  "app_open",
  "feed_view",
  "story_open",
  "story_save",
  "story_share",
  "language_switch",
  "search",
  "notification_open",
  "notification_opt_in",
  "onboarding_complete",
  "account_delete_request",
  "report_issue",
] as const;

export type AnalyticsEvent = (typeof ANALYTICS_EVENTS)[number];
