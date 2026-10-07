import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";
import { headers } from "next/headers";

import AdminNav from "@/components/AdminNav";
import ErrorTrackingBoot from "@/components/ErrorTrackingBoot";
import { ToastProvider } from "@/components/ui";

import "./globals.css";

// Same pairing as apps/web/src/app/layout.tsx — see that file for the
// rationale. Telugu is loaded here too: the review-queue story detail page
// renders the Telugu variant text for editorial QA.
//
// Self-hosted via next/font/local (variable woff2 from @fontsource-variable,
// OFL texts alongside in ./fonts) rather than next/font/google: the VPS
// Docker build failed inside next/font's Google loader when Google served a
// font URL without a file extension. Local files keep builds offline-safe.
// Each file is the variable font's full wght axis (latin subset; telugu subset
// for Noto Sans Telugu), covering the weights the Google config requested.
const fontDisplay = localFont({
  src: "./fonts/bricolage-grotesque-latin-wght-normal.woff2",
  variable: "--font-display",
  weight: "200 800",
  display: "swap",
});

const fontSans = localFont({
  src: "./fonts/inter-tight-latin-wght-normal.woff2",
  variable: "--font-sans",
  weight: "100 900",
  display: "swap",
});

const fontMono = localFont({
  src: "./fonts/jetbrains-mono-latin-wght-normal.woff2",
  variable: "--font-mono",
  weight: "100 800",
  display: "swap",
});

const fontTelugu = localFont({
  src: "./fonts/noto-sans-telugu-telugu-wght-normal.woff2",
  variable: "--font-telugu",
  weight: "100 900",
  display: "swap",
});

// Same as apps/web: apply a saved theme before hydration so there's no flash.
// Shares the "tg-theme" key, but admin and web are separate origins in prod,
// so each remembers its own choice.
const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("tg-theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`;

export const metadata: Metadata = {
  title: "TTE Admin",
  description: "Internal admin console.",
  // The manifest (app/manifest.ts) is linked automatically; this covers iOS,
  // which ignores most of it when adding to the home screen.
  appleWebApp: { capable: true, title: "TTE Admin", statusBarStyle: "default" }
};

// Browser chrome follows the page background (--color-bg) in each theme.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f2e8" },
    { media: "(prefers-color-scheme: dark)", color: "#171410" }
  ]
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  // Set by src/middleware.ts; the CSP allows only scripts carrying it.
  const nonce = (await headers()).get("x-nonce") ?? undefined;
  return (
    <html
      lang="en"
      className={`${fontDisplay.variable} ${fontSans.variable} ${fontMono.variable} ${fontTelugu.variable}`}
      // THEME_INIT_SCRIPT sets data-theme before hydration, so this attribute
      // intentionally differs from the server-rendered HTML.
      suppressHydrationWarning
    >
      <head>
        <script nonce={nonce} dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <ErrorTrackingBoot />
        <ToastProvider>
          <div className="admin-shell">
            <AdminNav />
            {children}
          </div>
        </ToastProvider>
      </body>
    </html>
  );
}
