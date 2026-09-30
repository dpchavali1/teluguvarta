/* eslint-disable @typescript-eslint/no-require-imports */
// jest-expo doesn't set this for React 19's reconciler, so state updates
// inside fetch/AsyncStorage `.then()` callbacks (not already wrapped in the
// test's own `act()`) log spurious "not configured to support act()"
// warnings even though `waitFor`/`fireEvent` still work correctly.
global.IS_REACT_ACT_ENVIRONMENT = true;
// v3's jest export is a plain in-memory implementation, not a self-registering
// mock (unlike the old `jest/async-storage-mock` path this replaced) — wire
// it up explicitly so `import AsyncStorage from "@react-native-async-storage/async-storage"`
// resolves to the in-memory version under test.
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest")
);

// Without this, SafeAreaProvider never receives initial insets from a real
// native layer in the test environment and renders nothing.
jest.mock("react-native-safe-area-context", () => {
  const mock = require("react-native-safe-area-context/jest/mock");
  return mock.default ?? mock;
});

// In-memory stand-in for the Keychain/Keystore (src/lib/identity.ts).
jest.mock("expo-secure-store", () => {
  const store = new Map();
  return {
    getItemAsync: jest.fn(async (key) => store.get(key) ?? null),
    setItemAsync: jest.fn(async (key, value) => { store.set(key, value); }),
    deleteItemAsync: jest.fn(async (key) => { store.delete(key); }),
  };
});

// jest-expo stubs the native module (randomUUID returns undefined); Node's
// CSPRNG stands in for the OS one.
jest.mock("expo-crypto", () => ({ randomUUID: () => require("crypto").randomUUID() }));
