#!/usr/bin/env node
// T14 acceptance criterion: "Automated accessibility check (e.g. axe) passes
// on home and story pages with no critical violations." Runs against a
// server already started with `next start` (or `next dev`) at BASE_URL —
// fetches the rendered HTML and checks it with axe-core inside jsdom, no
// browser download required.
//
// T19 §3.4 extends this from "home + story" to every page category a
// visitor actually reaches without an account (topic, search, saved,
// legal), and pins axe-core's ruleset to the WCAG 2.2 AA tag set explicitly
// rather than its (broader, includes best-practice) default — this is the
// literal "full WCAG 2.2 AA audit" the ticket asks for, with the same
// caveat T14 already documented: jsdom has no layout engine, so
// contrast-ratio and other CSS-rendering-dependent rules can't fire here —
// a real-browser (Playwright/axe) pass is still future scope, not something
// this check can claim.
import { JSDOM } from "jsdom";
import axeCore from "axe-core";

const BASE_URL = process.env.A11Y_BASE_URL ?? "http://localhost:3000";
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"];

async function checkPage(path) {
  const url = new URL(path, BASE_URL).toString();
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status} — is the server running and seeded?`);
  }
  const html = await response.text();
  const dom = new JSDOM(html, { url, runScripts: "outside-only", pretendToBeVisual: true });

  dom.window.eval(axeCore.source);
  const results = await dom.window.axe.run(dom.window.document, {
    resultTypes: ["violations"],
    runOnly: { type: "tag", values: WCAG_TAGS },
  });

  const serious = results.violations.filter((v) => v.impact === "critical" || v.impact === "serious");
  return { url, violations: results.violations, serious };
}

async function main() {
  const homeSlug = process.env.A11Y_STORY_SLUG;
  let storySlug = homeSlug;
  if (!storySlug) {
    const storiesResponse = await fetch(new URL("/v1/stories?limit=1", process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"));
    const stories = await storiesResponse.json();
    storySlug = stories.items?.[0]?.canonical_slug;
  }

  const pages = [
    "/",
    "/search",
    "/saved",
    "/about",
    "/privacy",
    "/terms",
    "/ai-disclosure",
    "/corrections",
    "/copyright-takedown",
    "/account/delete",
  ];
  if (storySlug) pages.push(`/story/${storySlug}`);
  else console.warn("No published story found — skipping the story-page a11y check (seed one with `pnpm run seed`).");

  const configResponse = await fetch(new URL("/v1/config", process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"));
  const config = await configResponse.json();
  const topicSlug = config.topics?.[0]?.slug;
  if (topicSlug) pages.push(`/topic/${topicSlug}`);

  let failed = false;
  for (const path of pages) {
    const { url, violations, serious } = await checkPage(path);
    if (violations.length === 0) {
      console.log(`OK   ${url} — no violations`);
      continue;
    }
    console.log(`--   ${url} — ${violations.length} violation(s), ${serious.length} critical/serious:`);
    for (const v of violations) {
      console.log(`     [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} node(s))`);
    }
    if (serious.length > 0) failed = true;
  }

  if (failed) {
    console.error("\nFAILED: critical or serious accessibility violations found.");
    process.exit(1);
  }
  console.log("\nPASSED: no critical or serious accessibility violations.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
