import { ApiNotFoundError, getStory, storyUrl } from "@/lib/api";
import { pathParam } from "@/lib/pathParam";
import { shareCardAllowed } from "@/lib/rateLimit";
import { renderShareCardPng } from "@/lib/renderShareCard";
import { shareCardContent } from "@/lib/shareCard";

export const runtime = "nodejs";
export const revalidate = 60;

// ADR-045: WhatsApp share card from TTE-authored text only. Missing,
// retracted/unpublished (API 404) and link-first brief stories return 404.
export async function GET(request: Request, { params }: { params: Promise<{ slug: string }> }) {
  // ADR-046 §4: bound CPU spent rendering PNGs; CDN/browser caching absorbs normal traffic.
  if (!shareCardAllowed(request.headers)) {
    return new Response("Too many requests", { status: 429, headers: { "retry-after": "60" } });
  }
  const slug = pathParam((await params).slug);
  if (slug === null) return new Response("Not found", { status: 404 });
  let story;
  try {
    story = await getStory(slug);
  } catch (err) {
    if (err instanceof ApiNotFoundError) return new Response("Not found", { status: 404 });
    throw err;
  }
  const wanted = new URL(request.url).searchParams.get("lang") === "te" ? "te" : "en";
  const card = shareCardContent(story, wanted, storyUrl(story.canonical_slug));
  if (card === null) return new Response("Not found", { status: 404 });
  return new Response(new Uint8Array(renderShareCardPng(card)), {
    headers: { "content-type": "image/png", "cache-control": "public, max-age=60, s-maxage=60" },
  });
}
