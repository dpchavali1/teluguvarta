/**
 * P05 "My Edit" (ADR-040). Pure, deterministic arrangement of the stories the
 * server already ranked, using only explicit on-device signals: follows
 * (reflected in the server `personalization.explanation`), hidden topics
 * ("Show less") and saved stories. No randomness, no behavior tracking:
 * identical inputs always give identical sections.
 */

/** Sensitivities a mute can never hide (NON_NEGOTIABLES #5, ADR-040). */
export const MUTE_PROTECTED_SENSITIVITIES = ["BREAKING", "IMMIGRATION", "LEGAL", "FINANCIAL"] as const;

export type MyEditStory = {
  id: string;
  topics?: string[];
  sensitivity: string;
  /** The first source is the one the card credits; "Mute source" matches its domain. */
  sources?: { url: string }[];
  importance: number;
  published_at?: string | null;
  personalization?: { explanation?: string | null } | null;
};

export type MyEditSection<T extends MyEditStory> = {
  key: "top5" | "for-you" | "because-saved";
  title: string;
  /** Present on "Because you saved X": the saved story's headline. */
  savedHeadline?: string;
  stories: T[];
};

export const TOP_TODAY_COUNT = 5;
export const TOP_TODAY_WINDOW_HOURS = 24;
export const SAVED_SECTION_LIMIT = 2;
export const SAVED_SECTION_STORIES = 3;

export function isMuteProtected(story: Pick<MyEditStory, "sensitivity">): boolean {
  return (MUTE_PROTECTED_SENSITIVITIES as readonly string[]).includes(story.sensitivity);
}

/**
 * Lowercased host of a source URL without "www.", or null. Not `new URL()`:
 * React Native's URL doesn't implement `hostname`.
 */
export function sourceDomainOf(url: string | undefined): string | null {
  const match = /^https?:\/\/(?:[^/?#@]*@)?([^/?#:]+)/i.exec(url ?? "");
  return match ? match[1].toLowerCase().replace(/^www\./, "") : null;
}

/**
 * Drops stories on a muted topic or from a muted source (the domain of their
 * first source), except breaking/immigration/legal/financial ones.
 */
export function applyMutes<T extends MyEditStory>(
  stories: T[],
  mutedTopics: readonly string[],
  mutedSources: readonly string[] = [],
): T[] {
  if (mutedTopics.length === 0 && mutedSources.length === 0) return stories;
  return stories.filter((story) => {
    if (isMuteProtected(story)) return true;
    if ((story.topics ?? []).some((slug) => mutedTopics.includes(slug))) return false;
    const domain = sourceDomainOf(story.sources?.[0]?.url);
    return !(domain && mutedSources.includes(domain));
  });
}

function publishedMs(story: MyEditStory): number {
  const ms = story.published_at ? Date.parse(story.published_at) : NaN;
  return Number.isNaN(ms) ? 0 : ms;
}

export type SavedRef = { id: string; headline: string; topics: readonly string[] };

/**
 * `ranked` is the server's order (already shaped by follows). Sections:
 *  - Top 5 today: the most important stories from the last 24h (ties: newer, then id).
 *  - Because you saved X: unsaved stories sharing a topic with a recently saved one.
 *  - For you: everything else, keeping the server order.
 * A story appears in at most one section.
 */
export function buildMyEdit<T extends MyEditStory>(
  ranked: T[],
  options: { mutedTopics: readonly string[]; mutedSources?: readonly string[]; saved: readonly SavedRef[]; now: Date },
): MyEditSection<T>[] {
  const visible = applyMutes(ranked, options.mutedTopics, options.mutedSources);
  const used = new Set<string>();
  const sections: MyEditSection<T>[] = [];

  const cutoff = options.now.getTime() - TOP_TODAY_WINDOW_HOURS * 3600 * 1000;
  const top = visible
    .filter((s) => publishedMs(s) >= cutoff)
    .sort((a, b) => b.importance - a.importance || publishedMs(b) - publishedMs(a) || a.id.localeCompare(b.id))
    .slice(0, TOP_TODAY_COUNT);
  if (top.length > 0) {
    top.forEach((s) => used.add(s.id));
    sections.push({ key: "top5", title: "Top 5 today", stories: top });
  }

  const savedIds = new Set(options.saved.map((s) => s.id));
  for (const saved of options.saved.slice(0, SAVED_SECTION_LIMIT)) {
    const related = visible
      .filter(
        (s) => !used.has(s.id) && !savedIds.has(s.id) && (s.topics ?? []).some((t) => saved.topics.includes(t)),
      )
      .slice(0, SAVED_SECTION_STORIES);
    if (related.length === 0) continue;
    related.forEach((s) => used.add(s.id));
    sections.push({
      key: "because-saved",
      title: `Because you saved “${saved.headline}”`,
      savedHeadline: saved.headline,
      stories: related,
    });
  }

  const rest = visible.filter((s) => !used.has(s.id));
  if (rest.length > 0) sections.splice(top.length > 0 ? 1 : 0, 0, { key: "for-you", title: "For you", stories: rest });
  return sections;
}

/** "Why am I seeing this?" text for a story in a given section. */
export function whySeeing(story: MyEditStory, section: Pick<MyEditSection<MyEditStory>, "key" | "savedHeadline">): string {
  if (section.key === "because-saved") return `Because you saved “${section.savedHeadline}” and it shares a topic.`;
  const parts: string[] = [];
  const own = story.personalization?.explanation;
  if (own) parts.push(own);
  if (section.key === "top5") parts.push("It is among today's most important stories.");
  if (isMuteProtected(story)) parts.push("Breaking, immigration, legal and financial news is never hidden by a mute.");
  if (parts.length === 0) parts.push("Newest and most important first; follow topics or places to tailor this.");
  return parts.join(" ");
}
