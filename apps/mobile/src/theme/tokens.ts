// GENERATED — DO NOT EDIT. Source: packages/design-tokens/tokens.json
export const colors = {
  bg: "#f7f8fc",
  surface: "#ffffff",
  surfaceSunken: "#eceff5",
  text: "#151827",
  muted: "#525a70",
  faint: "#6f778d",
  border: "#a8b0c2",
  rule: "#151827",
  accent: "#3657d6",
  accentStrong: "#2748b8",
  accentContrast: "#ffffff",
  accentSoft: "#e7ecff",
  accentInk: "#2343b0",
  hot: "#b42318",
  hotSoft: "#fde8e7",
  focusRing: "#3657d6",
  danger: "#b42318",
  dangerSoft: "#fde8e7",
} as const;
export const colorsDark = {
  bg: "#10131d",
  surface: "#181d2c",
  surfaceSunken: "#0a0d15",
  text: "#f4f6ff",
  muted: "#bcc3d4",
  faint: "#a0a9c1",
  border: "#66708a",
  rule: "#f4f6ff",
  accent: "#91a6ff",
  accentStrong: "#b2bfff",
  accentContrast: "#11162b",
  accentSoft: "#202958",
  accentInk: "#c7d0ff",
  hot: "#ff907f",
  hotSoft: "#341411",
  focusRing: "#91a6ff",
  danger: "#ff907f",
  dangerSoft: "#341411",
} as const;
export const colorSchemes = { light: colors, dark: colorsDark } as const;
export const ui = {
  canvas: "#f7f8fc",
  surface: "#ffffff",
  surfaceSubtle: "#eceff5",
  textPrimary: "#151827",
  textSecondary: "#525a70",
  textTertiary: "#687086",
  borderSubtle: "#d5dae5",
  borderControl: "#737d94",
  actionPrimary: "#3657d6",
  actionPrimaryHover: "#2748b8",
  actionPrimarySoft: "#e7ecff",
  actionPrimaryText: "#ffffff",
  actionText: "#2343b0",
  success: "#147a55",
  successSoft: "#e2f5ec",
  warning: "#8a5200",
  warningSoft: "#fff0ce",
  danger: "#b42318",
  dangerSoft: "#fde8e7",
} as const;
export const uiDark = {
  canvas: "#10131d",
  surface: "#181d2c",
  surfaceSubtle: "#222b42",
  textPrimary: "#f4f6ff",
  textSecondary: "#bcc3d4",
  textTertiary: "#a0a9c1",
  borderSubtle: "#3e4962",
  borderControl: "#66708a",
  actionPrimary: "#91a6ff",
  actionPrimaryHover: "#b2bfff",
  actionPrimarySoft: "#202958",
  actionPrimaryText: "#11162b",
  actionText: "#c7d0ff",
  success: "#62d3a5",
  successSoft: "#153a30",
  warning: "#f2bd61",
  warningSoft: "#3b2b12",
  danger: "#ff907f",
  dangerSoft: "#341411",
} as const;
export const uiSchemes = { light: ui, dark: uiDark } as const;
export const radius = { sm: 0, md: 2, lg: 3, pill: 0 } as const;
export const spacing = {
  "xs": 4,
  "sm": 8,
  "md": 12,
  "lg": 16,
  "xl": 24
} as const;
export const shadow = { card: { shadowColor: colors.rule, shadowOpacity: 1, shadowRadius: 0, shadowOffset: { width: 3, height: 3 }, elevation: 3 } } as const;
export const typography = { headline: { fontSize: 18, fontWeight: "700" as const, letterSpacing: -0.2, lineHeight: 22 }, body: { fontSize: 15, lineHeight: 23 }, meta: { fontSize: 12, fontWeight: "600" as const, letterSpacing: 0.4 } } as const;
export const typographyTe = { headline: { ...typography.headline, letterSpacing: -0.1, lineHeight: 24 }, body: { ...typography.body, lineHeight: 24 }, meta: typography.meta } as const;
export function typographyFor(language: "en" | "te") { return language === "te" ? typographyTe : typography; }
