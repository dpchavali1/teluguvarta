// §3.3: "save (local or account-backed depending on auth state)". The
// public site has no account system yet (NON_NEGOTIABLES #9 — browsing,
// and therefore saving, works without login), so V1 saves live in the
// viewer's own browser; swapping in an account-backed store later is a
// pure addition, not a breaking change to this API.
const STORAGE_KEY = "tg_saved_stories";

function readAll(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === "string") : [];
  } catch {
    return [];
  }
}

export const SAVED_CHANGE_EVENT = "tg:saved-change";

function writeAll(ids: string[]): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  window.dispatchEvent(new Event(SAVED_CHANGE_EVENT));
}

export function isSaved(storyId: string): boolean {
  return readAll().includes(storyId);
}

export function toggleSaved(storyId: string): boolean {
  const ids = readAll();
  const index = ids.indexOf(storyId);
  if (index === -1) {
    ids.push(storyId);
    writeAll(ids);
    return true;
  }
  ids.splice(index, 1);
  writeAll(ids);
  return false;
}

export function getSavedIds(): string[] {
  return readAll();
}
