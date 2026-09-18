"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";

import { LanguageToggle } from "@/components/LanguageToggle";
import { ThemeToggle } from "@/components/ThemeToggle";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/topics", label: "Topics" },
  { href: "/search", label: "Search" },
  { href: "/saved", label: "Saved" },
  { href: "/about", label: "About" },
];

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="site-header__brand">
          <span className="site-header__wordmark">
            <span className="site-header__brand-en">TTE</span>
            <span className="site-header__brand-te" lang="te">తెలుగు ఎడిట్</span>
          </span>
        </Link>
        <nav className="site-nav" aria-label="Main navigation">
          <ul>
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} aria-current={pathname === link.href || (link.href === "/topics" && pathname.startsWith("/topic/")) ? "page" : undefined}>{link.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="site-header__utility-controls">
          <LanguageToggle />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
