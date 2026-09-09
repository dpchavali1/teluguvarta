import { Platform, Share } from "react-native";

import { storyUrl, type StoryVariantOut } from "./api";

// ADR-002: text-only, always a visible link to the original — no branded
// Share Card image. The native OS share sheet (RN's `Share` module) is the
// literal T15 acceptance criterion ("use the native OS share sheet"); unlike
// web there's no clipboard-fallback path to reason about, since every iOS/
// Android device has a system share sheet.
export async function shareStory(canonicalSlug: string, variant: StoryVariantOut): Promise<void> {
  const url = storyUrl(canonicalSlug);
  const message = `${variant.headline}\n\n${variant.summary}\n\n${url}`;
  // `Share.share`'s `url` field is iOS-only (Android reads only `message`),
  // so only include it there.
  await Share.share(Platform.OS === "ios" ? { message, url } : { message });
}
