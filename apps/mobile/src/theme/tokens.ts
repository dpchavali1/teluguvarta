// Mirrors the "dusk-teal ground, marigold accent" palette in
// apps/web/src/app/globals.css so the mobile app reads as the same brand.
// React Native can't consume CSS custom properties, hence this JS mirror.
export const colors = {
  bg: "#eef1f0",
  surface: "#ffffff",
  surfaceSunken: "#e4e9e7",
  text: "#12262b",
  muted: "#52686a",
  faint: "#7c8c8d",
  border: "#c9d2cf",

  accent: "#b8791f",
  accentStrong: "#8f5c14",
  accentContrast: "#ffffff",
  accentSoft: "#f4e6c9",
  accentInk: "#6b4712",

  teal: "#1f7d6f",
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
