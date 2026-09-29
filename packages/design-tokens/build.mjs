import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const tokens = JSON.parse(readFileSync(path.join(root, "packages/design-tokens/tokens.json"), "utf8"));
const check = process.argv.includes("--check");

const kebab = (value) => value.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);
const cssValues = (scheme) => Object.entries(tokens.color[scheme]).map(([key, value]) => `  --color-${kebab(key)}: ${value};`).join("\n");
const cssSemantic = (scheme) => Object.entries(tokens.semantic[scheme]).map(([key, value]) => `  --${kebab(key)}: ${value};`).join("\n");
const css = `/* GENERATED — DO NOT EDIT. Source: packages/design-tokens/tokens.json */
:root {
  color-scheme: light;
${cssValues("light")}
${cssSemantic("light")}
  --color-danger: var(--color-hot);
  --color-danger-soft: var(--color-hot-soft);
  --focus-ring: var(--color-focus-ring);
  --shadow-hard: ${tokens.shadow.md}px ${tokens.shadow.md}px 0 var(--color-rule);
  --shadow-hard-sm: ${tokens.shadow.sm}px ${tokens.shadow.sm}px 0 var(--color-rule);
  --radius-md: ${tokens.radius.md}px;
  --radius-lg: ${tokens.radius.lg}px;
  --radius-card: ${tokens.radius.card}px;
  --radius-pill: ${tokens.radius.pill}px;
  --space-xs: ${tokens.spacing.xs}px;
  --space-sm: ${tokens.spacing.sm}px;
  --space-md: ${tokens.spacing.md}px;
  --space-lg: ${tokens.spacing.lg}px;
  --space-xl: ${tokens.spacing.xl}px;
  --ease-out: ${tokens.motion.easeOut};
  --duration-fast: ${tokens.motion.duration.fast}ms;
  --duration-base: ${tokens.motion.duration.base}ms;
  --font-sans-fallback: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-body: var(--font-sans), var(--font-sans-fallback);
  --font-heading: var(--font-display), var(--font-sans), var(--font-sans-fallback);
  --font-mono-stack: var(--font-mono), "SFMono-Regular", Consolas, monospace;
  --font-te: var(--font-telugu), var(--font-body);
  --font-te-heading: var(--font-telugu-display), var(--font-telugu), var(--font-heading);
}

@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark;
${cssValues("dark")}
${cssSemantic("dark")}
} }

:root[data-theme="dark"] { color-scheme: dark;
${cssValues("dark")}
${cssSemantic("dark")}
}
`;
const rnColors = (scheme) => Object.entries(tokens.color[scheme]).map(([key, value]) => `  ${key}: "${value}",`).join("\n");
const rnSemantic = (scheme) => Object.entries(tokens.semantic[scheme]).map(([key, value]) => `  ${key}: "${value}",`).join("\n");
const rn = `// GENERATED — DO NOT EDIT. Source: packages/design-tokens/tokens.json
export const colors = {\n${rnColors("light")}\n  danger: "${tokens.color.light.hot}",\n  dangerSoft: "${tokens.color.light.hotSoft}",\n} as const;
export const colorsDark = {\n${rnColors("dark")}\n  danger: "${tokens.color.dark.hot}",\n  dangerSoft: "${tokens.color.dark.hotSoft}",\n} as const;
export const colorSchemes = { light: colors, dark: colorsDark } as const;
export const ui = {\n${rnSemantic("light")}\n} as const;
export const uiDark = {\n${rnSemantic("dark")}\n} as const;
export const uiSchemes = { light: ui, dark: uiDark } as const;
export const radius = { sm: 0, md: ${tokens.radius.md}, lg: ${tokens.radius.lg}, pill: 0 } as const;
export const spacing = ${JSON.stringify(tokens.spacing, null, 2)} as const;
export const shadow = {
  sm: { shadowColor: colors.rule, shadowOpacity: 1, shadowRadius: 0, shadowOffset: { width: ${tokens.shadow.sm}, height: ${tokens.shadow.sm} }, elevation: ${tokens.shadow.sm}, boxShadow: \`${tokens.shadow.sm}px ${tokens.shadow.sm}px 0 \${colors.rule}\` },
  card: { shadowColor: colors.rule, shadowOpacity: 1, shadowRadius: 0, shadowOffset: { width: ${tokens.shadow.md}, height: ${tokens.shadow.md} }, elevation: ${tokens.shadow.md}, boxShadow: \`${tokens.shadow.md}px ${tokens.shadow.md}px 0 \${colors.rule}\` },
} as const;
export const duration = { fast: ${tokens.motion.duration.fast}, base: ${tokens.motion.duration.base} } as const;
export const typography = { display: { fontSize: ${tokens.typography.display.fontSize}, fontWeight: "700" as const, letterSpacing: ${tokens.typography.display.letterSpacing}, lineHeight: ${tokens.typography.display.lineHeight} }, headline: { fontSize: ${tokens.typography.headline.fontSize}, fontWeight: "700" as const, letterSpacing: ${tokens.typography.headline.letterSpacing}, lineHeight: ${tokens.typography.headline.lineHeight} }, body: { fontSize: ${tokens.typography.body.fontSize}, lineHeight: ${tokens.typography.body.lineHeight} }, meta: { fontSize: ${tokens.typography.meta.fontSize}, fontWeight: "600" as const, letterSpacing: ${tokens.typography.meta.letterSpacing} } } as const;
export const typographyTe = { display: { ...typography.display, lineHeight: ${tokens.typography.telugu.displayLineHeight} }, headline: { ...typography.headline, letterSpacing: ${tokens.typography.telugu.headlineLetterSpacing}, lineHeight: ${tokens.typography.telugu.headlineLineHeight} }, body: { ...typography.body, lineHeight: ${tokens.typography.telugu.bodyLineHeight} }, meta: typography.meta } as const;
export function typographyFor(language: "en" | "te") { return language === "te" ? typographyTe : typography; }
`;
const outputs = [
  ["apps/web/src/app/tokens.css", css],
  ["apps/admin/src/app/tokens.css", "/* GENERATED — DO NOT EDIT. Source: packages/design-tokens/tokens.json */\n@import \"../../../web/src/app/tokens.css\";\n"],
  ["apps/mobile/src/theme/tokens.ts", rn],
];
let stale = false;
for (const [relative, contents] of outputs) {
  const file = path.join(root, relative);
  if (readFileSync(file, "utf8") !== contents) {
    stale = true;
    if (check) continue;
    writeFileSync(file, contents);
    console.log(`generated ${relative}`);
  }
}
if (check && stale) process.exitCode = 1;
