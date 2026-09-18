import { useMemo } from "react";
import { useColorScheme } from "react-native";

import { colorSchemes, uiSchemes } from "./tokens";

// Hand-written (not generated — see tokens.ts's "GENERATED" header). The
// nav chrome and every themed screen previously imported `colors`/`ui`
// directly from tokens.ts, which are the light-scheme values only, so dark
// mode never took effect anywhere in the app (ADR-014's flagged functional
// bug, not a styling gap). This is the one place that reads the system
// scheme; everything else should go through it instead of the raw exports.
export type ThemeScheme = "light" | "dark";

export interface AppTheme {
  scheme: ThemeScheme;
  colors: (typeof colorSchemes)[ThemeScheme];
  ui: (typeof uiSchemes)[ThemeScheme];
}

export function useAppTheme(): AppTheme {
  const scheme: ThemeScheme = useColorScheme() === "dark" ? "dark" : "light";
  return useMemo(() => ({ scheme, colors: colorSchemes[scheme], ui: uiSchemes[scheme] }), [scheme]);
}
