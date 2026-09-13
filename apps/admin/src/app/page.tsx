"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiUrl, clearSession, getRole, getToken } from "@/lib/auth";
import { captureException } from "@/lib/errorTracking";

export default function Home() {
  const router = useRouter();
  const [status, setStatus] = useState<"checking" | "ready" | "unauthorized">("checking");
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    fetch(`${apiUrl()}/v1/admin/sources`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then((response) => {
        if (!response.ok) {
          clearSession();
          setStatus("unauthorized");
          router.replace("/login");
          return;
        }
        setRole(getRole());
        setStatus("ready");
      })
      .catch(() => setStatus("unauthorized"));
  }, [router]);

  if (status !== "ready") {
    return (
      <main>
        <p className="state-note">Checking session…</p>
      </main>
    );
  }

  return (
    <main>
      <h1>TTE Admin</h1>
      <section>
        <p>
          Signed in as <strong>{role}</strong>.
        </p>
        <p>
          <Link href="/review">Review queue</Link> · <Link href="/observability">Observability</Link>
        </p>
      </section>
      {process.env.NODE_ENV !== "production" ? (
        <section>
          <h2>Debug</h2>
          <button
            type="button"
            onClick={() => captureException(new Error("T18 debug throw — deliberate, for error-tracking verification"), { role: role ?? "" })}
          >
            Debug: throw error
          </button>
        </section>
      ) : null}
    </main>
  );
}
