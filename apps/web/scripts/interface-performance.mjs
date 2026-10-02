#!/usr/bin/env node
// Cold/warm browser contexts; identical fixture API for both production builds.
// This compares local layout/resource behavior, not production Core Web Vitals.
import { mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium } from "@playwright/test";

const before = process.env.INTERFACE_BASELINE_URL;
const after = process.env.INTERFACE_BASE_URL ?? "http://localhost:3000";
const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
if (!before) throw new Error("Set INTERFACE_BASELINE_URL to an isolated baseline production build");
const first = (await (await fetch(new URL("/v1/stories?limit=1", api))).json()).items?.[0];
if (!first) throw new Error("A published fixture story is required");
const output = process.env.INTERFACE_OUT_DIR ?? join(tmpdir(), "tte-interface-performance");
mkdirSync(output, { recursive: true });
const delayed = process.env.INTERFACE_SLOW_CHECK === "1";
const results = [];
const browser = await chromium.launch();
try {
  for (const width of (delayed ? [320] : [320, 390, 1440])) {
    for (const language of (delayed ? ["te"] : ["en", "te"])) {
      for (const cache of (delayed ? ["cold"] : ["cold", "warm"])) {
        for (const path of (delayed ? [`/story/${encodeURIComponent(first.canonical_slug)}`] : ["/", "/saved", `/story/${encodeURIComponent(first.canonical_slug)}`])) {
          const comparison = { width, language, cache, path };
          for (const [version, base] of [["before", before], ["after", after]]) {
            const context = await browser.newContext({ viewport: { width, height: 844 }, colorScheme: "light", reducedMotion: "reduce" });
            await context.addInitScript((language) => {
              localStorage.setItem("tg-theme", "light");
              localStorage.setItem("tg_onboarding_profile_v1", JSON.stringify({ lifeStages: [], topics: [], language }));
              window.__shifts = { max: 0, sum: 0, first: 0, last: 0 };
              new PerformanceObserver((list) => {
                for (const entry of list.getEntries()) {
                  if (entry.hadRecentInput) continue;
                  const value = window.__shifts;
                  if (entry.startTime - value.last > 1000 || entry.startTime - value.first > 5000) {
                    value.sum = 0; value.first = entry.startTime;
                  }
                  value.sum += entry.value; value.last = entry.startTime;
                  value.max = Math.max(value.max, value.sum);
                }
              }).observe({ type: "layout-shift", buffered: true });
            }, language);
            const page = await context.newPage();
            if (delayed) {
              await page.route(/\/_next\/static\/.*\.(js|woff2)(\?.*)?$/, async (route) => {
                await new Promise((resolve) => setTimeout(resolve, 1500));
                try { await route.continue(); }
                catch (error) { if (!page.isClosed()) throw error; }
              });
            }
            if (cache === "warm") {
              await page.goto(base, { waitUntil: "domcontentloaded" });
              await page.locator("main h1").waitFor();
              if (language === "te") await page.locator('.story-card__headline[lang="te"]').first().waitFor();
              await page.evaluate(() => document.fonts.ready);
            }
            await page.goto(new URL(path, base).href, { waitUntil: "domcontentloaded" });
            await page.locator("main h1").waitFor();
            if (path === "/saved") await page.locator(".empty-state").waitFor();
            if (language === "te" && path !== "/saved") await page.locator('.story-card__headline[lang="te"]').first().waitFor();
            await page.evaluate(() => document.fonts.ready);
            // Allow local hydration effects and queued layout observations to settle;
            // unrelated speculative prefetches need not go network-idle.
            await page.waitForTimeout(500);
            await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
            comparison[version] = await page.evaluate(() => {
              const resources = performance.getEntriesByType("resource").filter((entry) => new URL(entry.name).origin === location.origin && /\.(js|css|woff2)(\?|$)/.test(entry.name));
              const bytes = (extension) => resources.filter((entry) => entry.name.includes(extension)).reduce((sum, entry) => sum + entry.encodedBodySize, 0);
              return { cls: window.__shifts.max, htmlBytes: performance.getEntriesByType("navigation")[0]?.encodedBodySize ?? 0, jsBytes: bytes(".js"), cssBytes: bytes(".css"), fontBytes: bytes(".woff2") };
            });
            if (path === "/" && width === 390 && cache === "cold") await page.screenshot({ path: join(output, `home-${version}-${language}.png`), fullPage: true });
            await context.close();
          }
          results.push(comparison);
          console.log(`Compared ${width}px ${language} ${cache} ${path}`);
        }
      }
    }
  }
} finally { await browser.close(); }
writeFileSync(join(output, "performance.json"), JSON.stringify({ kind: "local synthetic comparison", resourceDelayMs: delayed ? 1500 : 0, results }, null, 2));
console.log(JSON.stringify({ comparisons: results.length, maxBeforeCLS: Math.max(...results.map((r) => r.before.cls)), maxAfterCLS: Math.max(...results.map((r) => r.after.cls)), output }));
