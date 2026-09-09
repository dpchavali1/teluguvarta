import AsyncStorage from "@react-native-async-storage/async-storage";

// ADR-006 device-scoped anonymous identity, resolved for real in T17: the
// client mints its own opaque, unguessable token once and sends it as
// `Authorization: Bearer` on every `/v1/me/*` call (see
// apps/api/app/auth.py::current_user — the first request bearing a given
// token get-or-creates its `users` row, so there's no separate "issue me a
// token" round trip). `crypto.randomUUID` is available in the Hermes/Expo
// runtime this app targets; a device that somehow lacks it falls back to a
// timestamp+random string, still unguessable enough for this purpose.

const KEY = "tg_client_token_v1";

export function randomToken(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

let cached: string | null = null;

export async function getClientToken(): Promise<string> {
  if (cached) return cached;
  try {
    const existing = await AsyncStorage.getItem(KEY);
    if (existing) {
      cached = existing;
      return existing;
    }
    const token = randomToken();
    await AsyncStorage.setItem(KEY, token);
    cached = token;
    return token;
  } catch {
    // Storage unavailable — fall back to an in-memory-only token for this
    // session rather than failing every /v1/me/* call.
    if (!cached) cached = randomToken();
    return cached;
  }
}

// T19: after server-side account deletion, the old token must never be
// reused — the server has forgotten it, but reusing it would just
// get-or-create a fresh, empty `users` row under the same identifier,
// which is harmless but pointless. Clearing it here means the next
// `getClientToken()` mints a genuinely new one.
export async function resetClientToken(): Promise<void> {
  cached = null;
  try {
    await AsyncStorage.removeItem(KEY);
  } catch {
    // Storage unavailable — in-memory `cached` is already cleared, which is
    // all that matters for the rest of this app session.
  }
}
