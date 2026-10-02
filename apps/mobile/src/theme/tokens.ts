// GENERATED — DO NOT EDIT. Source: packages/design-tokens/tokens.json
export const colors = {
  bg: "#f5f7fb",
  surface: "#ffffff",
  surfaceSunken: "#ebeff7",
  text: "#172033",
  muted: "#46536b",
  faint: "#5c6980",
  border: "#bec8d9",
  rule: "#25304a",
  accent: "#4b45a8",
  accentStrong: "#37338a",
  accentContrast: "#ffffff",
  accentSoft: "#e9e8ff",
  accentInk: "#332e80",
  hot: "#a54724",
  hotSoft: "#fcead9",
  focusRing: "#4b45a8",
  danger: "#a54724",
  dangerSoft: "#fcead9",
} as const;
export const colorsDark = {
  bg: "#0f1422",
  surface: "#192135",
  surfaceSunken: "#0b1020",
  text: "#f4f6fc",
  muted: "#cbd4e7",
  faint: "#acbcd3",
  border: "#47556e",
  rule: "#e8edfa",
  accent: "#b7aeff",
  accentStrong: "#d1cbff",
  accentContrast: "#1b1645",
  accentSoft: "#303060",
  accentInk: "#e0dcff",
  hot: "#ffad7c",
  hotSoft: "#3a281d",
  focusRing: "#b7aeff",
  danger: "#ffad7c",
  dangerSoft: "#3a281d",
} as const;
export const colorSchemes = { light: colors, dark: colorsDark } as const;
export const ui = {
  canvas: "#f5f7fb",
  surface: "#ffffff",
  surfaceSubtle: "#ecf0f8",
  textPrimary: "#172033",
  textSecondary: "#46536b",
  textTertiary: "#5e6b80",
  borderSubtle: "#d9e1ef",
  borderControl: "#7c8ba5",
  actionPrimary: "#4b45a8",
  actionPrimaryHover: "#37338a",
  actionPrimarySoft: "#e9e8ff",
  actionPrimaryText: "#ffffff",
  actionText: "#332e80",
  success: "#0f7652",
  successSoft: "#e2f5eb",
  warning: "#865400",
  warningSoft: "#fff0d2",
  danger: "#b12d37",
  dangerSoft: "#fde9eb",
} as const;
export const uiDark = {
  canvas: "#0f1422",
  surface: "#192135",
  surfaceSubtle: "#222d43",
  textPrimary: "#f4f6fc",
  textSecondary: "#cbd4e7",
  textTertiary: "#a9b9d1",
  borderSubtle: "#35425b",
  borderControl: "#6f819e",
  actionPrimary: "#b7aeff",
  actionPrimaryHover: "#d1cbff",
  actionPrimarySoft: "#303060",
  actionPrimaryText: "#1b1645",
  actionText: "#e0dcff",
  success: "#76d6b0",
  successSoft: "#13392c",
  warning: "#ffd178",
  warningSoft: "#3a2b17",
  danger: "#ff9a9f",
  dangerSoft: "#431f2a",
} as const;
export const uiSchemes = { light: ui, dark: uiDark } as const;
export const radius = { sm: 8, md: 8, lg: 12, card: 16, pill: 999 } as const;
export const spacing = {
  "xs": 4,
  "sm": 8,
  "md": 12,
  "lg": 16,
  "xl": 24
} as const;
export const shadow = {
  sm: { shadowColor: colors.rule, shadowOpacity: 1, shadowRadius: 0, shadowOffset: { width: 3, height: 3 }, elevation: 3, boxShadow: `3px 3px 0 ${colors.rule}` },
  card: { shadowColor: colors.rule, shadowOpacity: 1, shadowRadius: 0, shadowOffset: { width: 4, height: 4 }, elevation: 4, boxShadow: `4px 4px 0 ${colors.rule}` },
} as const;
export const duration = { fast: 120, base: 200 } as const;
export const typography = { display: { fontSize: 28, fontWeight: "700" as const, letterSpacing: -0.3, lineHeight: 32 }, headline: { fontSize: 18, fontWeight: "700" as const, letterSpacing: -0.2, lineHeight: 24 }, body: { fontSize: 15, lineHeight: 23 }, meta: { fontSize: 12, fontWeight: "600" as const, letterSpacing: 0.4 } } as const;
export const typographyTe = { display: { ...typography.display, lineHeight: 38 }, headline: { ...typography.headline, letterSpacing: -0.1, lineHeight: 26 }, body: { ...typography.body, lineHeight: 24 }, meta: typography.meta } as const;
export function typographyFor(language: "en" | "te") { return language === "te" ? typographyTe : typography; }
