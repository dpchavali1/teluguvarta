// P06 / ADR-044 on the web: collections and notes for bookmarks, kept in this
// browser only (never sent to the API). Keyed by story id; no story text is
// stored. Reminders are mobile-only (they need local notifications).
import {
  EMPTY_EXTRAS, dropStory, parseExtras, type SavedExtras,
} from "@teluguvarta/domain/savedExtras.ts";

export const EXTRAS_KEY = "tg_saved_extras_v1";
export const SAVED_EXTRAS_CHANGE_EVENT = "tg:saved-extras-change";

export function readExtras(): SavedExtras {
  if (typeof window === "undefined") return EMPTY_EXTRAS;
  try {
    const raw = window.localStorage.getItem(EXTRAS_KEY);
    return raw ? parseExtras(JSON.parse(raw)) : EMPTY_EXTRAS;
  } catch {
    return EMPTY_EXTRAS;
  }
}

// Throws if storage is unavailable, so the caller can say the change wasn't kept.
export function writeExtras(extras: SavedExtras): void {
  window.localStorage.setItem(EXTRAS_KEY, JSON.stringify(extras));
  window.dispatchEvent(new Event(SAVED_EXTRAS_CHANGE_EVENT));
}

// Unsaving removes the note and collection membership with the bookmark.
export function dropStoryExtras(storyId: string): void {
  const current = readExtras();
  if (!(storyId in current.notes) && !(storyId in current.membership) && !(storyId in current.reminders)) return;
  try { writeExtras(dropStory(current, storyId)); } catch { /* the bookmark change already succeeded */ }
}
