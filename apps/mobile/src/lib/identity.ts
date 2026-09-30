import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";

// ADR-006 device-scoped anonymous identity, resolved for real in T17: the
// client mints its own opaque, unguessable token once and sends it as
// `Authorization: Bearer` on every `/v1/me/*` call (see
// apps/api/app/auth.py::current_user — the first request bearing a given
// token get-or-creates its `users` row, so there's no separate "issue me a
// token" round trip).
//
// Review #15: the token is a UUID from the OS cryptographic RNG (expo-crypto;
// Hermes has no guaranteed `crypto.randomUUID`, so the old code could fall
// back to Math.random), kept in the Keychain/Keystore via expo-secure-store.
// A token an older build left in AsyncStorage is moved over on first read, so
// the device keeps its identity and preferences.

const KEY = "tg_client_token_v1";

export function randomToken(): string {
  return Crypto.randomUUID();
}

let cached: string | null = null;

export async function getClientToken(): Promise<string> {
  if (cached) return cached;
  try {
    const existing = await SecureStore.getItemAsync(KEY);
    if (existing) {
      cached = existing;
      return existing;
    }
    const legacy = await AsyncStorage.getItem(KEY);
    const token = legacy ?? randomToken();
    await SecureStore.setItemAsync(KEY, token);
    if (legacy) await AsyncStorage.removeItem(KEY);
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
    await SecureStore.deleteItemAsync(KEY);
    await AsyncStorage.removeItem(KEY);
  } catch {
    // Storage unavailable — in-memory `cached` is already cleared, which is
    // all that matters for the rest of this app session.
  }
}
