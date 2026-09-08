"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiUrl, clearSession, getRole, getToken } from "@/lib/auth";

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
        <p>Checking session…</p>
      </main>
    );
  }

  return (
    <main>
      <h1>Telugu Global Admin</h1>
      <p>Signed in as {role}. Editorial tooling lands in T12.</p>
      <button
        type="button"
        onClick={() => {
          clearSession();
          router.replace("/login");
        }}
      >
        Sign out
      </button>
    </main>
  );
}
