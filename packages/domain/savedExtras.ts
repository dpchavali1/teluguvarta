// P06 / ADR-044: collections, notes and read-later reminders for bookmarked
// stories. Keyed by story id only; no story text is stored. Device-only.
export const MAX_COLLECTIONS = 20;
export const MAX_COLLECTION_NAME = 40;
export const MAX_NOTE_LENGTH = 500;

export type Collection = { id: string; name: string };
export type Reminder = { at: number; notificationId: string };
export type SavedExtras = {
  collections: Collection[];
  membership: Record<string, string[]>; // story id -> collection ids
  notes: Record<string, string>;
  reminders: Record<string, Reminder>;
};

export const EMPTY_EXTRAS: SavedExtras = { collections: [], membership: {}, notes: {}, reminders: {} };

export function parseExtras(raw: unknown): SavedExtras {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return EMPTY_EXTRAS;
  const r = raw as Record<string, unknown>;
  const collections = (Array.isArray(r.collections) ? r.collections : [])
    .filter((c): c is Collection => !!c && typeof (c as Collection).id === "string" && typeof (c as Collection).name === "string")
    .slice(0, MAX_COLLECTIONS);
  const ids = new Set(collections.map((c) => c.id));
  const membership: SavedExtras["membership"] = {};
  for (const [story, list] of Object.entries((r.membership ?? {}) as Record<string, unknown>)) {
    if (!Array.isArray(list)) continue;
    const kept = list.filter((id): id is string => typeof id === "string" && ids.has(id));
    if (kept.length) membership[story] = kept;
  }
  const notes: SavedExtras["notes"] = {};
  for (const [story, note] of Object.entries((r.notes ?? {}) as Record<string, unknown>)) {
    if (typeof note === "string" && note) notes[story] = note.slice(0, MAX_NOTE_LENGTH);
  }
  const reminders: SavedExtras["reminders"] = {};
  for (const [story, rem] of Object.entries((r.reminders ?? {}) as Record<string, unknown>)) {
    const x = rem as Reminder;
    if (x && typeof x.at === "number" && typeof x.notificationId === "string") reminders[story] = { at: x.at, notificationId: x.notificationId };
  }
  return { collections, membership, notes, reminders };
}

export function addCollection(extras: SavedExtras, name: string, id: string): SavedExtras {
  const clean = name.trim().slice(0, MAX_COLLECTION_NAME);
  if (!clean || extras.collections.length >= MAX_COLLECTIONS) return extras;
  if (extras.collections.some((c) => c.name.toLowerCase() === clean.toLowerCase())) return extras;
  return { ...extras, collections: [...extras.collections, { id, name: clean }] };
}

export function deleteCollection(extras: SavedExtras, collectionId: string): SavedExtras {
  const membership: SavedExtras["membership"] = {};
  for (const [story, list] of Object.entries(extras.membership)) {
    const kept = list.filter((id) => id !== collectionId);
    if (kept.length) membership[story] = kept;
  }
  return { ...extras, collections: extras.collections.filter((c) => c.id !== collectionId), membership };
}

export function toggleMembership(extras: SavedExtras, storyId: string, collectionId: string): SavedExtras {
  if (!extras.collections.some((c) => c.id === collectionId)) return extras;
  const current = extras.membership[storyId] ?? [];
  const next = current.includes(collectionId) ? current.filter((id) => id !== collectionId) : [...current, collectionId];
  const membership = { ...extras.membership };
  if (next.length) membership[storyId] = next;
  else delete membership[storyId];
  return { ...extras, membership };
}

export function setNote(extras: SavedExtras, storyId: string, note: string): SavedExtras {
  const notes = { ...extras.notes };
  const clean = note.trim().slice(0, MAX_NOTE_LENGTH);
  if (clean) notes[storyId] = clean;
  else delete notes[storyId];
  return { ...extras, notes };
}

export function setReminder(extras: SavedExtras, storyId: string, reminder: Reminder | null): SavedExtras {
  const reminders = { ...extras.reminders };
  if (reminder) reminders[storyId] = reminder;
  else delete reminders[storyId];
  return { ...extras, reminders };
}

// Unsaving removes everything attached to the bookmark.
export function dropStory(extras: SavedExtras, storyId: string): SavedExtras {
  const { [storyId]: _m, ...membership } = extras.membership;
  const { [storyId]: _n, ...notes } = extras.notes;
  const { [storyId]: _r, ...reminders } = extras.reminders;
  return { ...extras, membership, notes, reminders };
}

export function idsInCollection(extras: SavedExtras, savedIds: string[], collectionId: string): string[] {
  return savedIds.filter((id) => extras.membership[id]?.includes(collectionId));
}

export const REMINDER_PRESETS = [
  { label: "Tomorrow morning", days: 1 },
  { label: "In 3 days", days: 3 },
  { label: "Next week", days: 7 },
] as const;

export function reminderTime(now: Date, days: number): number {
  const d = new Date(now);
  d.setDate(d.getDate() + days);
  d.setHours(8, 0, 0, 0);
  return d.getTime();
}
