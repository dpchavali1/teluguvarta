import React, { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import * as Font from "expo-font";
import { Mandali_400Regular } from "@expo-google-fonts/mandali";
import { NotoSerifTelugu_400Regular, NotoSerifTelugu_700Bold } from "@expo-google-fonts/noto-serif-telugu";

import {
  getReadingStyle,
  getTeluguFont,
  getTextSize,
  setReadingStyle,
  setTeluguFont,
  setTextSize,
  type ReadingStyle,
  type TeluguFont,
  type TextSize,
} from "../lib/storage";
import { typography, typographyFor } from "./tokens";

// The reader's text size for story text (Settings → Text size): headline,
// summary and "why this matters" on cards and the story page. Chrome
// (buttons, labels, tabs) stays put. React Native already applies the
// phone's font scale to every fontSize, so this multiplier sits on top of it.

export const TEXT_SIZE_SCALE: Record<TextSize, number> = {
  small: 0.9,
  default: 1,
  large: 1.15,
  xlarge: 1.3,
};

interface TextSizeValue {
  textSize: TextSize;
  setTextSize: (size: TextSize) => void;
  /** Telugu typeface chosen in Settings (may still be loading). */
  teluguFont: TeluguFont;
  /** The chosen font once its files are loaded, else "system". Use this to style text. */
  activeTeluguFont: TeluguFont;
  setTeluguFont: (font: TeluguFont) => void;
  readingStyle: ReadingStyle;
  setReadingStyle: (style: ReadingStyle) => void;
  /** Back to defaults without writing storage (after "clear data"). */
  resetTextSize: () => void;
}

const TextSizeContext = createContext<TextSizeValue>({
  textSize: "default",
  setTextSize: () => {},
  teluguFont: "system",
  activeTeluguFont: "system",
  setTeluguFont: () => {},
  readingStyle: "full",
  setReadingStyle: () => {},
  resetTextSize: () => {},
});

// Font family names registered with expo-font. Bold has its own family on
// Android, so a bold style uses it with a normal weight (no double bolding).
const FONT_FILES: Record<Exclude<TeluguFont, "system">, Record<string, number>> = {
  serif: { NotoSerifTelugu_400Regular, NotoSerifTelugu_700Bold },
  mandali: { Mandali_400Regular },
};

export function TextSizeProvider({ children }: { children: ReactNode }) {
  const [textSize, setState] = useState<TextSize | null>(null);
  const [teluguFont, setFontState] = useState<TeluguFont | null>(null);
  const [loadedFont, setLoadedFont] = useState<TeluguFont>("system");
  const [readingStyle, setStyleState] = useState<ReadingStyle | null>(null);

  useEffect(() => {
    let active = true;
    getTextSize().then((stored) => {
      if (active) setState(stored);
    });
    getTeluguFont().then((stored) => {
      if (active) setFontState(stored);
    });
    getReadingStyle().then((stored) => {
      if (active) setStyleState(stored);
    });
    return () => {
      active = false;
    };
  }, []);

  // Load the chosen font's files; until they are ready (or if loading fails)
  // story text keeps the phone's Telugu font.
  useEffect(() => {
    if (teluguFont === null) return;
    if (teluguFont === "system") {
      setLoadedFont("system");
      return;
    }
    let active = true;
    Font.loadAsync(FONT_FILES[teluguFont])
      .then(() => {
        if (active) setLoadedFont(teluguFont);
      })
      .catch(() => {
        if (active) setLoadedFont("system");
      });
    return () => {
      active = false;
    };
  }, [teluguFont]);

  const choose = useCallback((next: TextSize) => {
    setState(next);
    setTextSize(next);
  }, []);

  const chooseFont = useCallback((next: TeluguFont) => {
    setFontState(next);
    setTeluguFont(next);
  }, []);

  const chooseStyle = useCallback((next: ReadingStyle) => {
    setStyleState(next);
    setReadingStyle(next);
  }, []);

  const resetTextSize = useCallback(() => {
    setState("default");
    setFontState("system");
    setStyleState("full");
  }, []);

  const value = useMemo(
    () => ({
      textSize: textSize ?? "default",
      setTextSize: choose,
      teluguFont: teluguFont ?? "system",
      activeTeluguFont: teluguFont === loadedFont ? loadedFont : "system",
      setTeluguFont: chooseFont,
      readingStyle: readingStyle ?? "full",
      setReadingStyle: chooseStyle,
      resetTextSize,
    }),
    [textSize, choose, teluguFont, loadedFont, chooseFont, readingStyle, chooseStyle, resetTextSize],
  );

  // Same as the theme: wait for the stored choice so story text doesn't
  // jump size after the first frame.
  if (textSize === null || teluguFont === null || readingStyle === null) return null;
  return <TextSizeContext.Provider value={value}>{children}</TextSizeContext.Provider>;
}

export function useTextSize(): TextSizeValue {
  return useContext(TextSizeContext);
}

// The tokens are `as const` literals; scaled sizes are plain numbers.
type Widen<T> = { [K in keyof T]: T[K] extends number ? number : T[K] };
type StoryType = { [K in keyof typeof typography]: Widen<(typeof typography)[K]> };

/**
 * Story typography for a language at the reader's text size. Line heights
 * scale with the font so each language keeps its own tuned leading; Telugu
 * rounds up, because its stacked vowel signs clip before Latin descenders do.
 */
export function scaledStoryType(language: "en" | "te", size: TextSize, font: TeluguFont = "system"): StoryType {
  const base: StoryType = withTeluguFont(typographyFor(language), language === "te" ? font : "system");
  const factor = TEXT_SIZE_SCALE[size];
  if (factor === 1) return base;
  const leading = language === "te" ? Math.ceil : Math.round;
  const scale = <T extends { fontSize: number; lineHeight: number }>(style: T): T => ({
    ...style,
    fontSize: Math.round(style.fontSize * factor),
    lineHeight: leading(style.lineHeight * factor),
  });
  return { ...base, display: scale(base.display), headline: scale(base.headline), body: scale(base.body) };
}

// Telugu glyphs are wider and taller than the phone font's; the serif and
// Mandali faces get a little extra leading so stacked vowel signs don't clip.
function withTeluguFont(base: StoryType, font: TeluguFont): StoryType {
  if (font === "system") return base;
  const bold = font === "serif" ? "NotoSerifTelugu_700Bold" : "Mandali_400Regular";
  const regular = font === "serif" ? "NotoSerifTelugu_400Regular" : "Mandali_400Regular";
  const face = <T extends { fontSize: number; lineHeight: number }>(style: T, fontFamily: string, keepWeight: boolean): T => ({
    ...style,
    fontFamily,
    lineHeight: Math.ceil(style.lineHeight * 1.08),
    ...(keepWeight ? {} : { fontWeight: "400" as const }),
  });
  // Mandali has one weight: headlines keep fontWeight 700 (synthetic bold).
  const keep = font === "mandali";
  return {
    ...base,
    display: face(base.display, bold, keep),
    headline: face(base.headline, bold, keep),
    body: face(base.body, regular, true),
  };
}
