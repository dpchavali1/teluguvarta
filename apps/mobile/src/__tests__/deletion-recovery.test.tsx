import AsyncStorage from "@react-native-async-storage/async-storage";
import { act, fireEvent, render, screen, userEvent } from "@testing-library/react-native";
import React from "react";

import { deleteAccount } from "../lib/api";
import { resetClientToken } from "../lib/identity";
import { StoryCacheProvider } from "../lib/StoryCacheContext";
import { PrivacyScreen } from "../screens/PrivacyScreen";

jest.mock("../lib/api", () => ({ deleteAccount: jest.fn(), trackEvent: jest.fn() }));
jest.mock("../lib/identity", () => ({ resetClientToken: jest.fn(async () => undefined) }));

beforeEach(async () => { jest.clearAllMocks(); await AsyncStorage.clear(); });

test("server failure keeps local data and identity, and retry completes deletion", async () => {
  await AsyncStorage.setItem("tg_saved_stories_v1", '["saved"]');
  jest.mocked(deleteAccount).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(undefined);
  await render(<StoryCacheProvider><PrivacyScreen /></StoryCacheProvider>);
  await fireEvent.press(screen.getByLabelText("Delete account and clear all data on this device"));
  expect(await screen.findByText(/Your data and identity have been kept/)).toBeTruthy();
  expect(await AsyncStorage.getItem("tg_saved_stories_v1")).toBe('["saved"]');
  expect(resetClientToken).not.toHaveBeenCalled();
  expect(screen.queryByText("Account deleted and data cleared on this device.")).toBeNull();
  await fireEvent.press(screen.getByLabelText("Delete account and clear all data on this device"));
  await screen.findByText("Account deleted and data cleared on this device.");
  expect(await AsyncStorage.getItem("tg_saved_stories_v1")).toBeNull();
  expect(resetClientToken).toHaveBeenCalledWith(true);
  // Completion ends that operation; a later request must confirm deletion again.
  await fireEvent.press(screen.getByLabelText("Delete account and clear all data on this device"));
  expect(deleteAccount).toHaveBeenCalledTimes(3);
});

test("a local cleanup failure retries cleanup without another server request", async () => {
  jest.mocked(deleteAccount).mockResolvedValue(undefined);
  const clear = jest.spyOn(AsyncStorage, "removeMany").mockRejectedValueOnce(new Error("storage"));
  try {
    await render(<StoryCacheProvider><PrivacyScreen /></StoryCacheProvider>);
    await fireEvent.press(screen.getByLabelText("Delete account and clear all data on this device"));
    await screen.findByText(/some data on this device couldn’t be cleared/);
    expect(resetClientToken).not.toHaveBeenCalled();
    await fireEvent.press(screen.getByLabelText("Delete account and clear all data on this device"));
    await screen.findByText("Account deleted and data cleared on this device.");
    expect(deleteAccount).toHaveBeenCalledTimes(1);
  } finally { clear.mockRestore(); }
});

test("in-flight deletion is exclusive", async () => {
  let resolve!: () => void;
  jest.mocked(deleteAccount).mockImplementationOnce(() => new Promise<void>((r) => { resolve = r; }));
  await render(<StoryCacheProvider><PrivacyScreen /></StoryCacheProvider>);
  const button = screen.getByLabelText("Delete account and clear all data on this device");
  const user = userEvent.setup();
  await user.press(button);
  expect(button).toBeDisabled();
  await fireEvent.press(button);
  expect(deleteAccount).toHaveBeenCalledTimes(1);
  await act(async () => { resolve(); });
  await screen.findByText("Account deleted and data cleared on this device.");
});
