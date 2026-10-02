import AsyncStorage from "@react-native-async-storage/async-storage";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";
import { AppState, type AppStateStatus } from "react-native";
import { HOME_STALE_MS, HomeScreen } from "../screens/HomeScreen";
import { LatestScreen } from "../screens/LatestScreen";
import { SavedScreen } from "../screens/SavedScreen";
import { SearchScreen } from "../screens/SearchScreen";
import { StoryDetailScreen } from "../screens/StoryDetailScreen";
import { StoryCacheProvider, useStoryCache } from "../lib/StoryCacheContext";
import { ApiNetworkError, ApiNotFoundError, getHome, getSavedStories, getStory, listStories, search, type StoryOut } from "../lib/api";

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
  getHome: jest.fn(), getSavedStories: jest.fn(), getStory: jest.fn(), listStories: jest.fn(), search: jest.fn(), trackEvent: jest.fn(),
}));
const story = (headline: string): StoryOut => ({
  id: "11111111-1111-1111-1111-111111111111", canonical_slug: "example", status: "UPDATED", sensitivity: "NONE", format: "FULL",
  importance: 0.5, published_at: "2026-09-01T12:00:00Z", updated_at: "2026-09-12T12:00:00Z",
  countries: [], topics: [], sources: [], variants: { en: { language: "en", headline, summary: "Summary", qa_status: "PASSED" } },
});

beforeEach(async () => { jest.clearAllMocks(); jest.mocked(search).mockReset(); await AsyncStorage.clear(); });
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

test("search appends pages, updates duplicate IDs, and prevents duplicate paging requests", async () => {
  jest.useFakeTimers();
  let finish!: (value: Awaited<ReturnType<typeof search>>) => void;
  const older = { ...story("Older search"), id: "22222222-2222-2222-2222-222222222222" };
  jest.mocked(search).mockResolvedValueOnce({ query: "news", items: [story("First search")], next_cursor: "c1" })
    .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
  await render(<StoryCacheProvider><SearchScreen /></StoryCacheProvider>);
  await fireEvent.changeText(screen.getByLabelText("Search stories"), "news");
  await act(async () => { jest.advanceTimersByTime(350); });
  await screen.findByText("First search UPDATED");
  await fireEvent.press(screen.getByText("More results"));
  await fireEvent.press(screen.getByText("More results"));
  expect(search).toHaveBeenCalledTimes(2);
  expect(search).toHaveBeenLastCalledWith("news", "c1");
  expect(screen.getByLabelText("Loading more results")).toBeTruthy();
  expect(screen.getByText("First search UPDATED")).toBeTruthy();
  await act(async () => { finish({ query: "news", items: [story("Updated first"), older], next_cursor: null }); });
  await screen.findByText("Older search UPDATED");
  expect(screen.getAllByText("Updated first UPDATED")).toHaveLength(1);
  expect(screen.queryByText("First search UPDATED")).toBeNull();
  expect(screen.queryByText("More results")).toBeNull();
  expect(screen.getByText("Showing 2 stories · Newest first")).toBeTruthy();
});

test("search paging failure retains results and cursor for retry", async () => {
  jest.useFakeTimers();
  const older = { ...story("Recovered search"), id: "22222222-2222-2222-2222-222222222222" };
  jest.mocked(search).mockResolvedValueOnce({ query: "news", items: [story("Retained search")], next_cursor: "c1" })
    .mockRejectedValueOnce(new ApiNetworkError("offline"))
    .mockResolvedValueOnce({ query: "news", items: [older], next_cursor: null });
  await render(<StoryCacheProvider><SearchScreen /></StoryCacheProvider>);
  await fireEvent.changeText(screen.getByLabelText("Search stories"), "news");
  await act(async () => { jest.advanceTimersByTime(350); });
  await fireEvent.press(await screen.findByText("More results"));
  await screen.findByText("You're offline. Earlier results are still here.");
  expect(screen.getByText("Retained search UPDATED")).toBeTruthy();
  await fireEvent.press(screen.getByText("Retry more results"));
  await screen.findByText("Recovered search UPDATED");
  expect(search).toHaveBeenLastCalledWith("news", "c1");
  expect(screen.getByText("Retained search UPDATED")).toBeTruthy();
});

