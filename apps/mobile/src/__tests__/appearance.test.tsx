import AsyncStorage from "@react-native-async-storage/async-storage";
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";
import { Appearance, Text } from "react-native";
import * as ReactNative from "react-native";

import { LOCAL_DATA_KEYS, getThemePreference, setThemePreference } from "../lib/storage";
import { PrivacyScreen } from "../screens/PrivacyScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { ThemePreferenceProvider } from "../theme/ThemePreferenceContext";
import { useAppTheme } from "../theme/useAppTheme";

jest.mock("@react-navigation/native", () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
}));
jest.mock("../lib/api", () => ({ deleteAccount: jest.fn(async () => undefined), trackEvent: jest.fn() }));
jest.mock("../lib/identity", () => ({ resetClientToken: jest.fn(async () => undefined) }));

function SchemeProbe() {
  return <Text testID="scheme">{useAppTheme().scheme}</Text>;
}

function renderSettings() {
  return render(
    <ThemePreferenceProvider>
      <SettingsScreen />
      <SchemeProbe />
    </ThemePreferenceProvider>,
  );
}

beforeEach(async () => {
  jest.restoreAllMocks();
  await AsyncStorage.clear();
});

test("theme preference defaults to system, persists, and ignores junk", async () => {
  expect(await getThemePreference()).toBe("system");
  await setThemePreference("dark");
  expect(await getThemePreference()).toBe("dark");
  await AsyncStorage.setItem("tg_theme_pref_v1", "sepia");
  expect(await getThemePreference()).toBe("system");
});

test("delete-data keys include the theme preference", () => {
  expect(LOCAL_DATA_KEYS).toEqual(
    expect.arrayContaining(["tg_onboarded_v1", "tg_profile_v1", "tg_notification_prefs_v1", "tg_saved_stories_v1", "tg_theme_pref_v1"]),
  );
});

test("'Use phone setting' follows the system scheme", async () => {
  jest.spyOn(ReactNative, "useColorScheme").mockReturnValue("dark");
  await renderSettings();
  await waitFor(() => expect(screen.getByTestId("scheme")).toHaveTextContent("dark"));
  expect(screen.getByRole("radio", { name: "Use phone setting" })).toBeChecked();
});

test("choosing Light overrides a dark phone, applies natively, and survives a restart", async () => {
  jest.spyOn(ReactNative, "useColorScheme").mockReturnValue("dark");
  const native = jest.spyOn(Appearance, "setColorScheme").mockImplementation(() => {});
  const first = await renderSettings();
  await fireEvent.press(await screen.findByRole("radio", { name: "Light" }));

  await waitFor(() => expect(screen.getByTestId("scheme")).toHaveTextContent("light"));
  expect(screen.getByRole("radio", { name: "Light" })).toBeChecked();
  expect(native).toHaveBeenLastCalledWith("light");
  expect(await getThemePreference()).toBe("light");

  await first.unmount();
  await renderSettings();
  await waitFor(() => expect(screen.getByTestId("scheme")).toHaveTextContent("light"));
});

test("clearing data puts the app back on the phone setting", async () => {
  jest.spyOn(ReactNative, "useColorScheme").mockReturnValue("light");
  await setThemePreference("dark");
  await render(
    <ThemePreferenceProvider>
      <PrivacyScreen />
      <SchemeProbe />
    </ThemePreferenceProvider>,
  );
  await waitFor(() => expect(screen.getByTestId("scheme")).toHaveTextContent("dark"));

  await fireEvent.press(screen.getByLabelText("Delete account and clear all data on this device"));

  await waitFor(() => expect(screen.getByTestId("scheme")).toHaveTextContent("light"));
  expect(await AsyncStorage.getItem("tg_theme_pref_v1")).toBeNull();
});
