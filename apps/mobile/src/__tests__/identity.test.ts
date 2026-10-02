import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";

import { getClientToken, resetClientToken } from "../lib/identity";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

// resetClientToken also drops the in-memory copy, like a fresh app start.
beforeEach(async () => {
  await resetClientToken();
  await AsyncStorage.clear();
});

test("mints a v4 UUID and keeps it in secure storage, not AsyncStorage", async () => {
  const token = await getClientToken();
  expect(token).toMatch(UUID);
  expect(await SecureStore.getItemAsync("tg_client_token_v1")).toBe(token);
  expect(await AsyncStorage.getItem("tg_client_token_v1")).toBeNull();
  expect(await getClientToken()).toBe(token);
});

test("moves a token an older build left in AsyncStorage", async () => {
  await AsyncStorage.setItem("tg_client_token_v1", "1727712000000-k3j2h1g0f9-a8s7d6f5g4");
  expect(await getClientToken()).toBe("1727712000000-k3j2h1g0f9-a8s7d6f5g4");
  expect(await SecureStore.getItemAsync("tg_client_token_v1")).toBe("1727712000000-k3j2h1g0f9-a8s7d6f5g4");
  expect(await AsyncStorage.getItem("tg_client_token_v1")).toBeNull();
});

test("reset clears the token so the next one is new", async () => {
  const first = await getClientToken();
  await resetClientToken();
  expect(await SecureStore.getItemAsync("tg_client_token_v1")).toBeNull();
  expect(await getClientToken()).not.toBe(first);
});

test("strict deletion surfaces secure-storage failure and keeps the identity for retry", async () => {
  const first = await getClientToken();
  const remove = jest.spyOn(SecureStore, "deleteItemAsync").mockRejectedValueOnce(new Error("locked"));
  try {
    await expect(resetClientToken(true)).rejects.toThrow("locked");
    expect(await getClientToken()).toBe(first);
    await resetClientToken(true);
    expect(await SecureStore.getItemAsync("tg_client_token_v1")).toBeNull();
  } finally { remove.mockRestore(); }
});
