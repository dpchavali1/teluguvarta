import assert from "node:assert/strict";
import { test } from "node:test";
import { JSDOM } from "jsdom";
import { parseReadingPrefs, READING_INIT_SCRIPT, READING_STORAGE_KEY } from "../src/lib/readingPrefs.ts";

test("parse keeps valid fields and defaults the rest", () => {
  assert.deepEqual(parseReadingPrefs('{"textSize":"large","teluguFont":"nope","readingStyle":"short"}'), { textSize: "large", teluguFont: "default", readingStyle: "short" });
  for (const raw of [null, "broken", "null"]) assert.deepEqual(parseReadingPrefs(raw), { textSize: "default", teluguFont: "default", readingStyle: "full" });
});

test("the pre-paint script sets validated attributes and survives blocked storage", () => {
  const run = (setup) => {
    const dom = new JSDOM("", { url: "https://example.test", runScripts: "outside-only" });
    try { setup(dom); dom.window.eval(READING_INIT_SCRIPT); const r = dom.window.document.documentElement; return [r.getAttribute("data-text-size"), r.getAttribute("data-telugu-font"), r.getAttribute("data-reading")]; } finally { dom.window.close(); }
  };
  assert.deepEqual(run((d) => d.window.localStorage.setItem(READING_STORAGE_KEY, '{"textSize":"xlarge","teluguFont":"mandali","readingStyle":"short"}')), ["xlarge", "mandali", "short"]);
  assert.deepEqual(run((d) => d.window.localStorage.setItem(READING_STORAGE_KEY, '{"textSize":"huge"}')), ["default", "default", "full"]);
  assert.deepEqual(run((d) => Object.defineProperty(d.window, "localStorage", { get() { throw new Error("blocked"); } })), [null, null, null]);
});
