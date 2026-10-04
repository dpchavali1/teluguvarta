"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";

import { Icon } from "@/components/Icon";
import { LanguageToggle } from "@/components/LanguageToggle";
import { TopicBar } from "@/components/TopicBar";
import { ThemeToggle } from "@/components/ThemeToggle";
import type { TopicOut } from "@/lib/api";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/latest", label: "Latest" },
  { href: "/topics", label: "Topics" },
  { href: "/saved", label: "Saved" },
  { href: "/trackers", label: "US Visa Bulletin" },
  { href: "/about", label: "About" },
];

export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/topics") return pathname === "/topics" || pathname.startsWith("/topic/");
  return pathname === href || pathname.startsWith(`${href}/`);
}

// ADR-014 EditionHeader: masthead + edition-level language control + theme
// control, once per page. The topic bar underneath is the section nav.
export function SiteHeader({ topics }: { topics: TopicOut[] }) {
  const pathname = usePathname();
  return (
    <header className="site-header">
      <div className="site-header__bar">
        <div className="site-header__inner">
          <Link href="/" className="brand" aria-label="TTE — The Telugu Edit, home">
            <span className="brand__mark" aria-hidden="true" lang="te">తె</span>
            <span className="brand__text">
              <span className="brand__name">The Telugu Edit</span>
              <span className="brand__tag" lang="te">తెలుగు ఎడిట్</span>
            </span>
          </Link>
          <nav className="site-nav" aria-label="Main navigation">
            <ul>
              {NAV_LINKS.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} aria-current={isActivePath(pathname, link.href) ? "page" : undefined}>{link.label}</Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="site-header__tools">
            <Link href="/search" className="icon-button" aria-label="Search" aria-current={pathname === "/search" ? "page" : undefined}>
              <Icon name="search" />
            </Link>
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>
      </div>
      {topics.length > 0 && <TopicBar topics={topics} pathname={pathname} />}
    </header>
  );
}
