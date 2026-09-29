"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import ThemeToggle from "@/components/ThemeToggle";
import { clearSession, getRole, getToken } from "@/lib/auth";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/review", label: "Review queue" },
  { href: "/briefs", label: "Auto briefs" },
  { href: "/sources", label: "Sources" },
  { href: "/observability", label: "Observability" },
];

export default function AdminNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [role, setRole] = useState<string | null>(null);
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    setRole(getRole());
    setHasToken(Boolean(getToken()));
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
