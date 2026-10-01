import React, { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { getTextSize, setTextSize, type TextSize } from "../lib/storage";
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
  /** Back to "default" without writing storage (after "clear data"). */
  resetTextSize: () => void;
}

const TextSizeContext = createContext<TextSizeValue>({
  textSize: "default",
  setTextSize: () => {},
  resetTextSize: () => {},
});

export function TextSizeProvider({ children }: { children: ReactNode }) {
  const [textSize, setState] = useState<TextSize | null>(null);

  useEffect(() => {
    let active = true;
    getTextSize().then((stored) => {
      if (active) setState(stored);
    });
    return () => {
      active = false;
    };
  }, []);

  const choose = useCallback((next: TextSize) => {
    setState(next);
    setTextSize(next);
  }, []);

  const resetTextSize = useCallback(() => setState("default"), []);

  const value = useMemo(
    () => ({ textSize: textSize ?? "default", setTextSize: choose, resetTextSize }),
    [textSize, choose, resetTextSize],
  );

  // Same as the theme: wait for the stored choice so story text doesn't
  // jump size after the first frame.
  if (textSize === null) return null;
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
export function scaledStoryType(language: "en" | "te", size: TextSize): StoryType {
  const base: StoryType = typographyFor(language);
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
