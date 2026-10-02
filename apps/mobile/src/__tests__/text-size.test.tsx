import AsyncStorage from "@react-native-async-storage/async-storage";
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";
import { StyleSheet } from "react-native";

import { StoryCard } from "../components/StoryCard";
import type { StoryOut } from "../lib/api";
import { StoryCacheProvider } from "../lib/StoryCacheContext";
import { LOCAL_DATA_KEYS, getTextSize, setTextSize } from "../lib/storage";
import { PrivacyScreen } from "../screens/PrivacyScreen";
import { SettingsScreen } from "../screens/SettingsScreen";
import { TextSizeProvider, scaledStoryType } from "../theme/TextSizeContext";
import { typography, typographyTe } from "../theme/tokens";

jest.mock("@react-navigation/native", () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
}));
jest.mock("../lib/api", () => ({
  ...jest.requireActual("../lib/api"),
  deleteAccount: jest.fn(async () => undefined),
  trackEvent: jest.fn(),
}));
jest.mock("../lib/identity", () => ({ resetClientToken: jest.fn(async () => undefined) }));

const story: StoryOut = {
  id: "11111111-1111-1111-1111-111111111111", canonical_slug: "example", status: "PUBLISHED", sensitivity: "NONE", format: "FULL",
  importance: 0.5, published_at: "2026-09-01T12:00:00Z", updated_at: "2026-09-01T12:00:00Z",
  countries: [], topics: [], sources: [],
  variants: { en: { language: "en", headline: "Visa rules change", summary: "What changed and when.", qa_status: "PASSED" } },
};

function renderWithSize(children: React.ReactNode) {
  return render(
    <TextSizeProvider>
      <StoryCacheProvider>{children}</StoryCacheProvider>
    </TextSizeProvider>,
  );
}

const fontSizeOf = (text: string) => StyleSheet.flatten(screen.getByText(text).props.style).fontSize;

beforeEach(async () => {
  await AsyncStorage.clear();
});

test("text size defaults, persists, ignores junk, and is cleared with the other data", async () => {
  expect(await getTextSize()).toBe("default");
  await setTextSize("xlarge");
  expect(await getTextSize()).toBe("xlarge");
  await AsyncStorage.setItem("tg_text_size_v1", "huge");
  expect(await getTextSize()).toBe("default");
  expect(LOCAL_DATA_KEYS).toContain("tg_text_size_v1");
});

test("scaled type keeps each language's leading, Telugu rounding up", () => {
  expect(scaledStoryType("en", "default")).toBe(typography);
  const en = scaledStoryType("en", "large");
  expect(en.body).toMatchObject({ fontSize: 17, lineHeight: 26 }); // 15 × 1.15, 23 × 1.15 = 26.45
  const te = scaledStoryType("te", "large");
  expect(te.body).toMatchObject({ fontSize: 17, lineHeight: 28 }); // 24 × 1.15 = 27.6 → 28
  expect(te.display.lineHeight).toBe(Math.ceil(typographyTe.display.lineHeight * 1.15));
  // Chrome-sized meta text is not story text and stays put.
  expect(te.meta).toBe(typographyTe.meta);
});

test("choosing a size in Settings resizes story text and survives a restart", async () => {
  const first = await renderWithSize(
    <>
      <SettingsScreen />
      <StoryCard story={story} layout="compact" onOpenSource={() => {}} />
    </>,
  );
  expect(await screen.findByRole("radio", { name: "Default" })).toBeChecked();
  expect(fontSizeOf("What changed and when.")).toBe(typography.body.fontSize);

  await fireEvent.press(screen.getByRole("radio", { name: "Extra large" }));

  expect(screen.getByRole("radio", { name: "Extra large" })).toBeChecked();
  expect(fontSizeOf("What changed and when.")).toBe(Math.round(typography.body.fontSize * 1.3));
  expect(fontSizeOf("Visa rules change")).toBe(Math.round(typography.headline.fontSize * 1.3));
  await waitFor(async () => expect(await getTextSize()).toBe("xlarge"));

  await first.unmount();
  await renderWithSize(<StoryCard story={story} layout="compact" onOpenSource={() => {}} />);
  expect(await screen.findByText("What changed and when.")).toBeTruthy();
  expect(fontSizeOf("What changed and when.")).toBe(Math.round(typography.body.fontSize * 1.3));
});

test("clearing data puts story text back to the default size", async () => {
  await setTextSize("large");
  await renderWithSize(
    <>
      <PrivacyScreen />
      <StoryCard story={story} layout="compact" onOpenSource={() => {}} />
    </>,
  );
  await screen.findByText("What changed and when.");
  expect(fontSizeOf("What changed and when.")).toBe(Math.round(typography.body.fontSize * 1.15));

  await fireEvent.press(screen.getByLabelText("Delete account and clear all data on this device"));

  await waitFor(() => expect(fontSizeOf("What changed and when.")).toBe(typography.body.fontSize));
  expect(await AsyncStorage.getItem("tg_text_size_v1")).toBeNull();
});

test("a link-first brief keeps the source action and suppresses unexpected commentary", async () => {
  const brief: StoryOut = {
    ...story, format: "BRIEF",
    variants: { en: { ...story.variants.en!, why_matters: "Unexpected extra commentary" } },
    sources: [{ url: "https://example.test/announcement", title: "Announcement", is_x_post: false }],
  };
  await renderWithSize(<StoryCard story={brief} layout="detail" onOpenSource={() => {}} />);
  await screen.findByText("Visa rules change");
  expect(screen.getByRole("link", { name: "Read the original source: Announcement" })).toBeTruthy();
  expect(screen.queryByText(/Unexpected extra commentary/)).toBeNull();
});
