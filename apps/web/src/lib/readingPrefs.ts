// P04 reading controls (web). Stored in localStorage, applied as attributes on
// <html> so CSS does the work and the pre-paint script avoids a flash.

export const READING_STORAGE_KEY = "tg-reading-v1";

export const TEXT_SIZES = ["small", "default", "large", "xlarge"] as const;
export const TELUGU_FONTS = ["default", "serif", "mandali"] as const;
export const READING_STYLES = ["full", "short"] as const;

export type TextSize = (typeof TEXT_SIZES)[number];
export type TeluguFont = (typeof TELUGU_FONTS)[number];
export type ReadingStyle = (typeof READING_STYLES)[number];
export interface ReadingPrefs { textSize: TextSize; teluguFont: TeluguFont; readingStyle: ReadingStyle }

export const DEFAULT_READING_PREFS: ReadingPrefs = { textSize: "default", teluguFont: "default", readingStyle: "full" };

function pick<T extends string>(allowed: readonly T[], value: unknown, fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

export function parseReadingPrefs(raw: string | null): ReadingPrefs {
  try {
    const parsed = raw ? JSON.parse(raw) : null;
    return {
      textSize: pick(TEXT_SIZES, parsed?.textSize, "default"),
      teluguFont: pick(TELUGU_FONTS, parsed?.teluguFont, "default"),
      readingStyle: pick(READING_STYLES, parsed?.readingStyle, "full"),
    };
  } catch {
    return { ...DEFAULT_READING_PREFS };
  }
}

export function applyReadingPrefs(prefs: ReadingPrefs): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.setAttribute("data-text-size", prefs.textSize);
  root.setAttribute("data-telugu-font", prefs.teluguFont);
  root.setAttribute("data-reading", prefs.readingStyle);
}

export function loadReadingPrefs(): ReadingPrefs {
  try {
    return parseReadingPrefs(localStorage.getItem(READING_STORAGE_KEY));
  } catch {
    return { ...DEFAULT_READING_PREFS };
  }
}

export function saveReadingPrefs(prefs: ReadingPrefs): void {
  applyReadingPrefs(prefs);
  try {
    localStorage.setItem(READING_STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // best-effort persistence only
  }
}

// Validates each field in the browser before setting attributes (mirrors parseReadingPrefs).
export const READING_INIT_SCRIPT = `(function(){try{var p=JSON.parse(localStorage.getItem(${JSON.stringify(READING_STORAGE_KEY)}))||{};var r=document.documentElement;function s(a,v,l,d){r.setAttribute(a,l.indexOf(v)>-1?v:d);}s("data-text-size",p.textSize,${JSON.stringify(TEXT_SIZES)},"default");s("data-telugu-font",p.teluguFont,${JSON.stringify(TELUGU_FONTS)},"default");s("data-reading",p.readingStyle,${JSON.stringify(READING_STYLES)},"full");}catch(e){}})();`;
