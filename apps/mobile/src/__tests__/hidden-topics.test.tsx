import AsyncStorage from "@react-native-async-storage/async-storage";
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";

import { PagedStoryList } from "../components/PagedStoryList";
import { getHome, type StoryOut } from "../lib/api";
import { HiddenTopicsProvider } from "../lib/HiddenTopicsContext";
import { StoryCacheProvider } from "../lib/StoryCacheContext";
import { LOCAL_DATA_KEYS, getHiddenTopics, setHiddenTopics } from "../lib/storage";
import { HiddenTopicsScreen } from "../screens/HiddenTopicsScreen";
import { HomeScreen } from "../screens/HomeScreen";
import { PrivacyScreen } from "../screens/PrivacyScreen";

jest.mock("@react-navigation/native", () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
  useFocusEffect: (callback: () => void) => require("react").useEffect(callback, [callback]),
}));
jest.mock("../lib/api", () => ({
  ...jest.requireActual("../lib/api"),
  getHome: jest.fn(),
  deleteAccount: jest.fn(async () => undefined),
  trackEvent: jest.fn(),
}));
jest.mock("../lib/identity", () => ({ resetClientToken: jest.fn(async () => undefined) }));

const story = (id: string, headline: string, topics: string[]): StoryOut => ({
  id, canonical_slug: id, status: "PUBLISHED", sensitivity: "NONE", format: "FULL",
  importance: 0.5, published_at: "2026-09-01T12:00:00Z", updated_at: "2026-09-01T12:00:00Z",
  countries: [], topics, sources: [],
  variants: { en: { language: "en", headline, summary: `${headline} summary`, qa_status: "PASSED" } },
});
const lead = story("a", "Budget passed", ["politics"]);
const film = story("b", "Film release", ["entertainment"]);
const both = story("c", "Actor runs for office", ["politics", "entertainment"]);

function withProviders(children: React.ReactNode) {
  return (
    <StoryCacheProvider>
      <HiddenTopicsProvider>{children}</HiddenTopicsProvider>
    </StoryCacheProvider>
  );
}

beforeEach(async () => {
  jest.clearAllMocks();
  await AsyncStorage.clear();
  jest.mocked(getHome).mockResolvedValue({
    top_stories: [lead, film, both],
    topics: [
      { slug: "politics", name: "Politics", story_count: 2 },
      { slug: "entertainment", name: "Entertainment", story_count: 2 },
    ] as never,
  });
});

test("hidden topics default to none, ignore junk, and are cleared with the other data", async () => {
  expect(await getHiddenTopics()).toEqual([]);
  await setHiddenTopics(["politics"]);
  expect(await getHiddenTopics()).toEqual(["politics"]);
  await AsyncStorage.setItem("tg_hidden_topics_v1", '{"politics":true}');
  expect(await getHiddenTopics()).toEqual([]);
  expect(LOCAL_DATA_KEYS).toContain("tg_hidden_topics_v1");
});

test("'Show less' on a Home card hides every story and chip from that topic, and it persists", async () => {
  await render(withProviders(<HomeScreen />));
  await screen.findByText("Film release");

  await fireEvent.press(screen.getByLabelText("Show less like: Film release"));
  await fireEvent.press(screen.getByLabelText("Hide stories about Entertainment"));

  await waitFor(() => expect(screen.queryByText("Film release")).toBeNull());
  // Any hidden tag is enough, even alongside a topic the reader still follows.
  expect(screen.queryByText("Actor runs for office")).toBeNull();
  expect(screen.getByText("Budget passed")).toBeTruthy();
  expect(screen.queryByLabelText("Browse topic: Entertainment")).toBeNull();
  expect(screen.getByLabelText("Browse topic: Politics")).toBeTruthy();
  await waitFor(async () => expect(await getHiddenTopics()).toEqual(["entertainment"]));
});

test("Home says why it's empty when every story is hidden", async () => {
  await setHiddenTopics(["politics", "entertainment"]);
  await render(withProviders(<HomeScreen />));
  expect(await screen.findByText(/all from topics or sources you've hidden/)).toBeTruthy();
});

test("Latest filters and offers 'Show less'; a Topic list does neither", async () => {
  await setHiddenTopics(["entertainment"]);
  const fetchPage = jest.fn(async () => ({ stories: [lead, film] }));
  const latest = await render(
    withProviders(<PagedStoryList fetchPage={fetchPage} loadingLabel="l" errorLabel="e" emptyLabel="none" respectHiddenTopics />),
  );
  await screen.findByText("Budget passed");
  await waitFor(() => expect(screen.queryByText("Film release")).toBeNull());
  expect(screen.getByLabelText("Show less like: Budget passed")).toBeTruthy();
  await latest.unmount();

  await render(withProviders(<PagedStoryList fetchPage={fetchPage} loadingLabel="l" errorLabel="e" emptyLabel="none" />));
  expect(await screen.findByText("Film release")).toBeTruthy();
  expect(screen.queryByLabelText(/Show less like/)).toBeNull();
});

test("Settings → Hidden topics brings a topic back to Home", async () => {
  await setHiddenTopics(["entertainment"]);
  await render(
    withProviders(
      <>
        <HiddenTopicsScreen />
        <HomeScreen />
      </>,
    ),
  );
  await screen.findByText("Budget passed");
  await waitFor(() => expect(screen.queryByText("Film release")).toBeNull());

  await fireEvent.press(screen.getByLabelText("Show stories about Entertainment again"));

  expect(await screen.findByText("Film release")).toBeTruthy();
  expect(screen.getByText(/No hidden topics/)).toBeTruthy();
  await waitFor(async () => expect(await getHiddenTopics()).toEqual([]));
});

test("clearing data shows hidden topics again", async () => {
  await setHiddenTopics(["entertainment"]);
  await render(
    withProviders(
      <>
        <PrivacyScreen />
        <HiddenTopicsScreen />
      </>,
    ),
  );
  await screen.findByLabelText("Show stories about Entertainment again");

  await fireEvent.press(screen.getByLabelText("Delete account and clear all data on this device"));

  expect(await screen.findByText(/No hidden topics/)).toBeTruthy();
  expect(await AsyncStorage.getItem("tg_hidden_topics_v1")).toBeNull();
});
