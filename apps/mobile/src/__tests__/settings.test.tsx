import AsyncStorage from "@react-native-async-storage/async-storage";
import { act, fireEvent, render, screen } from "@testing-library/react-native";
import Constants from "expo-constants";
import React from "react";
import type { OnboardingProfile } from "../lib/storage";
import * as storage from "../lib/storage";
import { LanguageToggle } from "../components/LanguageToggle";
import { DeviceEventEmitter, Linking } from "react-native";

import { SettingsScreen, appVersionLabel } from "../screens/SettingsScreen";
import { ThemePreferenceProvider } from "../theme/ThemePreferenceContext";

jest.mock("@react-navigation/native", () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
}));
jest.mock("../lib/api", () => ({ siteUrl: () => "https://example.test" }));
jest.mock("expo-constants", () => ({ __esModule: true, default: { expoConfig: null } }));

function setConfig(config: object | null) {
  (Constants as { expoConfig: unknown }).expoConfig = config;
}

beforeEach(async () => {
  jest.restoreAllMocks();
  await AsyncStorage.clear();
});

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
