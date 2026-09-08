import type { ReactNode } from "react";

export const metadata = {
  title: "Telugu Global",
  description: "Global Telugu identity, local information."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
