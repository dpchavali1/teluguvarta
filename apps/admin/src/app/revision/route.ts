export const dynamic = "force-dynamic";

export function GET() {
  const candidate = process.env.RELEASE_SHA ?? "";
  const revision = /^[0-9a-f]{40}$/.test(candidate) ? candidate : "unknown";
  return new Response(
    revision,
    { headers: { "Cache-Control": "no-store" } }
  );
}
