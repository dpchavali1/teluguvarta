import type { ReactNode } from "react";

export const metadata = {
  title: "Telugu Global Admin",
  description: "Internal admin console."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
