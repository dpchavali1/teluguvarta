"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Icon, type IconName } from "@/components/Icon";
import { isActivePath } from "@/components/SiteHeader";

const TABS: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/latest", label: "Latest", icon: "latest" },
  { href: "/topics", label: "Topics", icon: "topics" },
  { href: "/search", label: "Search", icon: "search" },
  { href: "/saved", label: "Saved", icon: "bookmark" },
];

// Phone-width primary navigation: a thumb-reachable tab bar instead of a
// wrapped link row in the header. Hidden at tablet/desktop widths by CSS.
export function BottomNav() {
  const pathname = usePathname();
  return (
    <nav className="bottom-nav" aria-label="Quick navigation">
      <ul>
        {TABS.map((tab) => {
          const active = isActivePath(pathname, tab.href);
          return (
            <li key={tab.href}>
              <Link href={tab.href} aria-current={active ? "page" : undefined}>
                <Icon name={tab.icon} size={21} filled={active && tab.icon === "bookmark"} />
                <span>{tab.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
