import type { ReactNode } from "react";

import AdminNav from "@/components/AdminNav";
import ErrorTrackingBoot from "@/components/ErrorTrackingBoot";

import "./globals.css";

export const metadata = {
  title: "Telugu Global Admin",
  description: "Internal admin console."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ErrorTrackingBoot />
        <AdminNav />
        {children}
      </body>
    </html>
  );
}
