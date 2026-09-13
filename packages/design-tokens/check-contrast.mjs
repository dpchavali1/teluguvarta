import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const tokens = JSON.parse(readFileSync(path.join(root, "packages/design-tokens/tokens.json"), "utf8"));

function luminance(hex) {
  const channels = hex.slice(1).match(/../g).map((value) => Number.parseInt(value, 16) / 255);
  const linear = channels.map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

const pairs = [
  ["textPrimary", "surface", 4.5],
  ["textSecondary", "surface", 4.5],
  ["textTertiary", "surface", 4.5],
  ["actionPrimary", "surface", 3],
  ["actionPrimaryText", "actionPrimary", 4.5],
  ["actionText", "actionPrimarySoft", 4.5],
  ["success", "successSoft", 4.5],
  ["warning", "warningSoft", 4.5],
  ["danger", "dangerSoft", 4.5],
  ["borderControl", "surface", 3],
];

let failed = false;
for (const scheme of ["light", "dark"]) {
  const roles = tokens.semantic[scheme];
  for (const [foreground, background, minimum] of pairs) {
    const ratio = contrast(roles[foreground], roles[background]);
    if (ratio < minimum) {
      console.error(`${scheme}: ${foreground}/${background} is ${ratio.toFixed(2)}:1; need ${minimum}:1`);
      failed = true;
    }
  }
}
if (failed) process.exit(1);
console.log("semantic color contrast checks passed");
