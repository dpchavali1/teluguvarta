import type { MetadataRoute } from "next";

// Makes the admin console installable to a phone home screen so review and
// approve run full-screen. Deliberately no service worker: admin data is
// authenticated and must always be fresh, so nothing is cached offline, and
// current Chrome/Safari install without one.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "TTE Admin",
    short_name: "TTE Admin",
    description: "Internal admin console.",
    id: "/",
    start_url: "/review",
    scope: "/",
    display: "standalone",
    // --color-bg from tokens.css (light theme); layout.tsx's viewport
    // themeColor overrides per colour scheme once the page loads.
    theme_color: "#f6f2e8",
    background_color: "#f6f2e8",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" }
    ]
  };
}
