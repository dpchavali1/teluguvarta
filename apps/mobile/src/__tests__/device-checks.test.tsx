import AsyncStorage from "@react-native-async-storage/async-storage";
import { getStateFromPath } from "@react-navigation/native";
import { fireEvent, render, screen } from "@testing-library/react-native";
import React from "react";

import { LanguageToggle } from "../components/LanguageToggle";
import { linking } from "../navigation/linking";

jest.mock("../lib/api", () => ({ siteUrl: () => "https://example.test" }));

beforeEach(async () => {
  await AsyncStorage.clear();
});

test("a shared story link opens with Home underneath, Telugu slug decoded once", () => {
  const slug = "రేవంత్-రెడ్డి-a3f320e5";
  const state = getStateFromPath(`story/${encodeURIComponent(slug)}`, linking.config);
  expect(state?.routes.map((r) => r.name)).toEqual(["Main", "StoryDetail"]);
  expect(state?.routes[1].params).toEqual({ slug });
});

test("language toggle exposes the chosen language as a checked radio", async () => {
  await render(<LanguageToggle />);
  expect(await screen.findByRole("radio", { name: "English" })).toBeChecked();
  expect(screen.getByRole("radio", { name: "తెలుగు" })).not.toBeChecked();
  await fireEvent.press(screen.getByRole("radio", { name: "తెలుగు" }));
  expect(screen.getByRole("radio", { name: "తెలుగు" })).toBeChecked();
  expect(screen.getByRole("radio", { name: "English" })).not.toBeChecked();
});
