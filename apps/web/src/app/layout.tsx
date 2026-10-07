import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";

import { BottomNav } from "@/components/BottomNav";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { TrackEvent } from "@/components/TrackEvent";
import { ErrorTrackingBoot } from "@/components/ErrorTrackingBoot";
import { getConfig, siteUrl, type TopicOut } from "@/lib/api";
import { READING_INIT_SCRIPT } from "@/lib/readingPrefs";
import { STORY_LANGUAGE_INIT_SCRIPT } from "@/lib/storyLanguage";

import "./globals.css";

// Font budget: one variable Latin family (all weights in one file) is
// preloaded. The Telugu faces are large and only needed once Telugu text is
// on screen, so they are not preloaded — the browser fetches them on demand
// via unicode-range when a lang="te" glyph first renders.
//
// Self-hosted via next/font/local (woff2 from @fontsource / @fontsource-variable
// 5.3.0, OFL texts alongside in ./fonts) rather than next/font/google, same as
// apps/admin: the VPS Docker build failed inside next/font's Google loader when
// Google served a font URL without a file extension. Local files keep builds
// offline-safe. Telugu files are the telugu subset only; Latin glyphs in Telugu
// text fall through to --font-body via the stacks in tokens.css/globals.css.
const fontSans = localFont({
  src: "./fonts/inter-tight-latin-wght-normal.woff2",
  variable: "--font-sans",
  weight: "100 900",
  display: "swap",
});

const fontTelugu = localFont({
  src: "./fonts/noto-sans-telugu-telugu-wght-normal.woff2",
  variable: "--font-telugu",
  weight: "100 900",
  display: "swap",
  preload: false,
  // Repeated per face: next/font only accepts literal options.
  declarations: [
    { prop: "unicode-range", value: "U+0951-0952,U+0964-0965,U+0C00-0C7F,U+1CDA,U+1CF2,U+200C-200D,U+25CC" },
  ],
});

const fontTeluguDisplay = localFont({
  src: "./fonts/peddana-telugu-400-normal.woff2",
  variable: "--font-telugu-display",
  weight: "400",
  display: "swap",
  preload: false,
  // Repeated per face: next/font only accepts literal options.
  declarations: [
    { prop: "unicode-range", value: "U+0951-0952,U+0964-0965,U+0C00-0C7F,U+1CDA,U+1CF2,U+200C-200D,U+25CC" },
  ],
});

const fontTeluguSerif = localFont({
  src: "./fonts/noto-serif-telugu-telugu-wght-normal.woff2",
  variable: "--font-telugu-serif",
  weight: "100 900",
  display: "swap",
  preload: false,
  // Repeated per face: next/font only accepts literal options.
  declarations: [
    { prop: "unicode-range", value: "U+0951-0952,U+0964-0965,U+0C00-0C7F,U+1CDA,U+1CF2,U+200C-200D,U+25CC" },
  ],
});

const fontTeluguMandali = localFont({
  src: "./fonts/mandali-telugu-400-normal.woff2",
  variable: "--font-telugu-mandali",
  weight: "400",
  display: "swap",
  preload: false,
  // Repeated per face: next/font only accepts literal options.
  declarations: [
    { prop: "unicode-range", value: "U+0951-0952,U+0964-0965,U+0C00-0C7F,U+1CDA,U+1CF2,U+200C-200D,U+25CC" },
  ],
});

// Runs before hydration so the correct theme paints on first frame — avoids
// a light->dark (or vice versa) flash for anyone with a saved preference.
const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("tg-theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`;

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: { default: "TTE — The Telugu Edit", template: "%s · TTE" },
  description: "The Telugu world, thoughtfully edited.",
  applicationName: "The Telugu Edit",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#171410" },
  ],
};

// The section nav is chrome, not content: if the API is briefly down the
// page should still render (without the topic bar) rather than error out.
// Only topics with stories: the bar leads to content, the header's Topics
// link leads to the full list (review #11).
async function navTopics(): Promise<TopicOut[]> {
  try {
    return (await getConfig()).topics.filter((topic) => topic.active && topic.story_count > 0);
  } catch {
    return [];
  }
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const topics = await navTopics();
  return (
    <html
      lang="en"
      className={`${fontSans.variable} ${fontTelugu.variable} ${fontTeluguDisplay.variable} ${fontTeluguSerif.variable} ${fontTeluguMandali.variable}`}
      // Preference scripts set root attributes before hydration.
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
        <script dangerouslySetInnerHTML={{ __html: STORY_LANGUAGE_INIT_SCRIPT }} />
        <script dangerouslySetInnerHTML={{ __html: READING_INIT_SCRIPT }} />
      </head>
      <body>
        <ErrorTrackingBoot />
        <TrackEvent event="app_open" />
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <SiteHeader topics={topics} />
        <main id="main-content">{children}</main>
        <SiteFooter />
        <BottomNav />
      </body>
    </html>
  );
}
