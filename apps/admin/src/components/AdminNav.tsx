"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import ThemeToggle from "@/components/ThemeToggle";
import { clearSession, getRole, getToken } from "@/lib/auth";
import { adminFetch, type ReaderReportList } from "@/lib/reports";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/review", label: "Review queue" },
  { href: "/stories", label: "Stories" },
  { href: "/reports", label: "Reader reports" },
  { href: "/briefs", label: "Auto briefs" },
  { href: "/sources", label: "Sources" },
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

  useEffect(() => {
    setRole(getRole());
    const signedIn = Boolean(getToken());
    setHasToken(signedIn);
    if (!signedIn || pathname === "/login") return;
    // ADR-029: open reader reports, refreshed on every navigation.
    adminFetch<ReaderReportList>("/v1/admin/reports?limit=1")
      .then((list) => setOpenReports(list.open_count))
      .catch(() => setOpenReports(null));
  }, [pathname]);

  if (pathname === "/login" || !hasToken) return null;

  return (
    <nav className="admin-nav" aria-label="Admin">
      <Link href="/" className="admin-nav__brand">
        TTE<span>Admin</span>
      </Link>
      <div className="admin-nav__links">
        {LINKS.map((link) => (
          <Link key={link.href} href={link.href} className={pathname === link.href ? "is-active" : ""}>
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
        <button
          type="button"
          onClick={() => {
            clearSession();
            router.push("/login");
          }}
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
