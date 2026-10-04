import AsyncStorage from "@react-native-async-storage/async-storage";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";

import { getFollowedExams, getFollowedVisa, saveFollowedExams, saveFollowedVisa } from "../lib/storage";
import { TrackersScreen } from "../screens/TrackersScreen";
import { ThemePreferenceProvider } from "../theme/ThemePreferenceContext";

jest.mock("../lib/notificationSync", () => ({ syncSavedStories: jest.fn() }));
jest.mock("../lib/api", () => ({
  getLatestVisaBulletin: jest.fn().mockResolvedValue({
    id: "b1",
    month: "2026-10",
    status: "APPROVED",
    source_url: "https://travel.state.gov/x",
    entries: [{ chart: "FINAL_ACTION", category: "EB2", country: "INDIA", cutoff: "2012-01-01", previous: "2011-12-01", movement: "FORWARD" }],
  }),
  listExamDeadlines: jest.fn().mockResolvedValue([
    { id: "d1", exam: "GRE", kind: "EXAM_DATE", title: "GRE test window", deadline: "2026-12-01", source_url: "https://ets.org/gre", status: "APPROVED" },
  ]),
}));

beforeEach(() => AsyncStorage.clear());
afterEach(cleanup);

const renderScreen = () =>
  render(
    <ThemePreferenceProvider>
      <TrackersScreen />
    </ThemePreferenceProvider>,
  );

test("storage drops invalid, duplicate and over-cap tracker follows", async () => {
  const visa = await saveFollowedVisa([
    { category: "EB2", country: "INDIA", alerts: true },
    { category: "EB2", country: "INDIA", alerts: false },
    { category: "ZZ", country: "INDIA", alerts: true },
  ]);
  expect(visa).toEqual([{ category: "EB2", country: "INDIA", alerts: true }]);
  const exams = await saveFollowedExams([{ exam: "GRE", alerts: false }, { exam: "bad key", alerts: true }]);
  expect(exams).toEqual([{ exam: "GRE", alerts: false }]);
});

test("follows a visa category and an exam, showing the approved cutoff", async () => {
  await renderScreen();
  await fireEvent.press(await screen.findByRole("button", { name: "EB2" }));
  await fireEvent.press(await screen.findByRole("button", { name: "India" }));
  await fireEvent.press(await screen.findByRole("button", { name: "Follow EB2 · India" }));
  expect(await screen.findByText(/Final action: 2012-01-01 \(moved forward\)/)).toBeTruthy();
  await waitFor(async () => expect(await getFollowedVisa()).toEqual([{ category: "EB2", country: "INDIA", alerts: false }]));

  await fireEvent.press(await screen.findByRole("button", { name: "Follow GRE" }));
  await waitFor(async () => expect(await getFollowedExams()).toEqual([{ exam: "GRE", alerts: false }]));
});
