#!/usr/bin/env node
// UI12–UI14: run against an already-started local web/API pair. No server
// mutations: fixtures mode exercises errors and local bookmarks only.
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const base = process.env.INTERFACE_BASE_URL ?? "http://localhost:3000";
const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const output = process.env.INTERFACE_OUT_DIR ?? join(tmpdir(), "tte-interface-check");
const fixtures = process.env.INTERFACE_FIXTURE === "1";
mkdirSync(output, { recursive: true });
const published = await (await fetch(new URL("/v1/stories?limit=1", api))).json();
const paths = ["/", "/latest", "/topics", "/search", "/saved", "/account/delete"];
const slug = published.items?.[0]?.canonical_slug;
if (!slug) throw new Error("At least one published story is required for the reading checks");
paths.push(`/story/${encodeURIComponent(slug)}`);
const failures = [];
const layouts = [];
const browser = await chromium.launch();
try {
  for (const [width, height] of (process.env.INTERFACE_JOURNEYS_ONLY === "1" ? [] : [[320, 844], [390, 844], [768, 1024], [1440, 900], [640, 400]])) {
    for (const theme of ["light", "dark"]) {
      for (const language of ["en", "te"]) {
        const context = await browser.newContext({ viewport: { width, height }, colorScheme: theme, reducedMotion: "reduce" });
        await context.addInitScript(({ theme, language }) => {
          localStorage.setItem("tg-theme", theme);
          localStorage.setItem("tg_onboarding_profile_v1", JSON.stringify({ lifeStages: [], topics: [], language }));
          window.__layoutShift = { max: 0, sum: 0, first: 0, last: 0 };
          new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
              if (entry.hadRecentInput) continue;
              const value = window.__layoutShift;
              if (entry.startTime - value.last > 1000 || entry.startTime - value.first > 5000) {
                value.sum = 0; value.first = entry.startTime;
              }
              value.sum += entry.value; value.last = entry.startTime;
              value.max = Math.max(value.max, value.sum);
            }
          }).observe({ type: "layout-shift", buffered: true });
        }, { theme, language });
        const page = await context.newPage();
        page.setDefaultTimeout(10000);
        for (const path of paths) {
          const label = `${path} ${width}x${height} ${theme} ${language}`;
          try {
            await page.goto(new URL(path, base).href, { waitUntil: "networkidle" });
            await page.locator("main h1").waitFor();
            await page.evaluate(() => document.fonts.ready);
            const measured = await page.evaluate(() => {
              const headline = document.querySelector(".front-grid__lead .story-card__headline");
              return {
                overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                leadTop: headline?.getBoundingClientRect().top,
                cls: window.__layoutShift.max,
              };
            });
            assert(!measured.overflow, "horizontal page overflow");
            if (path === "/") assert(measured.leadTop < height, "lead begins below fold");
            layouts.push({ label, ...measured });
            if (width === 390) {
              const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
              const serious = axe.violations.filter((v) => ["serious", "critical"].includes(v.impact));
              assert.deepEqual(serious.map((v) => v.id), [], "serious/critical axe findings");
            }
            if ([390, 1440].includes(width)) await page.screenshot({ path: join(output, `${path.replaceAll("/", "_") || "home"}-${width}-${theme}-${language}.png`), fullPage: true });
          } catch (error) { failures.push({ label, message: error.message }); console.error(label, error.message); }
        }
        console.log(`Checked ${width}x${height} ${theme} ${language}`);
        await context.close();
      }
    }
  }

  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce" });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  const check = async (label, action) => { try { await action(); console.log(`Checked ${label}`); } catch (error) { failures.push({ label, message: error.message }); console.error(label, error.message); } };
  await check("topic scrolling, selection and focus", async () => {
    await page.goto(base, { waitUntil: "domcontentloaded" });
    await page.locator(".front-grid__lead .story-card__headline").waitFor();
    const more = page.getByRole("button", { name: "More topics" });
    if (await more.count()) {
      assert(await page.getByRole("button", { name: "Previous topics" }).isDisabled());
      await more.click();
      await page.locator("#header-topics").evaluate((el) => { el.scrollLeft = el.scrollWidth; });
      await page.waitForTimeout(100);
      assert(await more.isDisabled());
    }
    const last = page.locator("#header-topics a").last();
    await page.keyboard.press("Tab");
    await last.focus();
    assert(await last.evaluate((el) => el === document.activeElement && getComputedStyle(el).outlineStyle !== "none"));
    await last.click();
    await page.waitForURL(/\/topic\//);
    assert.equal(await page.locator('#header-topics [aria-current="page"]').count(), 1);
    // At a border width, controls must disappear when the items fit without them.
    if (fixtures) {
      await page.locator("#header-topics").evaluate((el) => [...el.children].slice(3).forEach((item) => item.remove()));
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.getByRole("button", { name: "More topics" }).waitFor({ state: "detached" });
    }
  });
  if (fixtures) {
    await check("zero/one story and returning preferences", async () => {
      for (const [homeState, count] of [["fixture-empty", 0], ["fixture-one", 1]]) {
        await page.goto(base, { waitUntil: "domcontentloaded" });
        await page.evaluate((homeState) => localStorage.setItem("tg_onboarding_profile_v1", JSON.stringify({ lifeStages: ["professional"], topics: [], language: "te", homeState })), homeState);
        await page.reload({ waitUntil: "domcontentloaded" });
        if (count === 0) await page.locator(".feed .empty-state").waitFor();
        else {
          await page.locator(".front-grid__side").waitFor({ state: "detached" });
          assert.equal(await page.locator(".front-grid__lead article").count(), 1);
        }
        assert.equal(await page.getByRole("link", { name: "Edit preferences" }).count(), 1);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1));
      }
      await page.evaluate(() => localStorage.removeItem("tg_onboarding_profile_v1"));
    });
    await check("English fallback, updated detail and link-first brief", async () => {
      await page.goto(new URL("/story/interface-fallback", base).href, { waitUntil: "domcontentloaded" });
      await page.evaluate(() => localStorage.setItem("tg_onboarding_profile_v1", JSON.stringify({ lifeStages: [], topics: [], language: "te" })));
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.getByText("Telugu translation isn’t available yet. Showing English.").waitFor();
      assert.equal(await page.locator('.story-detail .story-card__headline[lang="en"]').count(), 1);
      assert.equal(await page.getByText("Updated / corrected", { exact: true }).count(), 1);
      await page.goto(new URL("/story/interface-brief", base).href, { waitUntil: "domcontentloaded" });
      await page.locator(".story-card__source-link--lead").waitFor();
      assert.equal(await page.locator(".story-card__why").count(), 0);
      await page.evaluate(() => localStorage.removeItem("tg_onboarding_profile_v1"));
    });
    await check("search count and failure recovery", async () => {
      await page.goto(new URL("/search?q=sample", base).href, { waitUntil: "domcontentloaded" });
      await page.locator(".result-count").waitFor();
      assert.match(await page.locator(".result-count").innerText(), /Up to 20 matches shown/);
      await page.goto(new URL("/search?q=failed", base).href, { waitUntil: "domcontentloaded" });
      await page.getByRole("button", { name: "Try again" }).waitFor();
      assert.equal(await page.getByRole("searchbox").inputValue(), "failed");
      assert.equal(await page.getByRole("button", { name: "Try again" }).count(), 1);
      await page.goto(new URL("/search?q=empty", base).href, { waitUntil: "domcontentloaded" });
      await page.locator(".empty-state").waitFor();
      assert.match(await page.locator(".empty-state").innerText(), /No stories match/);
    });
    await check("saved lookup and corrupted storage recovery", async () => {
      await page.goto(base, { waitUntil: "domcontentloaded" });
    await page.locator(".front-grid__lead .story-card__headline").waitFor();
      await page.evaluate((id) => localStorage.setItem("tg_saved_stories", JSON.stringify([id, "unavailable"])), published.items[0].id);
      await page.goto(new URL("/saved", base).href, { waitUntil: "domcontentloaded" });
      await page.locator(".callout").waitFor();
      assert.match(await page.locator(".callout").innerText(), /currently unavailable/);
      assert.equal(await page.locator(".story-grid article").count(), 1);
      await page.evaluate(() => localStorage.setItem("tg_saved_stories", "broken"));
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.locator('main [role="alert"]').waitFor();
      assert.match(await page.locator('main [role="alert"]').innerText(), /couldn’t be read/);
      assert.equal(await page.evaluate(() => localStorage.getItem("tg_saved_stories")), "broken");
    });
  }
  await context.close();
} finally { await browser.close(); }
const report = { layoutChecks: layouts.length, failures, maxSyntheticCLS: Math.max(0, ...layouts.map((item) => item.cls)), layouts };
writeFileSync(join(output, "report.json"), JSON.stringify(report, null, 2));
console.log(JSON.stringify({ layoutChecks: report.layoutChecks, failures, maxSyntheticCLS: report.maxSyntheticCLS, output }));
if (failures.length) process.exitCode = 1;
