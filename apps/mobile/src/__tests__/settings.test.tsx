import AsyncStorage from "@react-native-async-storage/async-storage";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import Constants from "expo-constants";
import React from "react";
import type { OnboardingProfile } from "../lib/storage";
import * as storage from "../lib/storage";
import { LanguageToggle } from "../components/LanguageToggle";
import { DeviceEventEmitter, Linking } from "react-native";

import { SettingsScreen, appVersionLabel } from "../screens/SettingsScreen";
import { NotificationPreferencesForm } from "../components/NotificationPreferencesForm";
import { ThemePreferenceProvider } from "../theme/ThemePreferenceContext";

jest.mock("@react-navigation/native", () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
}));
jest.mock("../lib/api", () => ({
  siteUrl: () => "https://example.test",
  getConfig: () => Promise.resolve({ features: { push_notifications_enabled: false }, topics: [
    { slug: "immigration", name: "Immigration" },
    { slug: "travel", name: "Travel" },
    { slug: "opt", name: "OPT" },
  ] }),
}));
jest.mock("expo-constants", () => ({ __esModule: true, default: { expoConfig: null } }));

function setConfig(config: object | null) {
  (Constants as { expoConfig: unknown }).expoConfig = config;
}

beforeEach(async () => {
  jest.restoreAllMocks();
  await AsyncStorage.clear();
});

afterEach(cleanup);

test.each([
  ["/about", "About The Telugu Edit"],
  ["/ai-disclosure", "How we use AI"],
  ["/privacy", "Privacy policy"],
  ["/terms", "Terms of use"],
])("Settings opens the web %s page", async (path, label) => {
  const open = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
  await render(
    <ThemePreferenceProvider>
      <SettingsScreen />
    </ThemePreferenceProvider>,
  );
  await fireEvent.press(await screen.findByRole("link", { name: label }));
  expect(open).toHaveBeenCalledWith(`https://example.test${path}`);
});

test("a failed open does not throw", async () => {
  jest.spyOn(Linking, "openURL").mockRejectedValue(new Error("no browser"));
  await render(
    <ThemePreferenceProvider>
      <SettingsScreen />
    </ThemePreferenceProvider>,
  );
  await fireEvent.press(await screen.findByRole("link", { name: "Terms of use" }));
  expect(screen.getByRole("link", { name: "Terms of use" })).toBeOnTheScreen();
});

test("topic alerts start off until explicitly selected", async () => {
  const onChange = jest.fn();
  await render(
    <ThemePreferenceProvider>
      <NotificationPreferencesForm value={storage.DEFAULT_NOTIFICATION_PREFERENCES} onChange={onChange} />
    </ThemePreferenceProvider>,
  );
  const topic = await screen.findByLabelText("Immigration alerts");
  expect(screen.getByText(/Push alerts are not available yet/)).toBeOnTheScreen();
  expect(topic.props.value).toBe(false);
  fireEvent(topic, "valueChange", true);
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ topics: { immigration: true } }));
});

test("topic search and selected-only filter make toggles easy to find", async () => {
  function Harness() {
    const [prefs, setPrefs] = React.useState(storage.DEFAULT_NOTIFICATION_PREFERENCES);
    return <ThemePreferenceProvider><NotificationPreferencesForm value={prefs} onChange={setPrefs} /></ThemePreferenceProvider>;
  }
  await render(<Harness />);
  const search = await screen.findByLabelText("Search alert topics");
  fireEvent.changeText(search, "opt");
  expect(screen.getByLabelText("OPT alerts")).toBeOnTheScreen();
  await waitFor(() => expect(screen.queryByLabelText("Immigration alerts")).toBeNull());

  fireEvent(screen.getByLabelText("OPT alerts"), "valueChange", true);
  await waitFor(() => expect(screen.getByLabelText("OPT alerts").props.value).toBe(true));
  fireEvent.press(screen.getByLabelText("Clear topic search"));
  await screen.findByLabelText("Immigration alerts");
  fireEvent.press(screen.getByLabelText("Show selected alert topics only"));
  expect(screen.getByLabelText("OPT alerts")).toBeOnTheScreen();
  await waitFor(() => expect(screen.queryByLabelText("Immigration alerts")).toBeNull());
});

test("version label shows the build number only when configured", () => {
  setConfig({ version: "1.2.3", android: { versionCode: 7 } });
  expect(appVersionLabel()).toBe("Version 1.2.3 (7)");
  setConfig({ version: "1.2.3" });
  expect(appVersionLabel()).toBe("Version 1.2.3");
  setConfig(null);
  expect(appVersionLabel()).toBe("Version unknown");
});

test("header language follows a settings change even if its initial read finishes late", async () => {
  let resolve!: (profile: OnboardingProfile) => void;
  const read = jest.spyOn(storage, "getProfile").mockImplementationOnce(() => new Promise((r) => { resolve = r; }));
  try {
    await render(<LanguageToggle />);
    await act(async () => { DeviceEventEmitter.emit(storage.LANGUAGE_CHANGE_EVENT, "te"); });
    expect(screen.getByRole("radio", { name: "తెలుగు" }).props.accessibilityState.checked).toBe(true);
    await act(async () => { resolve({ lifeStages: [], interestTopicSlugs: [], language: "en" }); });
    expect(screen.getByRole("radio", { name: "తెలుగు" }).props.accessibilityState.checked).toBe(true);
  } finally { read.mockRestore(); }
});
