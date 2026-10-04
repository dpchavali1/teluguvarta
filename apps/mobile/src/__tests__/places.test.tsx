import AsyncStorage from "@react-native-async-storage/async-storage";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";

import { getFollowedPlaces, saveFollowedPlaces } from "../lib/storage";
import { PlacesScreen } from "../screens/PlacesScreen";
import { ThemePreferenceProvider } from "../theme/ThemePreferenceContext";

const mockNavigate = jest.fn();
jest.mock("@react-navigation/native", () => ({ useNavigation: () => ({ navigate: mockNavigate }) }));
jest.mock("../lib/notificationSync", () => ({ syncSavedStories: jest.fn() }));

beforeEach(async () => {
  mockNavigate.mockClear();
  await AsyncStorage.clear();
});
afterEach(cleanup);

function renderScreen() {
  return render(
    <ThemePreferenceProvider>
      <PlacesScreen />
    </ThemePreferenceProvider>,
  );
}

test("follow storage keeps catalog ids only, de-duplicates and caps at 10", async () => {
  const saved = await saveFollowedPlaces([
    { placeId: "IN-TG-warangal", alerts: true },
    { placeId: "IN-TG-warangal", alerts: false },
    { placeId: "Narnia", alerts: true },
    ...["US-CA", "US-TX", "US-NJ", "US-NY", "US-IL", "US-WA", "US-VA", "US-GA", "US-NC", "US-FL", "US-MA"].map(
      (placeId) => ({ placeId, alerts: false }),
    ),
  ]);
  expect(saved).toHaveLength(10);
  expect(saved[0]).toEqual({ placeId: "IN-TG-warangal", alerts: true });
  expect((await getFollowedPlaces()).map((p) => p.placeId)).not.toContain("Narnia");
});

test("follows a place, toggles its alert switch, and removes it", async () => {
  await renderScreen();
  await fireEvent.changeText(await screen.findByLabelText("Search places"), "warangal");
  await fireEvent.press(await screen.findByRole("button", { name: "Follow Warangal" }));

  await waitFor(async () => expect(await getFollowedPlaces()).toEqual([{ placeId: "IN-TG-warangal", alerts: false }]));
  await fireEvent(await screen.findByLabelText("Alerts for Warangal"), "valueChange", true);
  await waitFor(async () => expect((await getFollowedPlaces())[0]?.alerts).toBe(true));

  await fireEvent.press(await screen.findByRole("button", { name: "Stories for Warangal" }));
  expect(mockNavigate).toHaveBeenCalledWith("PlaceStories", { placeId: "IN-TG-warangal" });

  await fireEvent.press(await screen.findByRole("button", { name: "Stop following Warangal" }));
  await waitFor(async () => expect(await getFollowedPlaces()).toEqual([]));
});

test("disables Follow once ten places are followed", async () => {
  await saveFollowedPlaces(
    ["US-CA", "US-TX", "US-NJ", "US-NY", "US-IL", "US-WA", "US-VA", "US-GA", "US-NC", "US-FL"].map((placeId) => ({
      placeId,
      alerts: false,
    })),
  );
  await renderScreen();
  expect(await screen.findByText(/following the maximum/i)).toBeTruthy();
  const follow = await screen.findByRole("button", { name: "Follow India" });
  expect(follow.props.accessibilityState).toMatchObject({ disabled: true });
});
