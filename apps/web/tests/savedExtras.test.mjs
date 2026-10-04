import assert from "node:assert/strict";
import { test } from "node:test";
import { JSDOM } from "jsdom";
import { getSavedIds, toggleSaved } from "../src/lib/saved.ts";
import { readExtras, writeExtras } from "../src/lib/savedExtras.ts";
import { addCollection, setNote, toggleMembership } from "../../../packages/domain/savedExtras.ts";

test("unsaving a story drops its note and list membership; other stories keep theirs", () => {
  const dom = new JSDOM("", { url: "https://example.test" });
  const oldWindow = globalThis.window;
  const oldEvent = globalThis.Event;
  globalThis.window = dom.window;
  globalThis.Event = dom.window.Event;
  try {
    toggleSaved("a");
    toggleSaved("b");
    let extras = addCollection(readExtras(), "Visa", "c1");
    extras = toggleMembership(extras, "a", "c1");
    extras = toggleMembership(extras, "b", "c1");
    extras = setNote(setNote(extras, "a", "check dates"), "b", "keep");
    writeExtras(extras);
    assert.equal(toggleSaved("a"), false);
    const after = readExtras();
    assert.equal(after.notes.a, undefined);
    assert.equal(after.membership.a, undefined);
    assert.equal(after.notes.b, "keep");
    assert.deepEqual(after.membership.b, ["c1"]);
    assert.deepEqual(getSavedIds(true), ["b"]);
    window.localStorage.setItem("tg_saved_extras_v1", "broken");
    assert.deepEqual(readExtras().collections, []);
  } finally {
    globalThis.window = oldWindow;
    globalThis.Event = oldEvent;
    dom.window.close();
  }
});
