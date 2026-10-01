import AsyncStorage from "@react-native-async-storage/async-storage";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";
import { Linking, StyleSheet } from "react-native";

import { StoryCard } from "../components/StoryCard";
import { getSavedStories, getStory, type StoryOut } from "../lib/api";
import { HiddenTopicsProvider } from "../lib/HiddenTopicsContext";
import { StoryCacheProvider, useStoryCache } from "../lib/StoryCacheContext";
import { LOCAL_DATA_KEYS, READ_HISTORY_LIMIT, getReadIds, setReadIds } from "../lib/storage";
import { PrivacyScreen } from "../screens/PrivacyScreen";
import { SavedScreen } from "../screens/SavedScreen";
import { StoryDetailScreen } from "../screens/StoryDetailScreen";
import { colors } from "../theme/tokens";

jest.mock("@react-navigation/native", () => ({
  useNavigation: () => ({ navigate: jest.fn(), setOptions: jest.fn() }),
  useFocusEffect: (callback: () => void) => require("react").useEffect(callback, [callback]),
}));
jest.mock("../lib/api", () => ({
  ...jest.requireActual("../lib/api"),
  getStory: jest.fn(),
  getSavedStories: jest.fn(),
  deleteAccount: jest.fn(async () => undefined),
  trackEvent: jest.fn(),
}));
jest.mock("../lib/identity", () => ({ resetClientToken: jest.fn(async () => undefined) }));

const story = (id: string, headline: string): StoryOut => ({
  id, canonical_slug: id, status: "PUBLISHED", sensitivity: "NONE", format: "FULL",
  importance: 0.5, published_at: "2026-09-01T12:00:00Z", updated_at: "2026-09-01T12:00:00Z",
  countries: [], topics: [], sources: [],
  variants: { en: { language: "en", headline, summary: `${headline} summary`, qa_status: "PASSED" } },
});
const first = story("a", "Budget passed");
const second = story("b", "Film release");

function withProviders(children: React.ReactNode) {
  return (
    <StoryCacheProvider>
      <HiddenTopicsProvider>{children}</HiddenTopicsProvider>
    </StoryCacheProvider>
  );
}
const feedCard = (s: StoryOut) => <StoryCard story={s} onOpen={() => {}} onOpenSource={() => {}} />;
const detail = (slug: string) => <StoryDetailScreen {...({ route: { params: { slug } } } as any)} />;
const headlineColor = (text: string) => StyleSheet.flatten(screen.getAllByText(text)[0].props.style).color; // [0]: the feed card, not the detail page

beforeEach(async () => {
  jest.clearAllMocks();
  await AsyncStorage.clear();
  jest.mocked(getSavedStories).mockImplementation(async (ids) =>
    ids.map((id) => [first, second].find((s) => s.id === id)).filter((s): s is StoryOut => Boolean(s)),
  );
  jest.spyOn(Linking, "openURL").mockResolvedValue(true);
});

test("read history defaults to empty, ignores junk, caps, and is cleared with the other data", async () => {
  expect(await getReadIds()).toEqual([]);
  await AsyncStorage.setItem("tg_read_history_v1", '"a"');
  expect(await getReadIds()).toEqual([]);
  await setReadIds(Array.from({ length: READ_HISTORY_LIMIT + 5 }, (_, i) => `id${i}`));
  expect(await getReadIds()).toHaveLength(READ_HISTORY_LIMIT);
  expect(LOCAL_DATA_KEYS).toContain("tg_read_history_v1");
});

test("opening a story marks its feed card read, and that survives a restart", async () => {
  jest.mocked(getStory).mockResolvedValue(first);
  const app = await render(withProviders(<>{feedCard(first)}{feedCard(second)}{detail("a")}</>));

  await waitFor(() => expect(headlineColor("Budget passed")).toBe(colors.muted));
  expect(screen.getAllByLabelText("Open story: Budget passed")[0].props.accessibilityHint).toBe("You've read this story");
  expect(headlineColor("Film release")).toBe(colors.text);
  await waitFor(async () => expect(await getReadIds()).toEqual(["a"]));

  await app.unmount();
  await render(withProviders(<>{feedCard(first)}</>));
  await waitFor(() => expect(headlineColor("Budget passed")).toBe(colors.muted));
});

test("the most recent read moves to the top and the list stays capped", async () => {
  await setReadIds(Array.from({ length: READ_HISTORY_LIMIT }, (_, i) => `id${i}`));
  let markRead!: (id: string) => void;
  function Probe() {
    markRead = useStoryCache().markRead;
    return null;
  }
  await render(withProviders(<Probe />));
  await act(async () => markRead("id5"));
  await act(async () => markRead("new"));
  const ids = await getReadIds();
  expect(ids.slice(0, 2)).toEqual(["new", "id5"]);
  expect(ids).toHaveLength(READ_HISTORY_LIMIT);
  expect(ids).not.toContain(`id${READ_HISTORY_LIMIT - 1}`);
});

test("Saved → Recently read lists opened stories newest first, and can be cleared", async () => {
  await setReadIds(["b", "a"]);
  await render(withProviders(<SavedScreen />));
  expect(await screen.findByRole("radio", { name: "Saved" })).toBeChecked();

  await fireEvent.press(screen.getByRole("radio", { name: "Recently read" }));

  await screen.findByText("Film release");
  expect(getSavedStories).toHaveBeenLastCalledWith(["b", "a"]);
  expect(screen.getByText("Budget passed")).toBeTruthy();

  await fireEvent.press(screen.getByText("Clear reading history"));

  expect(await screen.findByText(/Stories you open show up here/)).toBeTruthy();
  expect(await getReadIds()).toEqual([]);
});

test("clearing data empties Recently read in the running app", async () => {
  await setReadIds(["a"]);
  await render(withProviders(<><PrivacyScreen />{feedCard(first)}</>));
  await waitFor(() => expect(headlineColor("Budget passed")).toBe(colors.muted));

  await fireEvent.press(screen.getByLabelText("Delete account and clear all data on this device"));

  await waitFor(() => expect(headlineColor("Budget passed")).toBe(colors.text));
  expect(await AsyncStorage.getItem("tg_read_history_v1")).toBeNull();
});

test("Recently read doesn't mute its own headlines", async () => {
  await setReadIds(["a"]);
  await render(withProviders(<SavedScreen />));
  await fireEvent.press(await screen.findByRole("radio", { name: "Recently read" }));
  await screen.findByText("Budget passed");
  expect(headlineColor("Budget passed")).toBe(colors.text);
});
