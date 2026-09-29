import AsyncStorage from "@react-native-async-storage/async-storage";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";
import { HomeScreen } from "../screens/HomeScreen";
import { SavedScreen } from "../screens/SavedScreen";
import { SearchScreen } from "../screens/SearchScreen";
import { StoryCacheProvider } from "../lib/StoryCacheContext";
import { getHome, getSavedStories, search, type StoryOut } from "../lib/api";

jest.mock("@react-navigation/native", () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
  useFocusEffect: (callback: () => void) => require("react").useEffect(callback, [callback]),
}));
jest.mock("../components/StoryCard", () => ({
  StoryCard: ({ story }: { story: StoryOut }) => {
    const { Text } = require("react-native");
    return <Text>{story.variants.en?.headline} {story.status}</Text>;
  },
}));
jest.mock("../lib/api", () => ({
  ...jest.requireActual("../lib/api"),
  getHome: jest.fn(), getSavedStories: jest.fn(), search: jest.fn(), trackEvent: jest.fn(),
}));
const story = (headline: string): StoryOut => ({
  id: "11111111-1111-1111-1111-111111111111", canonical_slug: "example", status: "UPDATED", sensitivity: "NONE", format: "FULL",
  importance: 0.5, published_at: "2026-09-01T12:00:00Z", updated_at: "2026-09-12T12:00:00Z",
  countries: [], topics: [], sources: [], variants: { en: { language: "en", headline, summary: "Summary", qa_status: "PASSED" } },
});

beforeEach(async () => { jest.clearAllMocks(); await AsyncStorage.clear(); });
afterEach(() => { jest.useRealTimers(); });

test("cache publication does not refetch an idle home", async () => {
  jest.mocked(getHome).mockImplementation(async () => ({ top_stories: [story("Fresh response")], topics: [] }));
  await render(<StoryCacheProvider><HomeScreen /></StoryCacheProvider>);
  await screen.findByText("Fresh response UPDATED");
  await act(async () => { await Promise.resolve(); });
  expect(getHome).toHaveBeenCalledTimes(1);
});

test("saved IDs recover after restart and use current server status", async () => {
  await AsyncStorage.setItem("tg_saved_stories_v1", JSON.stringify([story("Saved").id]));
  jest.mocked(getSavedStories).mockResolvedValue([story("Saved")]);
  const first = await render(<StoryCacheProvider><SavedScreen /></StoryCacheProvider>);
  await screen.findByText("Saved UPDATED");
  expect(getSavedStories).toHaveBeenCalledWith([story("Saved").id]);
  await first.unmount();
  await render(<StoryCacheProvider><SavedScreen /></StoryCacheProvider>);
  await screen.findByText("Saved UPDATED");
  expect(getSavedStories).toHaveBeenCalledTimes(2);
});

test("saved network errors retain bookmarks and offer retry", async () => {
  const ids = [story("Saved").id];
  await AsyncStorage.setItem("tg_saved_stories_v1", JSON.stringify(ids));
  jest.mocked(getSavedStories).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce([story("Recovered")]);
  await render(<StoryCacheProvider><SavedScreen /></StoryCacheProvider>);
  await fireEvent.press(await screen.findByText("Try again"));
  await screen.findByText("Recovered UPDATED");
  expect(JSON.parse((await AsyncStorage.getItem("tg_saved_stories_v1"))!)).toEqual(ids);
});

test("late search results cannot replace a newer query or a cleared field", async () => {
  jest.useFakeTimers();
  let first!: (value: Awaited<ReturnType<typeof search>>) => void;
  let second!: (value: Awaited<ReturnType<typeof search>>) => void;
  jest.mocked(search).mockImplementationOnce(() => new Promise((resolve) => { first = resolve; }))
    .mockImplementationOnce(() => new Promise((resolve) => { second = resolve; }));
  await render(<StoryCacheProvider><SearchScreen /></StoryCacheProvider>);
  const input = screen.getByLabelText("Search stories");
  await fireEvent.changeText(input, "first");
  await act(async () => { jest.advanceTimersByTime(350); });
  await fireEvent.changeText(input, "second");
  await act(async () => { jest.advanceTimersByTime(350); });
  await act(async () => { second({ query: "second", items: [story("Second")] }); });
  await screen.findByText("Second UPDATED");
  await act(async () => { first({ query: "first", items: [story("First")] }); });
  expect(screen.queryByText("First UPDATED")).toBeNull();
  expect(screen.getByText("Second UPDATED")).toBeTruthy();
  let pending!: (value: Awaited<ReturnType<typeof search>>) => void;
  jest.mocked(search).mockImplementationOnce(() => new Promise((resolve) => { pending = resolve; }));
  await fireEvent.changeText(input, "third");
  await act(async () => { jest.advanceTimersByTime(350); });
  await fireEvent.changeText(input, "");
  await act(async () => { pending({ query: "third", items: [story("Third")] }); });
  await waitFor(() => expect(screen.getByText("Search for a story.")).toBeTruthy());
  expect(screen.queryByText("Third UPDATED")).toBeNull();
});
