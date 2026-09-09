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

/**
 * S2 (docs/tickets/S2.md) / §3.1's student topic taxonomy. These are plain
 * `Topic` rows in the database (same table/API as every other topic — see
 * `infra/scripts/seed.py`'s `STUDENT_SEED_TOPICS`, which must stay in sync
 * with the slugs here) so they flow through the existing ranking/
 * notification code unchanged; this list exists only so onboarding/settings
 * UI can group them separately from general topics. §3.1 also lists
 * "travel" as a student topic, but that's the same topic as the general
 * "Travel" interest, not a duplicate row, so it's deliberately left out of
 * this list (it already renders in the general group).
 */
export const STUDENT_TOPIC_SLUGS = [
  "f1",
  "cpt",
  "opt",
  "stem-opt",
  "h1b-transition",
  "internships",
  "university-policy",
  "campus-safety",
  "taxes",
  "housing",
  "scholarships",
  "student-community",
  "international-student-jobs",
] as const;
