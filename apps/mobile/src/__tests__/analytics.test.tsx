import AsyncStorage from "@react-native-async-storage/async-storage";
import { logEvent, resetAnalyticsData } from "@react-native-firebase/analytics";
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";
import { Share } from "react-native";

import App from "../../App";
import { resetMobileAnalyticsConsentCacheForTest, setMobileAnalyticsConsent } from "../lib/mobileAnalytics";
import { getNotificationPreferences } from "../lib/storage";

/**
 * ADR-039 permits only coarse interaction names after affirmative mobile
 * analytics consent. Split the smoke flows into focused tests rather
 * than one long one — react-navigation's native-stack screens (StoryDetail,
 * Alerts, Privacy) cover the whole tab bar once pushed, so
 * a flow that needs the tab bar again afterward would have no way back in
 * this RTL environment (no native header back button to query). Each test
 * renders a fresh `<App />` and drives one stack push to its end.
 *
 * With analytics explicitly opted in, safe interaction names fire without
 * caller properties: onboarding_complete, feed_view (test 1); story_open,
 * language_switch, story_save, story_share, a reader report (test 2); search
 * (test 3); notification_opt_in (test 4). Firebase records app_open itself;
 * account deletion is deliberately not an analytics event.
 */

const STORY = {
  id: "22222222-2222-2222-2222-222222222222",
  canonical_slug: "example-story",
  status: "PUBLISHED",
  topics: ["Immigration"],
  countries: ["US"],
  variants: {
    en: { language: "en", headline: "Example headline", summary: "Example summary.", why_matters: null },
    te: { language: "te", headline: "ఉదాహరణ శీర్షిక", summary: "ఉదాహరణ సారాంశం.", why_matters: null },
  },
  sources: [{ url: "https://example.com/original", title: "Example Source" }],
};

let postedReports: Record<string, unknown>[];

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

function mockEvent(name: string) {
  return jest.mocked(logEvent).mock.calls.some(([, event]) => event === name);
}

beforeEach(async () => {
  // Each test drives onboarding from scratch — AsyncStorage's jest mock is
  // a shared in-memory store across tests in the same file, so without
  // this a later test's `getOnboarded()` would see the first test's
  // completed onboarding and skip straight to Main.
  await AsyncStorage.clear();
  resetMobileAnalyticsConsentCacheForTest();
  await setMobileAnalyticsConsent(true);
  jest.clearAllMocks();
  postedReports = [];
  jest.spyOn(Share, "share").mockResolvedValue({ action: "sharedAction" } as never);

  globalThis.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const path = new URL(url).pathname;
    if (path === `/v1/stories/${STORY.id}/reports` && init?.method === "POST") {
      postedReports.push(JSON.parse(init.body as string));
      return jsonResponse({ accepted: true }, 201);
    }
    if (path === "/v1/home") return jsonResponse({ top_stories: [STORY], topics: [] });
    if (path === `/v1/stories/${STORY.canonical_slug}`) return jsonResponse(STORY);
    if (path === "/v1/config") return jsonResponse({ topics: [], features: {} });
    if (path === "/v1/search") return jsonResponse({ query: "example", items: [STORY] });
    return jsonResponse({});
  }) as unknown as typeof fetch;
});

afterEach(() => {
  jest.restoreAllMocks();
});

async function skipOnboarding() {
  const view = await render(<App />);
  fireEvent.press(await screen.findByLabelText("Continue without login"));
  await waitFor(() => expect(mockEvent("onboarding_complete")).toBe(true));
  await waitFor(() => expect(mockEvent("feed_view")).toBe(true));
  return view;
}

test("onboarding_complete and feed_view fire after analytics opt-in", async () => {
  await skipOnboarding();
});

