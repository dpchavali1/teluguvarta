import Link from "next/link";

import { LanguageToggle } from "@/components/LanguageToggle";
import { ThemeToggle } from "@/components/ThemeToggle";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Search" },
  { href: "/saved", label: "Saved" },
  { href: "/about", label: "About" },
];

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link href="/" className="site-header__brand">
          <span className="site-header__mark" aria-hidden="true" />
          <span className="site-header__wordmark">
            <span className="site-header__brand-en">Telugu Global</span>
            <span className="site-header__brand-te" lang="te">తెలుగు గ్లోబల్</span>
          </span>
        </Link>
        <div className="site-header__right">
          <nav className="site-nav" aria-label="Main navigation">
            <ul>
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <Link href={link.href}>{link.label}</Link>
                </li>
              ))}
            </ul>
          </nav>
          <LanguageToggle />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
