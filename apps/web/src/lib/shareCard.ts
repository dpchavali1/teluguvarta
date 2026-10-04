import type { Language, StoryOut } from "./api";
import { sourceDomain } from "./format.ts";

export type ShareCardContent = {
  language: Language;
  headline: string;
  summary: string;
  attribution: string;
  link: string;
};

// ADR-045 (Option A): the card carries only TTE-authored text. A link-first
// brief (ADR-019) has the source's own headline, so it never gets an image;
// callers fall back to the text-only share.
export function canRenderShareCard(story: Pick<StoryOut, "format">): boolean {
  return story.format !== "BRIEF";
}

export function shareCardContent(story: StoryOut, wanted: Language, link: string): ShareCardContent | null {
  if (!canRenderShareCard(story)) return null;
  // Telugu only when a displayable Telugu variant exists; otherwise English.
  const language: Language = wanted === "te" && story.variants.te ? "te" : "en";
  const variant = story.variants[language];
  if (!variant) return null;
  const first = story.sources[0];
  return {
    language,
    headline: variant.headline,
    summary: variant.summary,
    attribution: first ? sourceDomain(first.url) : "",
    link,
  };
}

// Text fallback shared alongside (or instead of) the card: our text,
// visible attribution, canonical URL.
export function shareText(story: StoryOut, language: Language, link: string): string {
  const variant = story.variants[language] ?? story.variants.en;
  const first = story.sources[0];
  const lines = [variant?.headline ?? "", ""];
  if (first) lines.push(`Source: ${sourceDomain(first.url)}`);
  lines.push(link);
  return lines.join("\n").trim();
}

// Browser-side: fetch the card as a File for the Web Share API. Any failure
// returns null so the caller shares text only.
export async function fetchCardFile(canonicalSlug: string, language: Language): Promise<File | null> {
  try {
    const response = await fetch(`/story/${encodeURIComponent(canonicalSlug)}/card?lang=${language}`, { signal: AbortSignal.timeout(4000) });
    if (!response.ok) return null;
    return new File([await response.blob()], "the-telugu-edit.png", { type: "image/png" });
  } catch {
    return null;
  }
}
