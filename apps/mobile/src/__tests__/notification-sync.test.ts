import { DEFAULT_NOTIFICATION_PREFERENCES } from "../lib/storage";

const mockUpdatePreferences = jest.fn().mockResolvedValue({});
jest.mock("../lib/api", () => ({ updatePreferences: (b: unknown) => mockUpdatePreferences(b) }));
jest.mock("../lib/storage", () => ({
  ...jest.requireActual("../lib/storage"),
  getSavedIds: jest.fn().mockResolvedValue(["s1", "s2"]),
  getFollowedPlaces: jest.fn().mockResolvedValue([{ placeId: "IN-TG-warangal", alerts: true }]),
}));

import { syncToServer } from "../lib/notificationSync";

const prefs = {
  ...DEFAULT_NOTIFICATION_PREFERENCES,
  topics: { money: true, jobs: false },
  topicUrgency: { money: "DIGEST" as const },
  keywords: ["h-1b"],
  digestMorningHour: 7,
  residenceTz: "America/Chicago",
};

test("sends urgency, keywords, digest, zones and saved ids", async () => {
  await syncToServer(prefs);
  expect(mockUpdatePreferences).toHaveBeenLastCalledWith(expect.objectContaining({
    topic_slugs: ["money"],
    topic_urgency: { money: "DIGEST" },
    keywords: ["h-1b"],
    digest_morning_hour: 7,
    residence_tz: "America/Chicago",
    saved_story_ids: ["s1", "s2"],
    follow_places: [{ place_id: "IN-TG-warangal", alerts: true }],
  }));
});

test("disable-all clears keywords, digests and saved ids", async () => {
  await syncToServer({ ...prefs, disableAll: true });
  expect(mockUpdatePreferences).toHaveBeenLastCalledWith(expect.objectContaining({
    topic_slugs: [], keywords: [], digest_morning_hour: null, saved_story_ids: [], follow_places: [], breaking_alerts_enabled: false,
  }));
});
