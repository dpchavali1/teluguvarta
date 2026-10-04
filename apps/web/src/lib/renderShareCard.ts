import { readFileSync } from "node:fs";
import path from "node:path";
import { Resvg } from "@resvg/resvg-js";
import * as hb from "harfbuzzjs";

import type { ShareCardContent } from "./shareCard";

// Why HarfBuzz outlines + resvg: next/og (satori) and resvg's own text engine
// both mis-shape Telugu conjuncts / vowel signs (overlapping or split glyphs).
// HarfBuzz shapes correctly; we draw its glyph outlines as SVG paths and let
// resvg only rasterize. No text elements, so no font loading in resvg.

const WIDTH = 1200;
const HEIGHT = 630;
const PAD = 64;
const MAX_LINES = 5;
const FONT_DIR = path.join(process.cwd(), "src/assets");

type Weight = 400 | 700;
type Shaped = { width: number; paths: { d: string; x: number }[] };
type Face = { font: hb.Font; upem: number };

const faces = new Map<string, Face>();
function face(file: string): Face {
  let cached = faces.get(file);
  if (!cached) {
    const data = readFileSync(path.join(FONT_DIR, file));
    const f = new hb.Face(new hb.Blob(data));
    cached = { font: new hb.Font(f), upem: f.upem };
    faces.set(file, cached);
  }
  return cached;
}

const LATIN: Record<Weight, string> = { 400: "NotoSans_400Regular.ttf", 700: "NotoSans_700Bold.ttf" };
const TELUGU: Record<Weight, string> = { 400: "NotoSansTelugu-Regular.ttf", 700: "NotoSansTelugu-Bold.ttf" };

const isTeluguChar = (ch: string) => /[ఀ-౿]/u.test(ch);
// ZWJ/ZWNJ must stay inside the Telugu run they belong to.
const isJoiner = (ch: string) => ch === "‍" || ch === "‌";

export function splitRuns(text: string): { telugu: boolean; text: string }[] {
  const runs: { telugu: boolean; text: string }[] = [];
  for (const ch of text) {
    const telugu = isTeluguChar(ch) || (isJoiner(ch) && runs.at(-1)?.telugu === true);
    const last = runs.at(-1);
    if (last && last.telugu === telugu) last.text += ch;
    else runs.push({ telugu, text: ch });
  }
  return runs;
}

function shapeRun(text: string, telugu: boolean, weight: Weight, size: number, startX: number): Shaped {
  const { font, upem } = face((telugu ? TELUGU : LATIN)[weight]);
  const scale = size / upem;
  const buffer = new hb.Buffer();
  buffer.addText(text);
  buffer.guessSegmentProperties();
  hb.shape(font, buffer);
  const infos = buffer.getGlyphInfos();
  const positions = buffer.getGlyphPositions();
  let pen = 0;
  const paths: Shaped["paths"] = [];
  infos.forEach((info, i) => {
    const pos = positions[i]!;
    const d = font.glyphToPath(info.codepoint);
    if (d) paths.push({ d, x: startX + (pen + pos.xOffset) * scale });
    pen += pos.xAdvance;
  });
  return { width: pen * scale, paths };
}

export function shapeLine(text: string, weight: Weight, size: number, startX = 0): Shaped {
  let x = startX;
  const paths: Shaped["paths"] = [];
  for (const run of splitRuns(text)) {
    const shaped = shapeRun(run.text, run.telugu, weight, size, x);
    paths.push(...shaped.paths);
    x += shaped.width;
  }
  return { width: x - startX, paths };
}

export function measure(text: string, weight: Weight, size: number): number {
  return shapeLine(text, weight, size).width;
}

// Greedy word wrap; a single over-long word is split by grapheme.
export function wrapLines(text: string, size: number, weight: Weight, maxWidth: number, maxLines: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  const fits = (candidate: string) => measure(candidate, weight, size) <= maxWidth;
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (fits(candidate)) { current = candidate; continue; }
    if (current) lines.push(current);
    current = word;
    if (!fits(current)) {
      const graphemes = Array.from(new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(word), (s) => s.segment);
      let piece = "";
      for (const g of graphemes) {
        if (fits(piece + g)) { piece += g; } else { lines.push(piece); piece = g; }
      }
      current = piece;
    }
  }
  if (current) lines.push(current);
  if (lines.length <= maxLines) return lines;
  const kept = lines.slice(0, maxLines);
  kept[maxLines - 1] = `${kept[maxLines - 1]}…`;
  return kept;
}

function textPaths(text: string, weight: Weight, size: number, x: number, y: number, fill: string): string {
  const scaleOf = (telugu: boolean) => size / face((telugu ? TELUGU : LATIN)[weight]).upem;
  let cursor = x;
  let out = "";
  for (const run of splitRuns(text)) {
    const shaped = shapeRun(run.text, run.telugu, weight, size, cursor);
    const s = scaleOf(run.telugu);
    for (const p of shaped.paths) out += `<path transform="translate(${p.x.toFixed(2)} ${y}) scale(${s} ${-s})" d="${p.d}"/>`;
    cursor += shaped.width;
  }
  return `<g fill="${fill}">${out}</g>`;
}

export function shareCardSvg(card: ShareCardContent): string {
  const size = card.headline.length > 90 ? 50 : 60;
  const lineHeight = Math.round(size * 1.45);
  const lines = wrapLines(card.headline, size, 700, WIDTH - PAD * 2, MAX_LINES);
  const headline = lines.map((line, i) => textPaths(line, 700, size, PAD, 190 + i * lineHeight, "#1b1b1b")).join("");
  const attribution = card.attribution
    ? textPaths(`Source: ${card.attribution}`, 400, 28, PAD, HEIGHT - PAD - 40, "#444444")
    : "";
  const link = card.link.replace(/^https?:\/\//, "");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}">
<rect width="${WIDTH}" height="${HEIGHT}" fill="#fffaf0"/>
${textPaths("The Telugu Edit", 700, 32, PAD, PAD + 30, "#9a3412")}${headline}${attribution}
${textPaths(link, 700, 28, PAD, HEIGHT - PAD, "#1b1b1b")}
</svg>`;
}

export function renderShareCardPng(card: ShareCardContent): Buffer {
  return new Resvg(shareCardSvg(card)).render().asPng();
}
