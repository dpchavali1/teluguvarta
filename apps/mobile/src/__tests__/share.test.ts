import { shareMessage } from "../lib/share";

const variant = { headline: "Headline", summary: "Summary" } as never;

describe("shareMessage", () => {
  it("has our text, source attribution and the canonical link", () => {
    const text = shareMessage("slug-1", variant, "https://www.example.gov/a");
    expect(text).toContain("Headline");
    expect(text).toContain("Source: example.gov");
    expect(text).toMatch(/\/story\/slug-1$/);
  });
  it("skips attribution for a missing or invalid source URL", () => {
    expect(shareMessage("s", variant)).not.toContain("Source:");
    expect(shareMessage("s", variant, "not a url")).not.toContain("Source:");
  });
});
