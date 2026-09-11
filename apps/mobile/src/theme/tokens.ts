// Ported by hand from apps/web/src/app/globals.css's light-mode "Ink &
// Signal" tokens, per ADR-009's sequencing note (palette first, shared
// token source later). React Native can't consume CSS custom properties,
// hence this JS mirror — keep values identical to web's :root block.
export const colors = {
  bg: "#f2f0e8",
  surface: "#fbfaf6",
  surfaceSunken: "#e6e3d7",
  text: "#14140f",
  muted: "#52504a",
  faint: "#6e6c62",
  // Design-review fix: web's own #d8d4c6 is ~1.4:1 against both `bg` and
  // `surface`, below the 3:1 WCAG 1.4.11 floor for a UI-component boundary
  // (unselected pill/langButton borders here rely on it alone). #7f7c6f
  // clears 3:1 against both — see the matching comment in
  // apps/admin/src/app/globals.css.
  border: "#7f7c6f",
  rule: "#14140f",

  // Signal lime — fills and rules, never small text on paper.
  accent: "#c8f03f",
  accentStrong: "#b2db24",
  accentContrast: "#14140f",
  accentSoft: "#e9f7c0",
  accentInk: "#4a5c08",

  // Hot vermilion — corrections, retractions, alerts.
  hot: "#c63512",
  hotSoft: "#fbe0d8",
  danger: "#c63512",
  dangerSoft: "#fbe0d8",
} as const;

export const radius = {
  sm: 0,
  md: 2,
  lg: 3,
  pill: 0,
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
} as const;

// Hard offset shadow instead of a soft drop shadow, matching web's
// --shadow-hard. RN has no box-shadow-offset primitive, so this is the
// closest approximation: a flat, non-blurred shadow with no elevation glow.
export const shadow = {
  card: {
    shadowColor: "#14140f",
    shadowOpacity: 1,
    shadowRadius: 0,
    shadowOffset: { width: 3, height: 3 },
    elevation: 3,
  },
} as const;

export const typography = {
  headline: { fontSize: 18, fontWeight: "700" as const, letterSpacing: -0.2 },
  body: { fontSize: 15, lineHeight: 21 },
  meta: { fontSize: 12, fontWeight: "600" as const, letterSpacing: 0.4 },
} as const;

// Telugu-specific type. The Latin scale above is display-tuned with negative
// tracking (-0.2), which crowds Telugu conjunct clusters, and its 1.4x body
// leading clips the stacked vowel signs (talakattu/gunintam) that sit above
// and below the baseline — Telugu glyphs occupy a taller box than Latin at
// the same font size. These values mirror the [lang="te"] cascade in
// apps/web/src/app/globals.css: near-zero tracking and 1.2x leading on
// headings, the looser 1.55x body leading web already applies.
export const typographyTe = {
  headline: { fontSize: 18, fontWeight: "700" as const, letterSpacing: -0.1, lineHeight: 22 },
  body: { fontSize: 15, lineHeight: 23 },
  meta: { fontSize: 12, fontWeight: "600" as const, letterSpacing: 0.4 },
} as const;

/** Type scale for a story variant's language. Telugu needs its own metrics. */
export function typographyFor(language: "en" | "te") {
  return language === "te" ? typographyTe : typography;
}
