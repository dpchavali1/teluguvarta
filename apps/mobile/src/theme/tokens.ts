// GENERATED — DO NOT EDIT. Source: packages/design-tokens/tokens.json
export const colors = {
  bg: "#f6f2e8",
  surface: "#fffcf5",
  surfaceSunken: "#ece4d2",
  text: "#1c1a15",
  muted: "#524c40",
  faint: "#5c5647",
  border: "#c4b9a0",
  rule: "#1c1a15",
  accent: "#453d8f",
  accentStrong: "#332c6d",
  accentContrast: "#ffffff",
  accentSoft: "#e7e4f5",
  accentInk: "#332c6d",
  hot: "#a8431d",
  hotSoft: "#f6ddc9",
  focusRing: "#453d8f",
  danger: "#a8431d",
  dangerSoft: "#f6ddc9",
} as const;
export const colorsDark = {
  bg: "#171410",
  surface: "#211d16",
  surfaceSunken: "#0e0c09",
  text: "#f5efe1",
  muted: "#c8bfab",
  faint: "#b3aa93",
  border: "#584f3c",
  rule: "#f5efe1",
  accent: "#9c92e6",
  accentStrong: "#b7aef0",
  accentContrast: "#1a1640",
  accentSoft: "#2b2660",
  accentInk: "#cec7f5",
  hot: "#e89468",
  hotSoft: "#3c2415",
  focusRing: "#9c92e6",
  danger: "#e89468",
  dangerSoft: "#3c2415",
} as const;
export const colorSchemes = { light: colors, dark: colorsDark } as const;
export const ui = {
  canvas: "#f6f2e8",
  surface: "#fffcf5",
  surfaceSubtle: "#ece4d2",
  textPrimary: "#1c1a15",
  textSecondary: "#524c40",
  textTertiary: "#6b6455",
  borderSubtle: "#e0d7c1",
  borderControl: "#8c8168",
  actionPrimary: "#453d8f",
  actionPrimaryHover: "#332c6d",
  actionPrimarySoft: "#e7e4f5",
  actionPrimaryText: "#ffffff",
  actionText: "#332c6d",
  success: "#12744f",
  successSoft: "#dff1e6",
  warning: "#8a5200",
  warningSoft: "#fbeecd",
  danger: "#a3261e",
  dangerSoft: "#f8ded9",
} as const;
export const uiDark = {
  canvas: "#171410",
  surface: "#211d16",
  surfaceSubtle: "#2c2619",
  textPrimary: "#f5efe1",
  textSecondary: "#c8bfab",
  textTertiary: "#ada38b",
  borderSubtle: "#453d2e",
  borderControl: "#786e57",
  actionPrimary: "#9c92e6",
  actionPrimaryHover: "#b7aef0",
  actionPrimarySoft: "#2b2660",
  actionPrimaryText: "#1a1640",
  actionText: "#cec7f5",
  success: "#68d1a2",
  successSoft: "#123a2a",
  warning: "#f0bd61",
  warningSoft: "#3a2c11",
  danger: "#ff9686",
  dangerSoft: "#3c1f19",
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
export const shadow = {
  sm: { shadowColor: colors.rule, shadowOpacity: 1, shadowRadius: 0, shadowOffset: { width: 3, height: 3 }, elevation: 3, boxShadow: `3px 3px 0 ${colors.rule}` },
  card: { shadowColor: colors.rule, shadowOpacity: 1, shadowRadius: 0, shadowOffset: { width: 4, height: 4 }, elevation: 4, boxShadow: `4px 4px 0 ${colors.rule}` },
} as const;
export const duration = { fast: 120, base: 200 } as const;
export const typography = { display: { fontSize: 28, fontWeight: "700" as const, letterSpacing: -0.3, lineHeight: 32 }, headline: { fontSize: 18, fontWeight: "700" as const, letterSpacing: -0.2, lineHeight: 24 }, body: { fontSize: 15, lineHeight: 23 }, meta: { fontSize: 12, fontWeight: "600" as const, letterSpacing: 0.4 } } as const;
export const typographyTe = { display: { ...typography.display, lineHeight: 38 }, headline: { ...typography.headline, letterSpacing: -0.1, lineHeight: 26 }, body: { ...typography.body, lineHeight: 24 }, meta: typography.meta } as const;
export function typographyFor(language: "en" | "te") { return language === "te" ? typographyTe : typography; }
