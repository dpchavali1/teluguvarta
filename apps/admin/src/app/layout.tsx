import type { ReactNode } from "react";
import { Bricolage_Grotesque, Inter_Tight, JetBrains_Mono, Noto_Sans_Telugu } from "next/font/google";

import AdminNav from "@/components/AdminNav";
import ErrorTrackingBoot from "@/components/ErrorTrackingBoot";
import { ToastProvider } from "@/components/ui";

import "./globals.css";

// Same pairing as apps/web/src/app/layout.tsx — see that file for the
// rationale. Telugu is loaded here too: the review-queue story detail page
// renders the Telugu variant text for editorial QA.
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

// Same as apps/web: apply a saved theme before hydration so there's no flash.
// Shares the "tg-theme" key, but admin and web are separate origins in prod,
// so each remembers its own choice.
const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("tg-theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`;

export const metadata = {
  title: "TTE Admin",
  description: "Internal admin console."
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
