#!/usr/bin/env node
// ADR-014 step 5: cross-surface visual regression pass for the web surface.
// Runs in a real browser (Playwright Chromium) against a server already
// started with `next start` (or `next dev`) at VR_BASE_URL, so unlike
// a11y-check.mjs it sees actual layout. For every page × viewport × color
// scheme it saves a screenshot and asserts layout invariants that a human
// reviewer would otherwise have to eyeball:
//   - no horizontal page scroll and no visible element past the right edge
//   - on home, the StoryLead headline is above the fold
//   - the same holds with every headline replaced by a long Telugu string
// then walks the four ADR-014 user journeys: first-story visibility, topic
// discovery, language switching, and save/reopen.
//
// Screenshots are written to VR_OUT_DIR (default: a temp dir) for review;
// the pass/fail checks are what gate the exit code. The long-Telugu case
// rewrites headlines in the rendered DOM only — no data is changed.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE_URL = process.env.VR_BASE_URL ?? "http://localhost:3000";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const OUT_DIR = process.env.VR_OUT_DIR ?? join(tmpdir(), "teluguvarta-visual-regression");

// 200% zoom is emulated the way a browser applies it: a 1280×800 window at
// 200% lays out as a 640×400 CSS-pixel viewport at device scale factor 2.
const VIEWPORTS = [
  { name: "390", width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  { name: "768", width: 768, height: 1024, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  { name: "desktop", width: 1440, height: 900, deviceScaleFactor: 1 },
  { name: "zoom200", width: 640, height: 400, deviceScaleFactor: 2 },
];
const SCHEMES = ["light", "dark"];
const LONG_TELUGU_HEADLINE =
  "అమెరికాలో నివసిస్తున్న తెలుగు విద్యార్థులు మరియు ఉద్యోగుల కోసం హెచ్-1బి వీసా దరఖాస్తు రుసుము మార్పులు, కొత్త గడువు తేదీలు మరియు అంతర్జాతీయ ప్రయాణ నిబంధనలపై పూర్తి వివరణ";

const failures = [];
function check(ok, label) {
  console.log(`${ok ? "OK  " : "FAIL"} ${label}`);
  if (!ok) failures.push(label);
}

async function discoverPaths() {
  const stories = await (await fetch(new URL("/v1/stories?limit=1", API_URL))).json();
  const config = await (await fetch(new URL("/v1/config", API_URL))).json();
  const paths = ["/", "/topics", "/search", "/saved"];
  const storySlug = stories.items?.[0]?.canonical_slug;
  const topicSlug = config.topics?.[0]?.slug;
  if (storySlug) paths.push(`/story/${storySlug}`);
  else console.warn("No published story found — skipping story page (seed one with `pnpm run seed`).");
  if (topicSlug) paths.push(`/topic/${topicSlug}`);
  return paths;
}

// Visible elements whose box extends past the viewport's right edge, plus
// whether the document itself scrolls horizontally. Visually-hidden
// (clip/1px) helpers are skipped — they're off-screen by design.
async function overflowReport(page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const pageScrolls = document.documentElement.scrollWidth > vw + 1;
    const offenders = [];
    for (const el of document.body.querySelectorAll("*")) {
      const style = getComputedStyle(el);
      if (style.visibility === "hidden" || style.display === "none" || style.position === "fixed") continue;
      const rect = el.getBoundingClientRect();
      if (rect.width <= 1 || rect.height <= 1) continue;
      if (rect.right > vw + 1) {
        // Ignore children of a container that deliberately scrolls sideways (e.g. a topic rail).
        let scroller = el.parentElement;
        let insideScroller = false;
        while (scroller && scroller !== document.body) {
          const ox = getComputedStyle(scroller).overflowX;
          if (ox === "auto" || ox === "scroll" || ox === "hidden") { insideScroller = true; break; }
          scroller = scroller.parentElement;
        }
        if (!insideScroller) offenders.push(`${el.tagName.toLowerCase()}.${[...el.classList].join(".")} right=${Math.round(rect.right)}`);
      }
    }
    return { pageScrolls, offenders: offenders.slice(0, 5) };
  });
}

async function leadAboveFold(page) {
  return page.evaluate(() => {
    const headline = document.querySelector(".front-grid__lead .story-card__headline");
    if (!headline) return null;
    return headline.getBoundingClientRect().top < window.innerHeight;
  });
}

async function injectLongTelugu(page) {
  await page.evaluate((text) => {
    for (const h of document.querySelectorAll(".story-card__headline")) {
      const target = h.querySelector("a") ?? h;
      target.textContent = text;
      h.setAttribute("lang", "te");
    }
  }, LONG_TELUGU_HEADLINE);
}

