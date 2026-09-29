import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Inter_Tight, Noto_Sans_Telugu, Peddana } from "next/font/google";

import { BottomNav } from "@/components/BottomNav";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { TrackEvent } from "@/components/TrackEvent";
import { ErrorTrackingBoot } from "@/components/ErrorTrackingBoot";
import { getConfig, siteUrl, type TopicOut } from "@/lib/api";

import "./globals.css";

// Font budget: one variable Latin family (all weights in one file) is
// preloaded. The Telugu faces are large and only needed once Telugu text is
// on screen, so they are not preloaded — the browser fetches them on demand
// via unicode-range when a lang="te" glyph first renders.
const fontSans = Inter_Tight({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const fontTelugu = Noto_Sans_Telugu({
  subsets: ["telugu"],
  variable: "--font-telugu",
  display: "swap",
  preload: false,
});

const fontTeluguDisplay = Peddana({
  subsets: ["telugu"],
  variable: "--font-telugu-display",
  weight: ["400"],
  display: "swap",
  preload: false,
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
async function navTopics(): Promise<TopicOut[]> {
  try {
    return (await getConfig()).topics.filter((topic) => topic.active);
  } catch {
    return [];
  }
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const topics = await navTopics();
  return (
    <html
      lang="en"
      className={`${fontSans.variable} ${fontTelugu.variable} ${fontTeluguDisplay.variable}`}
      // THEME_INIT_SCRIPT sets data-theme before hydration, so this attribute
      // intentionally differs from the server-rendered HTML.
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
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
