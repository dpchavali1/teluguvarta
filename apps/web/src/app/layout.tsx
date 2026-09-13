import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Fraunces, Inter_Tight, JetBrains_Mono, Noto_Sans_Telugu, Peddana } from "next/font/google";

import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { TrackEvent } from "@/components/TrackEvent";
import { ErrorTrackingBoot } from "@/components/ErrorTrackingBoot";
import { siteUrl } from "@/lib/api";

import "./globals.css";

// Type pairing: an editorial serif for display (Fraunces, English / Peddana,
// Telugu — both language-native serifs from the same "characterful
// headline" register) against a tight neo-grotesque for running text (Inter
// Tight / Noto Sans Telugu), with a mono for all micro-labels. Headings get
// a distinct per-language voice; body text stays on the proven, highly
// readable sans pairing.
const fontDisplay = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "600", "700", "800"],
  display: "swap",
});

const fontTeluguDisplay = Peddana({
  subsets: ["telugu"],
  variable: "--font-telugu-display",
  weight: ["400"],
  display: "swap",
});

const fontSans = Inter_Tight({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const fontMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "700"],
  display: "swap",
});

const fontTelugu = Noto_Sans_Telugu({
  subsets: ["telugu"],
  variable: "--font-telugu",
  weight: ["400", "500", "700"],
  display: "swap",
});

// Runs before hydration so the correct theme paints on first frame — avoids
// a light->dark (or vice versa) flash for anyone with a saved preference.
const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("tg-theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`;

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: { default: "TTE — The Telugu Edit", template: "%s · TTE" },
  description: "The Telugu world, thoughtfully edited.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${fontDisplay.variable} ${fontSans.variable} ${fontMono.variable} ${fontTelugu.variable} ${fontTeluguDisplay.variable}`}
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
        <SiteHeader />
        <main id="main-content">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
