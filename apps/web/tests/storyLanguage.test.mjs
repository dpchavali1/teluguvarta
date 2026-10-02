import assert from "node:assert/strict";
import { test } from "node:test";
import { JSDOM } from "jsdom";
import { applyStoryLanguage, normalizeStoryLanguage, PROFILE_STORAGE_KEY, STORY_LANGUAGE_INIT_SCRIPT } from "../src/lib/storyLanguage.ts";

test("the pre-paint script selects only a valid stored language and survives unreadable storage", () => {
  for (const [raw, expected] of [[null, "en"], ['{"language":"te"}', "te"], ['{"language":"en"}', "en"], ['{"language":"unknown"}', "en"], ["null", "en"], ["broken", "en"]]) {
    const dom = new JSDOM("", { url: "https://example.test", runScripts: "outside-only" });
    try {
      if (raw !== null) dom.window.localStorage.setItem(PROFILE_STORAGE_KEY, raw);
      dom.window.eval(STORY_LANGUAGE_INIT_SCRIPT);
      assert.equal(dom.window.document.documentElement.getAttribute("data-story-language"), expected);
    } finally { dom.window.close(); }
  }
  const dom = new JSDOM("", { url: "https://example.test", runScripts: "outside-only" });
  try {
    Object.defineProperty(dom.window, "localStorage", { get() { throw new Error("blocked"); } });
    assert.doesNotThrow(() => dom.window.eval(STORY_LANGUAGE_INIT_SCRIPT));
    assert.equal(dom.window.document.documentElement.getAttribute("data-story-language"), "en");
  } finally { dom.window.close(); }
});

test("session selection updates the root without requiring browser storage", () => {
  assert.equal(normalizeStoryLanguage("te"), "te");
  assert.equal(normalizeStoryLanguage({ language: "te" }), "en");
  const dom = new JSDOM("");
  const previous = globalThis.document;
  globalThis.document = dom.window.document;
  try {
    applyStoryLanguage("te");
    assert.equal(document.documentElement.getAttribute("data-story-language"), "te");
    applyStoryLanguage("en");
    assert.equal(document.documentElement.getAttribute("data-story-language"), "en");
  } finally {
    globalThis.document = previous;
    dom.window.close();
  }
});