async function assertLayout(page, label, isHome) {
  const { pageScrolls, offenders } = await overflowReport(page);
  check(!pageScrolls && offenders.length === 0, `${label} — no horizontal overflow${offenders.length ? ` (${offenders.join("; ")})` : ""}`);
  if (isHome) {
    const above = await leadAboveFold(page);
    check(above !== false, `${label} — lead headline above the fold${above === null ? " (no lead story)" : ""}`);
  }
}

async function matrix(browser, paths) {
  for (const vp of VIEWPORTS) {
    for (const scheme of SCHEMES) {
      const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: vp.deviceScaleFactor, isMobile: vp.isMobile, hasTouch: vp.hasTouch, colorScheme: scheme });
      const page = await context.newPage();
      for (const path of paths) {
        await page.goto(new URL(path, BASE_URL).toString(), { waitUntil: "networkidle" });
        const slug = path === "/" ? "home" : path.replace(/^\//, "").replace(/\//g, "_").slice(0, 40);
        const label = `${path} @${vp.name}/${scheme}`;
        await page.screenshot({ path: join(OUT_DIR, `${slug}--${vp.name}--${scheme}.png`), fullPage: true });
        await assertLayout(page, label, path === "/");
        if (path === "/" || path.startsWith("/story/")) {
          await injectLongTelugu(page);
          await page.screenshot({ path: join(OUT_DIR, `${slug}--${vp.name}--${scheme}--long-te.png`), fullPage: true });
          await assertLayout(page, `${label} long-Telugu`, path === "/");
        }
      }
      await context.close();
    }
  }
}

async function journeys(browser) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const page = await context.newPage();

  // 1. First-story visibility: a first-time visitor sees a real story without scrolling or logging in.
  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  check((await leadAboveFold(page)) === true, "journey: first story visible above the fold on first visit (390px)");

  // 2. Topic discovery: primary nav → topic index → a topic page with a heading and content/empty state.
  // At phone width the primary nav is the bottom tab bar (ADR-017); the header link row is desktop-only.
  await page.getByRole("navigation", { name: "Quick navigation" }).getByRole("link", { name: "Topics" }).click();
  await page.waitForURL(/\/topics$/);
  await page.locator("main h1").waitFor();
  const topicLink = page.locator('main a[href^="/topic/"]').first();
  check((await topicLink.count()) > 0, "journey: topic index lists at least one topic");
  if (await topicLink.count()) {
    await topicLink.click();
    await page.waitForURL(/\/topic\//);
    // The route streams a skeleton (loading.tsx) first; wait for the real page.
    await page.locator("main h1").waitFor();
    const hasContent = (await page.locator(".story-grid li, .empty-state").count()) > 0;
    check((await page.locator("h1").count()) === 1 && hasContent, "journey: topic page renders a heading and stories or an empty state");
  }

  // 3. Language switching: the edition-level toggle flips cards with a Telugu variant and survives reload.
  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  await page.locator(".language-toggle button[lang=te]").click();
  const teHeadlines = page.locator('.story-card__headline[lang="te"]');
  await page.waitForTimeout(200);
  const teCount = await teHeadlines.count();
  check(teCount > 0, `journey: switching to Telugu renders Telugu headlines (${teCount})`);
  await page.reload({ waitUntil: "networkidle" });
  check((await page.locator('.language-toggle button[lang=te]').getAttribute("aria-pressed")) === "true" && (await teHeadlines.count()) === teCount, "journey: Telugu preference persists across reload");
  await page.locator(".language-toggle button").first().click();

  // 4. Save/reopen: save a story from the feed, find it in Saved after a reload, open it.
  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  const saveButton = page.locator(".story-card__action--save").first();
  const savedLabel = (await saveButton.getAttribute("aria-label"))?.replace(/^Save: /, "");
  await saveButton.click();
  check((await saveButton.getAttribute("aria-pressed")) === "true", "journey: Save toggles to pressed");
  await page.goto(new URL("/saved", BASE_URL).toString(), { waitUntil: "networkidle" });
  await page.reload({ waitUntil: "networkidle" });
  const savedCard = page.locator(".story-grid .story-card__headline", { hasText: savedLabel ?? "" }).first();
  check(Boolean(savedLabel) && (await savedCard.count()) === 1, "journey: saved story appears in Saved after reload");
  if (await savedCard.count()) {
    await savedCard.locator("a").click();
    await page.waitForURL(/\/story\//);
    check((await page.locator("h1").textContent())?.trim() === savedLabel, "journey: reopening the saved story lands on its detail page");
  }

  await context.close();
}

async function main() {
  mkdirSync(OUT_DIR, { recursive: true });
  const paths = await discoverPaths();
  const browser = await chromium.launch();
  try {
    await matrix(browser, paths);
    await journeys(browser);
  } finally {
    await browser.close();
  }
  console.log(`\nScreenshots: ${OUT_DIR}`);
  if (failures.length) {
    console.error(`FAILED: ${failures.length} check(s).`);
    process.exit(1);
  }
  console.log("PASSED: all visual regression checks.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
