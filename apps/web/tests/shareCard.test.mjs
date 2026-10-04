import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { test } from "node:test";
import { canRenderShareCard, shareCardContent, shareText } from "../src/lib/shareCard.ts";
import { renderShareCardPng, shareCardSvg, wrapLines } from "../src/lib/renderShareCard.ts";

const story = (over = {}) => ({
  format: "STORY",
  variants: {
    en: { headline: "H-1B cap season: what changes this year", summary: "s" },
    te: { headline: "అమెరికా వీసా బులెటిన్: ప్రసాద్ బద్ధీ శ్రీ మార్పులు", summary: "స" },
  },
  sources: [{ url: "https://www.example.gov/news/a", title: "SOURCE HEADLINE" }],
  ...over,
});
const link = "https://theteluguedit.com/story/x";

test("link-first briefs never get a card (source headline, ADR-045)", () => {
  assert.equal(canRenderShareCard({ format: "BRIEF" }), false);
  assert.equal(shareCardContent(story({ format: "BRIEF" }), "en", link), null);
});

test("language follows the reader, falling back to English without a Telugu variant", () => {
  assert.equal(shareCardContent(story(), "te", link).language, "te");
  assert.equal(shareCardContent(story({ variants: { en: story().variants.en } }), "te", link).language, "en");
});

test("card carries attribution domain and link, never the source title", () => {
  const card = shareCardContent(story(), "en", link);
  assert.equal(card.attribution, "example.gov");
  const svg = shareCardSvg(card);
  assert.ok(card.attribution === "example.gov" && !JSON.stringify(card).includes("SOURCE HEADLINE"));
  assert.ok(svg.includes("<path"));
});

test("text fallback has our headline, attribution and the canonical URL", () => {
  const text = shareText(story(), "en", link);
  assert.ok(text.includes("H-1B cap season") && text.includes("Source: example.gov") && text.endsWith(link));
  assert.ok(!text.includes("SOURCE HEADLINE"));
});

test("headline text never reaches the SVG as markup", () => {
  const svg = shareCardSvg({ ...shareCardContent(story(), "en", link), headline: "A <b>&</b>" });
  assert.ok(!svg.includes("<b>") && !svg.includes("<text"));
});

test("wrapping bounds lines and keeps Telugu graphemes intact", () => {
  const lines = wrapLines("ప్రసాద్ ".repeat(40), 60, 700, 1000, 3);
  assert.equal(lines.length, 3);
  assert.ok(lines[2].endsWith("…"));
});

test("renders a PNG for English and Telugu", () => {
  for (const lang of ["en", "te"]) {
    const png = renderShareCardPng(shareCardContent(story(), lang, link));
    assert.equal(png.subarray(1, 4).toString(), "PNG");
    if (process.env.SHARE_CARD_OUT) {
      mkdirSync(process.env.SHARE_CARD_OUT, { recursive: true });
      writeFileSync(`${process.env.SHARE_CARD_OUT}/card-${lang}.png`, png);
    }
  }
});
