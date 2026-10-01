// ADR-028: the admin session is an HttpOnly cookie the API sets on login and
// script can't read. The only thing kept here is the account's role, a UI
// hint (which nav and buttons to show) and the "probably signed in" marker
// pages use to send a signed-out visitor to /login without a round trip.
// The API decides every request on its own; a stale hint just means a 401
// or 403, after which the page clears it.
const ROLE_KEY = "tg_admin_role";
// The bearer token the admin kept before ADR-028. Removed on sight so an old
// copy doesn't linger in the browser.
const LEGACY_TOKEN_KEY = "tg_admin_token";

export function apiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

/** fetch() for admin API calls: sends the session cookie and the CSRF header. */
export function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("X-TTE-Admin", "1");
  return fetch(input, { ...init, headers, credentials: "include" });
}

export function isSignedIn(): boolean {
  return getRole() !== null;
}

export function setSession(role: string): void {
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
  window.localStorage.setItem(ROLE_KEY, role);
}

export function getRole(): string | null {
  if (typeof window === "undefined") return null;
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
  return window.localStorage.getItem(ROLE_KEY);
}

/** Forgets the local hint. The server session is ended by `signOut`. */
export function clearSession(): void {
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
  window.localStorage.removeItem(ROLE_KEY);
}

/** Ends this session (or, with `everywhere`, every session of the account) on the server. */
export async function signOut(everywhere = false): Promise<void> {
  try {
    await apiFetch(`${apiUrl()}/v1/admin/auth/${everywhere ? "logout-everywhere" : "logout"}`, { method: "POST" });
  } finally {
    clearSession();
  }
}
