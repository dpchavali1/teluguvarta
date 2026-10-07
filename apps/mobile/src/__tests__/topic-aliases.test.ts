import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  DEFAULT_NOTIFICATION_PREFERENCES,
  getHiddenTopics,
  getNotificationPreferences,
  getProfile,
  remapRetiredTopics,
  setHiddenTopics,
  setNotificationPreferences,
  setProfile,
} from "../lib/storage";

const ALIASES = { tollywood: "entertainment", cinema: "entertainment", crime: "crime-safety" };

beforeEach(() => AsyncStorage.clear());

test("stored selections move onto the canonical topic (ADR-056)", async () => {
  await setNotificationPreferences({
    ...DEFAULT_NOTIFICATION_PREFERENCES,
    topics: { tollywood: false, cinema: true, crime: true, money: true, "local-news": true },
    topicUrgency: { tollywood: "DIGEST", cinema: "INSTANT", crime: "BREAKING_ONLY" },
  });
  await setProfile({ lifeStages: [], interestTopicSlugs: ["tollywood", "cinema", "money"], language: "en" });
  await setHiddenTopics(["crime"]);

  await remapRetiredTopics(ALIASES);

  const prefs = await getNotificationPreferences();
  expect(prefs.topics).toEqual({ entertainment: true, "crime-safety": true, money: true, "local-news": true });
  expect(prefs.topicUrgency).toEqual({ entertainment: "INSTANT", "crime-safety": "BREAKING_ONLY" });
  expect((await getProfile()).interestTopicSlugs).toEqual(["entertainment", "money"]);
  expect(await getHiddenTopics()).toEqual(["crime-safety"]);
});

test("an object-prototype slug is not treated as an alias", async () => {
  await setHiddenTopics(["constructor"]);
  await remapRetiredTopics(ALIASES);
  expect(await getHiddenTopics()).toEqual(["constructor"]);
});
