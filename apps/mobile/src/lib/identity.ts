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

function randomToken(): string {
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
