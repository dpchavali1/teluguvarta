import React, { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Appearance } from "react-native";

import { getThemePreference, setThemePreference, type ThemePreference } from "../lib/storage";

// The reader's System / Light / Dark choice (Settings → Appearance).
// useAppTheme reads it, so every screen follows without per-screen work.
// Appearance.setColorScheme also moves native chrome (alerts, keyboard,
// Android DayNight) onto the chosen scheme; "unspecified" hands it back to
// the system.

interface ThemePreferenceValue {
  preference: ThemePreference;
  setPreference: (preference: ThemePreference) => void;
  /** Back to "system" without writing storage (after "clear data"). */
  resetPreference: () => void;
}

// Outside a provider (tests, isolated renders) the app follows the system.
const ThemePreferenceContext = createContext<ThemePreferenceValue>({
  preference: "system",
  setPreference: () => {},
  resetPreference: () => {},
});

function applyNative(preference: ThemePreference) {
  // Best effort: JS colours come from useAppTheme either way, and a throw
  // here must never stop the provider from rendering the app.
  try {
    Appearance.setColorScheme?.(preference === "system" ? "unspecified" : preference);
  } catch {
    // Native module missing (tests, old OS) — native chrome keeps the system scheme.
  }
}

export function ThemePreferenceProvider({ children }: { children: ReactNode }) {
  const [preference, setState] = useState<ThemePreference | null>(null);

  useEffect(() => {
    let active = true;
    getThemePreference().then((stored) => {
      if (!active) return;
      applyNative(stored);
      setState(stored);
    });
    return () => {
      active = false;
    };
  }, []);

  const setPreference = useCallback((next: ThemePreference) => {
    applyNative(next);
    setState(next);
    setThemePreference(next);
  }, []);

  const resetPreference = useCallback(() => {
    applyNative("system");
    setState("system");
  }, []);

  const value = useMemo(
    () => ({ preference: preference ?? "system", setPreference, resetPreference }),
    [preference, setPreference, resetPreference],
  );

  // Render nothing until the stored choice is read (one AsyncStorage read),
  // so a reader who picked Light doesn't see a dark flash on every launch.
  if (preference === null) return null;
  return <ThemePreferenceContext.Provider value={value}>{children}</ThemePreferenceContext.Provider>;
}

export function useThemePreference(): ThemePreferenceValue {
  return useContext(ThemePreferenceContext);
}
