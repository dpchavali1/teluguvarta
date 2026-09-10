import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Bricolage_Grotesque, Inter_Tight, JetBrains_Mono, Noto_Sans_Telugu } from "next/font/google";

import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { TrackEvent } from "@/components/TrackEvent";
import { ErrorTrackingBoot } from "@/components/ErrorTrackingBoot";
import { siteUrl } from "@/lib/api";

import "./globals.css";

// Type pairing: a wide, slightly wonky grotesque for display (Bricolage
// Grotesque) against a tight neo-grotesque for running text (Inter Tight),
// with a mono for all micro-labels. Telugu rides on Noto Sans Telugu at both
// text and display weights so the bilingual pairing stays in the same
// (grotesque) voice instead of switching to a serif mid-page.
const fontDisplay = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "600", "700", "800"],
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
  title: { default: "Telugu Global", template: "%s · Telugu Global" },
  description: "Global Telugu identity, local information.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${fontDisplay.variable} ${fontSans.variable} ${fontMono.variable} ${fontTelugu.variable}`}
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
