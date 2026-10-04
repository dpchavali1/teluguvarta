import { Platform, Share } from "react-native";

import { storyUrl, type StoryVariantOut } from "./api";

// ADR-045: our own text, visible source attribution and the canonical link.
// The branded image card is web-only for now (it needs a file-sharing native
// module here); the native OS share sheet carries this text.
export function shareMessage(canonicalSlug: string, variant: StoryVariantOut, sourceUrl?: string): string {
  const lines = [variant.headline, variant.summary, ""];
  if (sourceUrl) {
    try { lines.push(`Source: ${new URL(sourceUrl).hostname.replace(/^www\./, "")}`); } catch { /* unparsable source URL: skip attribution line */ }
  }
  lines.push(storyUrl(canonicalSlug));
  return lines.join("\n");
}

export async function shareStory(canonicalSlug: string, variant: StoryVariantOut, sourceUrl?: string): Promise<void> {
  const message = shareMessage(canonicalSlug, variant, sourceUrl);
  // `Share.share`'s `url` field is iOS-only (Android reads only `message`),
  // so only include it there.
  await Share.share(Platform.OS === "ios" ? { message, url: storyUrl(canonicalSlug) } : { message });
}