test.each(["change", "clear", "unmount"])("late search page is ignored after %s", async (action) => {
  jest.useFakeTimers();
  let finish!: (value: Awaited<ReturnType<typeof search>>) => void;
  jest.mocked(search).mockResolvedValueOnce({ query: "news", items: [story("Old query")], next_cursor: "c1" })
    .mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }))
    .mockResolvedValueOnce({ query: "new", items: [story("New query")], next_cursor: null });
  const view = await render(<StoryCacheProvider><SearchScreen /></StoryCacheProvider>);
  await fireEvent.changeText(screen.getByLabelText("Search stories"), "news");
  await act(async () => { jest.advanceTimersByTime(350); });
  await fireEvent.press(await screen.findByText("More results"));
  if (action === "unmount") await view.unmount();
  else {
    await fireEvent.changeText(screen.getByLabelText("Search stories"), action === "change" ? "new" : "");
    await act(async () => { jest.advanceTimersByTime(350); });
  }
  await act(async () => { finish({ query: "news", items: [story("Late page")], next_cursor: "c2" }); });
  expect(screen.queryByText("Late page UPDATED")).toBeNull();
  if (action === "change") expect(screen.getByText("New query UPDATED")).toBeTruthy();
  if (action === "clear") expect(screen.getByText("Search for a story.")).toBeTruthy();
});

test("home reloads on resume only once the feed is stale", async () => {
  let onChange: ((state: AppStateStatus) => void) | undefined;
  jest.spyOn(AppState, "addEventListener").mockImplementation((_type, handler) => {
    onChange = handler as (state: AppStateStatus) => void;
    return { remove: jest.fn() };
  });
  let now = 1_000_000;
  jest.spyOn(Date, "now").mockImplementation(() => now);
  jest.mocked(getHome)
    .mockResolvedValueOnce({ top_stories: [story("Morning")], topics: [] })
    .mockResolvedValueOnce({ top_stories: [story("Evening")], topics: [] });
  await render(<StoryCacheProvider><HomeScreen /></StoryCacheProvider>);
  await screen.findByText("Morning UPDATED");

  now += HOME_STALE_MS - 1;
  await act(async () => { onChange?.("active"); });
  expect(getHome).toHaveBeenCalledTimes(1);

  now += 1;
  await act(async () => { onChange?.("active"); });
  await screen.findByText("Evening UPDATED");
  expect(getHome).toHaveBeenCalledTimes(2);
  jest.restoreAllMocks();
});

test("latest pages through every story by cursor", async () => {
  const older = { ...story("Older"), id: "22222222-2222-2222-2222-222222222222" };
  jest.mocked(listStories)
    .mockResolvedValueOnce({ items: [story("Newest")], next_cursor: "c1" })
    .mockResolvedValueOnce({ items: [older], next_cursor: null });
  await render(<StoryCacheProvider><LatestScreen /></StoryCacheProvider>);
  await screen.findByText("Newest UPDATED");
  await fireEvent.press(screen.getByText("Older stories"));
  await screen.findByText("Older UPDATED");
  expect(listStories).toHaveBeenLastCalledWith({ cursor: "c1" });
  expect(screen.getByText("Newest UPDATED")).toBeTruthy();
  expect(screen.queryByText("Older stories")).toBeNull();
});

