#!/usr/bin/env node
// Local synthetic fixture only; the server-side API must also point at that fixture.
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const base = process.env.SEARCH_BASE_URL ?? "http://127.0.0.1:3076";
const fixtureApi = process.env.SEARCH_FIXTURE_API ?? "http://127.0.0.1:8076";
const out = process.env.SEARCH_CHECK_OUT ?? "/tmp/tte-search-browser";
assert([base, fixtureApi].every((url) => ["127.0.0.1", "localhost"].includes(new URL(url).hostname)), "Local fixtures required");
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
try {
  for (const width of (process.env.SEARCH_JOURNEYS_ONLY === "1" ? [] : [320, 390, 1440])) {
    for (const theme of ["light", "dark"]) {
      for (const language of ["en", "te"]) {
        const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme });
        await context.route("**/*", (route) => {
          const origin = new URL(route.request().url()).origin;
          return [new URL(base).origin, new URL(fixtureApi).origin].includes(origin) ? route.continue() : route.abort();
        });
        await context.addInitScript(({ theme, language }) => {
          localStorage.setItem("tg-theme", theme);
          localStorage.setItem("tg_onboarding_profile_v1", JSON.stringify({ lifeStages: [], topics: [], language }));
        }, { theme, language });
        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", (error) => errors.push(error.message));
        await page.goto(`${base}/search?q=paged`, { waitUntil: "networkidle" });
        assert.equal(await page.locator(".story-card").count(), 20);
        await page.getByRole("link", { name: "More results", exact: true }).click();
        await page.waitForURL(/cursor=fixture-page-2/);
        await page.getByText("Showing 2 stories on this page · Newest first", { exact: true }).waitFor();
        await page.waitForFunction(() => document.title.includes("Search"));
        await page.evaluate(() => document.fonts.ready);
        assert.equal(await page.locator(".story-card").count(), 2);
        assert.equal(await page.getByLabel("Search stories", { exact: true }).inputValue(), "paged");
        assert.equal(await page.getByRole("link", { name: "More results", exact: true }).count(), 0);
        const heading = page.locator(".story-card__headline").first();
        assert.match(await heading.innerText(), language === "te" ? /శోధన ఫలితం 21/ : /Search result 21/);
        assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), "Overflow");
        const findings = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
        assert.deepEqual(findings.violations.filter((v) => ["serious", "critical"].includes(v.impact)).map((v) => v.id), []);
        if (language === "te" && width !== 320) {
          await page.evaluate(() => scrollTo(0, 0));
          await page.screenshot({ path: `${out}/page-two-${width}-${theme}-te.png`, fullPage: true });
        }
        await page.getByRole("link", { name: "Back to first results", exact: true }).click();
        await page.waitForURL((url) => url.searchParams.get("q") === "paged" && !url.searchParams.has("cursor"));
        assert.equal(await page.locator(".story-card").count(), 20);
        await page.getByLabel("Search stories", { exact: true }).fill("తెలుగు");
        await page.locator(".search-form").getByRole("button", { name: "Search", exact: true }).click();
        await page.waitForURL((url) => url.searchParams.get("q") === "తెలుగు" && !url.searchParams.has("cursor"));
        await page.getByRole("link", { name: "More results", exact: true }).waitFor();
        assert.deepEqual(errors, []);
        await context.close();
        console.log(`Passed ${width}px ${theme} ${language}`);
      }
    }
  }
  const journeyContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await journeyContext.route("**/*", (route) => {
    const origin = new URL(route.request().url()).origin;
    return [new URL(base).origin, new URL(fixtureApi).origin].includes(origin) ? route.continue() : route.abort();
  });
  const page = await journeyContext.newPage();
  await page.goto(`${base}/search?q=paged`, { waitUntil: "networkidle" });
  const more = page.getByRole("link", { name: "More results", exact: true });
  await more.focus();
  assert(await more.evaluate((element) => element === document.activeElement));
  const firstPageAxe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  assert.deepEqual(firstPageAxe.violations.filter((v) => ["serious", "critical"].includes(v.impact)).map((v) => v.id), []);
  await page.keyboard.press("Enter");
  await page.waitForURL(/cursor=fixture-page-2/);
  await page.getByText("Showing 2 stories on this page · Newest first", { exact: true }).waitFor();
  const failureCursor = `fixture-failure-${Date.now()}`;
  await page.goto(`${base}/search?q=page-failure&cursor=${failureCursor}`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Try again", exact: true }).waitFor();
  assert.equal(await page.getByLabel("Search stories", { exact: true }).inputValue(), "page-failure");
  assert.equal(await page.locator('input[type="hidden"][name="cursor"]').inputValue(), failureCursor);
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await page.getByText("Showing 2 stories on this page · Newest first", { exact: true }).waitFor();
  await page.goto(`${base}/search?q=paged&cursor=invalid`, { waitUntil: "networkidle" });
  await page.getByRole("link", { name: "Back to first results", exact: true }).click();
  await page.waitForURL((url) => !url.searchParams.has("cursor"));
  await page.getByRole("link", { name: "More results", exact: true }).waitFor();
  await page.goto(`${base}/search?q=empty`, { waitUntil: "networkidle" });
  assert.equal(await page.getByRole("link", { name: "More results", exact: true }).count(), 0);
  await page.getByText(/No stories match/).first().waitFor();
  await page.goto(`${base}/search?q=legacy`, { waitUntil: "networkidle" });
  await page.getByText(/Up to 20 matches shown/).waitFor();
  assert.equal(await page.getByRole("link", { name: "More results", exact: true }).count(), 0);
  console.log("Passed keyboard paging, first-page axe, page retry/query retention, invalid-cursor recovery, empty results and legacy cap guidance");
} finally {
  await browser.close();
}
