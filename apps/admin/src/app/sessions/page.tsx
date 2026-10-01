"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import type { components } from "@teluguvarta/contracts";

import { EmptyState, PageHeader } from "@/components/ui";
import { signOut } from "@/lib/auth";
import { adminFetch, SessionExpired } from "@/lib/reports";
import { ago } from "@/lib/time";

// ADR-028 (review 2026-09-30 R11): where this account is signed in, and a way
// to end all of it — e.g. after using a shared computer or losing a laptop.
type SessionList = components["schemas"]["AdminSessionListOut"];
type AdminSession = SessionList["items"][number];

function describeDevice(userAgent: string | null | undefined): string {
  if (!userAgent) return "Unknown browser";
  const browser = /Edg\//.test(userAgent)
    ? "Edge"
    : /Firefox\//.test(userAgent)
      ? "Firefox"
      : /Chrome\//.test(userAgent)
        ? "Chrome"
        : /Safari\//.test(userAgent)
          ? "Safari"
          : "Browser";
  const os = /iPhone|iPad/.test(userAgent)
    ? "iOS"
    : /Android/.test(userAgent)
      ? "Android"
      : /Mac OS X/.test(userAgent)
        ? "macOS"
        : /Windows/.test(userAgent)
          ? "Windows"
          : /Linux/.test(userAgent)
            ? "Linux"
            : "";
  return os ? `${browser} on ${os}` : browser;
}

export default function SessionsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<AdminSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setError(null);
    adminFetch<SessionList>("/v1/admin/auth/sessions", {}, "Couldn't load sessions")
      .then((list) => setSessions(list.items))
      .catch((err) => {
        if (err instanceof SessionExpired) router.replace("/login");
        else setError(err instanceof Error ? err.message : "Couldn't load sessions");
      });
  }, [router]);

  useEffect(() => load(), [load]);

  async function signOutEverywhere() {
    setBusy(true);
    setError(null);
    try {
      await signOut(true);
      router.push("/login");
    } catch {
      setError("Couldn't sign out everywhere. Check your connection and try again.");
      setBusy(false);
    }
  }

  return (
    <main>
      <PageHeader
        title="Sessions"
        subtitle="Where this account is signed in. A session ends after 30 minutes without activity or 12 hours after sign-in."
        actions={
          <button type="button" onClick={signOutEverywhere} disabled={busy}>
            {busy ? "Signing out…" : "Sign out everywhere"}
          </button>
        }
      />
      {error ? <p role="alert">{error}</p> : null}
      {sessions === null && !error ? <p>Loading…</p> : null}
      {sessions?.length === 0 ? <EmptyState title="No active sessions" /> : null}
      {sessions && sessions.length > 0 ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Device</th>
                <th scope="col">Signed in</th>
                <th scope="col">Last active</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.id}>
                  <td title={session.user_agent ?? undefined}>
                    {describeDevice(session.user_agent)}
                    {session.current ? " (this browser)" : ""}
                  </td>
                  <td>{ago(session.created_at)}</td>
                  <td>{ago(session.last_seen_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </main>
  );
}
