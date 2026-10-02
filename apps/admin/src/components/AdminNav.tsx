"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import ThemeToggle from "@/components/ThemeToggle";
import { getRole, isSignedIn, setSession, signOut } from "@/lib/auth";
import { adminFetch, SessionExpired, type ReaderReportList } from "@/lib/reports";
import type { components } from "@teluguvarta/contracts";

type CurrentSession = components["schemas"]["AdminCurrentSessionOut"];

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/review", label: "Review queue" },
  { href: "/stories", label: "Stories" },
  { href: "/reports", label: "Reader reports" },
  { href: "/briefs", label: "Auto briefs" },
  { href: "/sources", label: "Sources" },
  { href: "/coverage", label: "Coverage" },
  { href: "/costs", label: "AI costs" },
  { href: "/observability", label: "Observability" },
  { href: "/audit", label: "Audit log" },
];

export default function AdminNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [role, setRole] = useState<string | null>(null);
  const [hasToken, setHasToken] = useState(false);
  const [openReports, setOpenReports] = useState<number | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => { setMenuOpen(false); }, [pathname]);

  useEffect(() => {
    setRole(getRole());
    const signedIn = isSignedIn();
    setHasToken(signedIn);
    if (!signedIn || pathname === "/login") return;
    // ADR-028: the cookie can't be read here, so ask the API who is signed
    // in; that refreshes the role hint and notices a session that ended.
    adminFetch<CurrentSession>("/v1/admin/auth/session")
      .then((session) => {
        if (session.mfa_enrollment_required) throw new SessionExpired("Enrollment only");
        setSession(session.role);
        setRole(session.role);
      })
      .catch((err) => {
        if (err instanceof SessionExpired) {
          void signOut().catch(() => undefined);
          setHasToken(false);
          router.replace("/login");
        }
      });
    // ADR-029: open reader reports, refreshed on every navigation.
    adminFetch<ReaderReportList>("/v1/admin/reports?limit=1")
      .then((list) => setOpenReports(list.open_count))
      .catch(() => setOpenReports(null));
  }, [pathname, router]);

  if (pathname === "/login" || !hasToken) return null;

  return (
    <nav className={`admin-nav${menuOpen ? " admin-nav--open" : ""}`} aria-label="Admin">
      <Link href="/" className="admin-nav__brand">
        TTE<span>Admin</span>
      </Link>
      <span className="admin-nav__current">{LINKS.find((link) => link.href !== "/" && pathname.startsWith(link.href))?.label ?? (pathname === "/sessions" ? "Sessions" : "Home")}</span>
      <button type="button" className="admin-nav__menu-toggle" aria-expanded={menuOpen} aria-controls="admin-nav-menu" onClick={() => setMenuOpen((open) => !open)}>
        {menuOpen ? "Close" : "Menu"}
      </button>
      <div className="admin-nav__links" id="admin-nav-menu">
        {LINKS.map((link) => (
          <Link key={link.href} href={link.href} aria-current={pathname === link.href || (link.href !== "/" && pathname.startsWith(`${link.href}/`)) ? "page" : undefined} className={pathname === link.href || (link.href !== "/" && pathname.startsWith(`${link.href}/`)) ? "is-active" : ""}>
            <span className="admin-nav__dot" aria-hidden="true" />
            {link.label}
            {link.href === "/reports" && openReports ? (
              <span className="admin-nav__count" aria-label={`${openReports} open`}>{openReports}</span>
            ) : null}
          </Link>
        ))}
      </div>
      <div className="admin-nav__footer">
        {role ? <span className="admin-nav__role">{role}</span> : null}
        <ThemeToggle />
        <Link href="/sessions" className={pathname === "/sessions" ? "is-active" : ""}>
          Sessions
        </Link>
        <button
          type="button"
          onClick={async () => {
            await signOut().catch(() => undefined);
            router.push("/login");
          }}
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
