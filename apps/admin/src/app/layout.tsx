import type { ReactNode } from "react";

import ErrorTrackingBoot from "@/components/ErrorTrackingBoot";

export const metadata = {
  title: "Telugu Global Admin",
  description: "Internal admin console."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ErrorTrackingBoot />
        {children}
      </body>
    </html>
  );
}