// Review R10: story detail opens from the copy a feed already loaded.
function SeedCache({ stories, children }: { stories: StoryOut[]; children: React.ReactNode }) {
  const { put } = useStoryCache();
  const [ready, setReady] = React.useState(false);
  React.useEffect(() => { put(stories); setReady(true); }, [put, stories]);
  return ready ? <>{children}</> : null;
}
const detail = () => <StoryDetailScreen {...({ route: { params: { slug: "example" } } } as any)} />;

test("story detail shows the cached copy at once, then the API version", async () => {
  let resolve!: (s: StoryOut) => void;
  jest.mocked(getStory).mockImplementationOnce(() => new Promise((r) => { resolve = r; }));
  await render(<StoryCacheProvider><SeedCache stories={[story("From feed")]}>{detail()}</SeedCache></StoryCacheProvider>);
  await screen.findByText("From feed UPDATED");
  expect(screen.getByText(/Checking for updates\. Showing the copy loaded/)).toBeTruthy();
  await act(async () => { resolve(story("Corrected")); });
  await screen.findByText("Corrected UPDATED");
});

test("story detail keeps the cached copy offline, labelled, with retry", async () => {
  jest.mocked(getStory).mockRejectedValueOnce(new ApiNetworkError("offline")).mockResolvedValueOnce(story("Back online"));
  await render(<StoryCacheProvider><SeedCache stories={[story("From feed")]}>{detail()}</SeedCache></StoryCacheProvider>);
  await screen.findByText(/You're offline\. Showing the copy loaded at/);
  expect(screen.getByText("From feed UPDATED")).toBeTruthy();
  await fireEvent.press(screen.getByLabelText("Retry loading the latest version"));
  await screen.findByText("Back online UPDATED");
  expect(screen.queryByText(/Showing the copy loaded/)).toBeNull();
});

test("story detail drops a cached copy the API no longer serves", async () => {
  jest.mocked(getStory).mockRejectedValueOnce(new ApiNotFoundError("gone")).mockRejectedValueOnce(new ApiNetworkError("offline"));
  await render(<StoryCacheProvider><SeedCache stories={[story("Retracted later")]}>{detail()}</SeedCache></StoryCacheProvider>);
  await screen.findByText("This story is no longer available.");
  expect(screen.queryByText("Retracted later UPDATED")).toBeNull();
  // Evicted: a retry while offline must not bring the stale copy back.
  await fireEvent.press(screen.getByLabelText("Retry"));
  await screen.findByText("You're offline. Check your connection.");
  expect(screen.queryByText("Retracted later UPDATED")).toBeNull();
});


test("detail rechecks stale content on resume without discarding the reading view", async () => {
  let onChange: ((state: AppStateStatus) => void) | undefined;
  jest.spyOn(AppState, "addEventListener").mockImplementation((_type, handler) => {
    onChange = handler as (state: AppStateStatus) => void;
    return { remove: jest.fn() };
  });
  let now = 1_000_000;
  jest.spyOn(Date, "now").mockImplementation(() => now);
  let resolve!: (value: StoryOut) => void;
  jest.mocked(getStory).mockResolvedValueOnce(story("Read this"))
    .mockImplementationOnce(() => new Promise((r) => { resolve = r; }));
  try {
    await render(<StoryCacheProvider>{detail()}</StoryCacheProvider>);
    await screen.findByText("Read this UPDATED");
    now += HOME_STALE_MS - 1;
    await act(async () => { onChange?.("active"); });
    expect(getStory).toHaveBeenCalledTimes(1);
    now += 1;
    await act(async () => { onChange?.("active"); });
    expect(screen.getByText("Read this UPDATED")).toBeTruthy();
    expect(screen.getByText(/Checking for updates/)).toBeTruthy();
    await act(async () => { onChange?.("active"); });
    expect(getStory).toHaveBeenCalledTimes(2);
    await act(async () => { resolve(story("Latest correction")); });
    await screen.findByText("Latest correction UPDATED");
    expect(screen.queryByText(/Checking for updates/)).toBeNull();
  } finally { jest.restoreAllMocks(); }
});
