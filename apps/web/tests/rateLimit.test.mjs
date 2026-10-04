import assert from "node:assert/strict";
import { test } from "node:test";

import { allow, clientKey, shareCardAllowed } from "../src/lib/rateLimit.ts";

test("blocks past the max within the window and recovers after it", () => {
  assert.equal(allow("a", 2, 1000, 0), true);
  assert.equal(allow("a", 2, 1000, 1), true);
  assert.equal(allow("a", 2, 1000, 2), false);
  assert.equal(allow("a", 2, 1000, 1500), true);
});

test("uses the last forwarded hop, not a client-supplied first one", () => {
  assert.equal(clientKey(new Headers({ "x-forwarded-for": "6.6.6.6, 10.0.0.1" })), "10.0.0.1");
  assert.equal(clientKey(new Headers()), "unknown");
});

test("share card: per-client limit of 20 a minute; another client is unaffected", () => {
  const h = (ip) => new Headers({ "x-forwarded-for": ip });
  for (let i = 0; i < 20; i++) assert.equal(shareCardAllowed(h("1.1.1.1"), 10_000_000), true);
  assert.equal(shareCardAllowed(h("1.1.1.1"), 10_000_000), false);
  assert.equal(shareCardAllowed(h("2.2.2.2"), 10_000_000), true);
});
