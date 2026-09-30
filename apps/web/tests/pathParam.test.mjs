// Runs with node's built-in test runner and type stripping: `pnpm --filter @teluguvarta/web test`.
import assert from "node:assert/strict";
import { test } from "node:test";

import { pathParam } from "../src/lib/pathParam.ts";

test("decodes a percent-encoded Telugu slug once, so the API isn't sent it double-encoded", () => {
  const slug = "సఎ-గరవనన-రవత-b5ee367d";
  assert.equal(pathParam(encodeURIComponent(slug)), slug);
});

test("leaves an ASCII slug unchanged", () => {
  assert.equal(pathParam("jailer-2-team-divided-f37b8a60"), "jailer-2-team-divided-f37b8a60");
});

test("decodes a cursor's escaped padding", () => {
  assert.equal(pathParam("eyJhIjoxfQ%3D%3D"), "eyJhIjoxfQ==");
});

test("returns null for a malformed escape so the page can 404", () => {
  assert.equal(pathParam("%E0%B0"), null);
  assert.equal(pathParam("%zz"), null);
});
