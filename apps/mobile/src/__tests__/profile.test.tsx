import AsyncStorage from "@react-native-async-storage/async-storage";
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";

import { getConfig, getHome } from "../lib/api";
import { StoryCacheProvider } from "../lib/StoryCacheContext";
import { getOnboarded, getProfile, setOnboarded, setProfile, type OnboardingProfile } from "../lib/storage";
import { HomeScreen } from "../screens/HomeScreen";
import { ProfileScreen } from "../screens/ProfileScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { ThemePreferenceProvider } from "../theme/ThemePreferenceContext";

const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
jest.mock("@react-navigation/native", () => ({
  useNavigation: () => ({ navigate: mockNavigate, goBack: mockGoBack }),
  useFocusEffect: () => {},
}));
jest.mock("../lib/api", () => ({
  ...jest.requireActual("../lib/api"),
  getConfig: jest.fn(),
  getHome: jest.fn(),
  trackEvent: jest.fn(),
}));

const STORED: OnboardingProfile = {
  residenceCountry: "US",
  homeRegion: "Telangana",
  homeCity: "Hyderabad",
  lifeStages: ["INTERNATIONAL_STUDENT"],
  student: { studyCountry: "US", degreeLevel: "Master's" },
  interestTopicSlugs: ["politics"],
  language: "te",
};

beforeEach(async () => {
  jest.clearAllMocks();
  await AsyncStorage.clear();
  jest.mocked(getConfig).mockResolvedValue({
    topics: [
      { slug: "politics", name: "Politics" },
      { slug: "tech", name: "Tech" },
    ],
  } as unknown as Awaited<ReturnType<typeof getConfig>>);
  jest.mocked(getHome).mockResolvedValue({ top_stories: [], topics: [] });
});

test("Settings opens Your profile", async () => {
  await render(
    <ThemePreferenceProvider>
      <SettingsScreen />
    </ThemePreferenceProvider>,
  );
  await fireEvent.press(await screen.findByRole("button", { name: "Your profile" }));
  expect(mockNavigate).toHaveBeenCalledWith("Profile");
});

test("edits save over the stored answers, keep language and onboarding, and go back", async () => {
  await setProfile(STORED);
  await setOnboarded(true);
  await render(<ProfileScreen />);

  const city = await screen.findByLabelText("Home city");
  expect(city).toHaveDisplayValue("Hyderabad");
  expect(screen.getByLabelText("Degree level")).toHaveDisplayValue("Master's");
  await fireEvent.changeText(city, "Warangal");
  await fireEvent.press(await screen.findByRole("checkbox", { name: "Tech" }));
  await fireEvent.press(screen.getByRole("checkbox", { name: "Politics" }));
  await fireEvent.press(screen.getByRole("button", { name: "Save profile" }));

  await waitFor(() => expect(mockGoBack).toHaveBeenCalled());
  expect(await getProfile()).toEqual({ ...STORED, homeCity: "Warangal", interestTopicSlugs: ["tech"] });
  expect(await getOnboarded()).toBe(true);
});

test("dropping the student stage hides and discards study details", async () => {
  await setProfile(STORED);
  await render(<ProfileScreen />);

  await fireEvent.press(await screen.findByRole("checkbox", { name: "International Student" }));
  expect(screen.queryByLabelText("Degree level")).toBeNull();
  await fireEvent.press(screen.getByRole("button", { name: "Save profile" }));

  await waitFor(() => expect(mockGoBack).toHaveBeenCalled());
  const saved = await getProfile();
  expect(saved.lifeStages).toEqual([]);
  expect(saved.student).toBeUndefined();
});

test("going back without saving writes nothing", async () => {
  await setProfile(STORED);
  const view = await render(<ProfileScreen />);
  await fireEvent.changeText(await screen.findByLabelText("Home city"), "Warangal");
  await view.unmount();
  expect(await getProfile()).toEqual(STORED);
});

test("Home reloads with the new answers as soon as they are saved", async () => {
  await setProfile({ ...STORED, lifeStages: [], student: undefined });
  await render(
    <StoryCacheProvider>
      <HomeScreen />
    </StoryCacheProvider>,
  );
  await waitFor(() => expect(getHome).toHaveBeenCalledTimes(1));
  expect(getHome).toHaveBeenLastCalledWith(expect.objectContaining({ homeCity: "Hyderabad", topics: ["politics"] }));

  await render(<ProfileScreen />);
  await fireEvent.changeText(await screen.findByLabelText("Home city"), "Warangal");
  await fireEvent.press(screen.getByRole("button", { name: "Save profile" }));

  await waitFor(() =>
    expect(getHome).toHaveBeenLastCalledWith(expect.objectContaining({ homeCity: "Warangal" })),
  );
});
