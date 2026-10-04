import { applyMutes, buildMyEdit, whySeeing } from "@teluguvarta/domain";

const now = new Date("2026-10-04T12:00:00Z");
const hoursAgo = (h: number) => new Date(now.getTime() - h * 3600 * 1000).toISOString();
const story = (id: string, over: Record<string, unknown> = {}) => ({
  id,
  topics: ["sports"],
  sensitivity: "NONE",
  importance: 0.5,
  published_at: hoursAgo(1),
  ...over,
});

test("mutes hide a topic but never breaking/immigration/legal/financial stories", () => {
  const list = [
    story("a"),
    story("b", { sensitivity: "BREAKING" }),
    story("c", { sensitivity: "IMMIGRATION" }),
    story("d", { sensitivity: "LEGAL" }),
    story("e", { sensitivity: "FINANCIAL" }),
  ];
  expect(applyMutes(list, ["sports"]).map((s) => s.id)).toEqual(["b", "c", "d", "e"]);
});

test("identical inputs give identical sections", () => {
  const list = [story("a", { importance: 0.9 }), story("b"), story("c", { topics: ["movies"] })];
  const opts = { mutedTopics: [], saved: [], now };
  expect(buildMyEdit(list, opts)).toEqual(buildMyEdit([...list], opts));
});

test("top 5 today picks the most important recent stories; a story is in one section only", () => {
  const list = [
    ...Array.from({ length: 6 }, (_, i) => story(`s${i}`, { importance: i / 10 })),
    story("old", { importance: 1, published_at: hoursAgo(48) }),
  ];
  const [top, forYou] = buildMyEdit(list, { mutedTopics: [], saved: [], now });
  expect(top.title).toBe("Top 5 today");
  expect(top.stories.map((s) => s.id)).toEqual(["s5", "s4", "s3", "s2", "s1"]);
  expect(forYou.key).toBe("for-you");
  expect(forYou.stories.map((s) => s.id)).toEqual(["s0", "old"]);
});

test("because-you-saved lists related unsaved stories and explains why", () => {
  const list = [
    story("a", { topics: ["jobs"], importance: 0.1, published_at: hoursAgo(72) }),
    story("b", { topics: ["movies"], published_at: hoursAgo(72) }),
  ];
  const sections = buildMyEdit(list, {
    mutedTopics: [],
    saved: [{ id: "x", headline: "H-1B update", topics: ["jobs"] }],
    now,
  });
  const saved = sections.find((s) => s.key === "because-saved")!;
  expect(saved.stories.map((s) => s.id)).toEqual(["a"]);
  expect(whySeeing(saved.stories[0], saved)).toContain("H-1B update");
});
