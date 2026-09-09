import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import React from "react";
import { Share } from "react-native";

import App from "../../App";

// T15 acceptance criterion: "onboarding-skip -> home -> story open -> save
// -> share". Everything the app talks to (the public API, the OS share
// sheet, on-device storage) is mocked here — this proves the app's own
// wiring, not a live backend or a real device share sheet.
const STORY = {
  id: "11111111-1111-1111-1111-111111111111",
  canonical_slug: "example-story",
  status: "PUBLISHED",
  topics: ["Immigration"],
  countries: ["US"],
  variants: {
    en: {
      language: "en",
      headline: "Example headline",
      summary: "Example summary.",
      why_matters: "It matters because of reasons.",
    },
  },
  sources: [{ url: "https://example.com/original", title: "Example Source" }],
};

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

beforeEach(() => {
  jest.spyOn(Share, "share").mockResolvedValue({ action: "sharedAction" } as never);
  global.fetch = jest.fn((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    const path = new URL(url).pathname;
    if (path === "/v1/home") return jsonResponse({ top_stories: [STORY], topics: [] });
    if (path === `/v1/stories/${STORY.canonical_slug}`) return jsonResponse(STORY);
    if (path === "/v1/config") return jsonResponse({ topics: [], features: {} });
    return jsonResponse({});
  }) as unknown as typeof fetch;
});

afterEach(() => {
  jest.restoreAllMocks();
});

test("onboarding skip -> home -> story open -> save -> share", async () => {
  await render(<App />);

  const skipButton = await screen.findByLabelText("Continue without login");
  fireEvent.press(skipButton);

  const openLink = await screen.findByLabelText(`Open story: ${STORY.variants.en.headline}`);
  fireEvent.press(openLink);

  // React Navigation's native stack keeps Home mounted underneath the
  // pushed StoryDetail screen, so the story renders twice in the tree (its
  // card on Home, plus the freshly-fetched detail screen) — query the last
  // match (the most recently mounted instance) rather than assuming one.
  await waitFor(async () => {
    const opens = await screen.findAllByLabelText(`Open story: ${STORY.variants.en.headline}`);
    expect(opens.length).toBeGreaterThanOrEqual(1);
  });

  const saveButtons = await screen.findAllByLabelText(`Save: ${STORY.variants.en.headline}`);
  const saveButton = saveButtons[saveButtons.length - 1];
  fireEvent.press(saveButton);
  await waitFor(async () => {
    const unsaveButtons = await screen.findAllByLabelText(`Unsave: ${STORY.variants.en.headline}`);
    expect(unsaveButtons.length).toBeGreaterThanOrEqual(1);
  });

  const shareButtons = await screen.findAllByLabelText(`Share: ${STORY.variants.en.headline}`);
  fireEvent.press(shareButtons[shareButtons.length - 1]);

  await waitFor(() => expect(Share.share).toHaveBeenCalledTimes(1));
  const payload = (Share.share as jest.Mock).mock.calls[0][0];
  expect(payload.message).toContain(`/story/${STORY.canonical_slug}`);
});
