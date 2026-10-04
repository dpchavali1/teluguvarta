import AsyncStorage from "@react-native-async-storage/async-storage";

import {
  addCollection, deleteCollection, dropStory, EMPTY_EXTRAS, idsInCollection, MAX_COLLECTIONS, MAX_NOTE_LENGTH,
  parseExtras, reminderTime, setNote, setReminder, toggleMembership,
} from "../lib/savedExtras";
import { getSavedExtras, LOCAL_DATA_KEYS, setSavedExtras } from "../lib/storage";

describe("saved extras (P06)", () => {
  it("adds collections with trimmed unique names and a cap", () => {
    let e = addCollection(EMPTY_EXTRAS, "  Visa  ", "a");
    expect(e.collections).toEqual([{ id: "a", name: "Visa" }]);
    expect(addCollection(e, "visa", "b")).toBe(e);
    expect(addCollection(e, "  ", "b")).toBe(e);
    for (let i = 0; i < MAX_COLLECTIONS; i++) e = addCollection(e, `L${i}`, `id${i}`);
    expect(e.collections).toHaveLength(MAX_COLLECTIONS);
  });

  it("toggles membership, filters by list, and deleting a list removes membership", () => {
    let e = addCollection(EMPTY_EXTRAS, "Visa", "a");
    e = toggleMembership(e, "s1", "a");
    e = toggleMembership(e, "s2", "a");
    expect(idsInCollection(e, ["s1", "s2", "s3"], "a")).toEqual(["s1", "s2"]);
    expect(toggleMembership(e, "s1", "missing")).toBe(e);
    e = toggleMembership(e, "s2", "a");
    expect(e.membership.s2).toBeUndefined();
    e = deleteCollection(e, "a");
    expect(e.membership).toEqual({});
  });

  it("limits and clears notes", () => {
    let e = setNote(EMPTY_EXTRAS, "s1", "x".repeat(MAX_NOTE_LENGTH + 20));
    expect(e.notes.s1).toHaveLength(MAX_NOTE_LENGTH);
    e = setNote(e, "s1", "   ");
    expect(e.notes).toEqual({});
  });

  it("unsaving drops note, membership and reminder", () => {
    let e = toggleMembership(addCollection(EMPTY_EXTRAS, "Visa", "a"), "s1", "a");
    e = setReminder(setNote(e, "s1", "hi"), "s1", { at: 1, notificationId: "n" });
    e = dropStory(e, "s1");
    expect([e.membership, e.notes, e.reminders]).toEqual([{}, {}, {}]);
    expect(e.collections).toHaveLength(1);
  });

  it("parseExtras discards malformed data and unknown collection ids", () => {
    expect(parseExtras("junk")).toEqual(EMPTY_EXTRAS);
    const e = parseExtras({ collections: [{ id: "a", name: "A" }, 5], membership: { s: ["a", "zz"], t: ["zz"] }, notes: { s: 3 }, reminders: { s: { at: "x" } } });
    expect(e.membership).toEqual({ s: ["a"] });
    expect(e.notes).toEqual({});
    expect(e.reminders).toEqual({});
  });

  it("schedules at 8am on a future day", () => {
    const at = new Date(reminderTime(new Date(2026, 9, 4, 15, 30), 3));
    expect([at.getDate(), at.getHours(), at.getMinutes()]).toEqual([7, 8, 0]);
  });

  it("persists across restart and is cleared with local data", async () => {
    await AsyncStorage.clear();
    await setSavedExtras(setNote(EMPTY_EXTRAS, "s1", "remember"));
    expect((await getSavedExtras()).notes.s1).toBe("remember");
    await AsyncStorage.removeMany(LOCAL_DATA_KEYS);
    expect(await getSavedExtras()).toEqual(EMPTY_EXTRAS);
  });
});
