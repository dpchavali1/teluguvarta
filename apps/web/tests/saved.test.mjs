import assert from "node:assert/strict";
import { test } from "node:test";
import { JSDOM } from "jsdom";
import { getSavedIds, toggleSaved } from "../src/lib/saved.ts";

test("unreadable bookmarks fail visibly and a toggle never overwrites them", () => {
  const dom = new JSDOM("", { url: "https://example.test" });
  const oldWindow = globalThis.window;
  const oldEvent = globalThis.Event;
  globalThis.window = dom.window;
  globalThis.Event = dom.window.Event;
  try {
    window.localStorage.setItem("tg_saved_stories", "broken-json");
    assert.deepEqual(getSavedIds(), []);
    assert.throws(() => getSavedIds(true));
    assert.throws(() => toggleSaved("new-id"));
    assert.equal(window.localStorage.getItem("tg_saved_stories"), "broken-json");
    window.localStorage.setItem("tg_saved_stories", '["one","one",42]');
    assert.deepEqual(getSavedIds(true), ["one"]);
    assert.equal(toggleSaved("two"), true);
    assert.deepEqual(getSavedIds(true), ["one", "two"]);
  } finally {
    globalThis.window = oldWindow;
    globalThis.Event = oldEvent;
    dom.window.close();
  }
});
