// Mirrors the "dusk-teal ground, marigold accent" palette in
// apps/web/src/app/globals.css so the mobile app reads as the same brand.
// React Native can't consume CSS custom properties, hence this JS mirror.
export const colors = {
  bg: "#eef1f0",
  surface: "#ffffff",
  surfaceSunken: "#e4e9e7",
  text: "#12262b",
  muted: "#52686a",
  // Design-review fix: #7c8c8d on `bg` was 3.08:1, failing WCAG AA (4.5:1)
  // for the normal-weight meta/timestamp text this token is used for.
  faint: "#5f7072",
  border: "#c9d2cf",

  accent: "#b8791f",
  accentStrong: "#8f5c14",
  accentContrast: "#ffffff",
  accentSoft: "#f4e6c9",
  accentInk: "#6b4712",

  // Design-review fix: #1f7d6f on `tealSoft` was 4.16:1, marginally failing
  // AA (4.5:1) for the 0.72rem/600-weight status-pill text that uses it.
  teal: "#1a6d61",
  tealSoft: "#dcefe9",

  danger: "#a3321f",
  dangerSoft: "#f7ddd6",
} as const;

export const radius = {
  sm: 6,
  md: 10,
  lg: 16,
  pill: 999,
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
} as const;

export const shadow = {
  card: {
    shadowColor: "#12262b",
    shadowOpacity: 0.12,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
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