test("story_open, language_switch, story_save, story_share, and report_issue fire from a story", async () => {
  await skipOnboarding();

  fireEvent.press(await screen.findByLabelText(`Open story: ${STORY.variants.en.headline}`));
  await waitFor(() => expect(mockEvent("story_open")).toBe(true));

  const teButtons = await screen.findAllByLabelText("Telugu");
  fireEvent.press(teButtons[teButtons.length - 1]);
  await waitFor(() => expect(mockEvent("language_switch")).toBe(true));

  const saveButtons = await screen.findAllByLabelText(`Save: ${STORY.variants.te.headline}`);
  fireEvent.press(saveButtons[saveButtons.length - 1]);
  await waitFor(() => expect(mockEvent("story_save")).toBe(true));

  const shareButtons = await screen.findAllByLabelText(`Share: ${STORY.variants.te.headline}`);
  fireEvent.press(shareButtons[shareButtons.length - 1]);
  await waitFor(() => expect(mockEvent("story_share")).toBe(true));

  const reportButtons = await screen.findAllByLabelText(`Report an issue: ${STORY.variants.te.headline}`);
  fireEvent.press(reportButtons[reportButtons.length - 1]);
  // ADR-029: a report goes to its own endpoint with a category; the server
  // emits report_issue, so the app doesn't post the text as an event.
  fireEvent.press(await screen.findByLabelText("Telugu translation problem"));
  fireEvent.press(await screen.findByLabelText("Send report"));
  await waitFor(() =>
    expect(postedReports).toEqual([{ category: "TRANSLATION", description: null, language: "te", platform: "ios" }]),
  );
  expect(mockEvent("report_issue")).toBe(false);
});

test("search fires from the Search tab", async () => {
  await skipOnboarding();

  fireEvent.press(await screen.findByLabelText("Search"));
  fireEvent.changeText(await screen.findByLabelText("Search stories"), "example");
  await waitFor(() => expect(mockEvent("search")).toBe(true));
});

test("notification_opt_in fires when the master notification switch is re-enabled", async () => {
  await skipOnboarding();

  fireEvent.press(await screen.findByLabelText("Settings"));
  expect(screen.queryByLabelText("Notification preferences")).toBeNull();
  fireEvent.press(await screen.findByLabelText("Alerts"));
  await screen.findByText("Choose your alerts");
  const enableSwitch = await screen.findByLabelText("Send alerts");

  fireEvent(enableSwitch, "valueChange", false);
  // Let the state update from the first toggle commit before firing the
  // second — otherwise handleChange's `prefs` closure is still stale and
  // both toggles are read as no-ops relative to each other.
  await waitFor(() => expect(enableSwitch.props.value).toBe(false));
  expect((await screen.findByLabelText("Breaking news alerts")).props.disabled).toBe(true);
  await screen.findByText(/Your choices below are saved/);
  expect(mockEvent("notification_opt_in")).toBe(false);

  fireEvent(enableSwitch, "valueChange", true);
  await waitFor(() => expect(mockEvent("notification_opt_in")).toBe(true));
  expect((await screen.findByLabelText("Breaking news alerts")).props.disabled).toBe(false);

  fireEvent(await screen.findByLabelText("Pause alerts overnight"), "valueChange", true);
  fireEvent.press(await screen.findByLabelText("Quiet hours start one hour later"));
  await waitFor(async () => expect((await getNotificationPreferences()).quietHoursStart).toBe("23:00"));
});

test("account deletion resets the Firebase analytics identifier", async () => {
  await skipOnboarding();

  fireEvent.press(await screen.findByLabelText("Settings"));
  fireEvent.press(await screen.findByLabelText("Privacy & delete account"));
  fireEvent.press(await screen.findByLabelText("Delete account and clear all data on this device"));
  await waitFor(() => expect(resetAnalyticsData).toHaveBeenCalled());
});

test("Alert settings show a retry when server sync fails", async () => {
  await skipOnboarding();
  const baseFetch = globalThis.fetch;
  let failuresLeft = 1;
  globalThis.fetch = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(typeof input === "string" ? input : input.toString()).pathname;
    if (path === "/v1/me/preferences" && init?.method === "PATCH" && failuresLeft-- > 0) {
      return jsonResponse({}, 503);
    }
    return baseFetch(input, init);
  }) as unknown as typeof fetch;

  fireEvent.press(await screen.findByLabelText("Settings"));
  fireEvent.press(await screen.findByLabelText("Alerts"));
  await screen.findByText(/Earlier alerts may still arrive/);
  fireEvent.press(await screen.findByLabelText("Retry syncing alert settings"));
  await waitFor(() => expect(screen.queryByText(/Earlier alerts may still arrive/)).toBeNull());
});
