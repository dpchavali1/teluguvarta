import { applyPreset, removePreset, type PersonaState } from "@teluguvarta/domain";

const base: PersonaState = {
  interests: ["sports"],
  lifeStages: [],
  alertTopics: { sports: true },
  quietHoursEnabled: false,
  quietHoursStart: "22:00",
  quietHoursEnd: "07:00",
  applied: {},
};

test("student preset reuses the student life stage and adds only its own topics", () => {
  const next = applyPreset(base, "student");
  expect(next.lifeStages).toEqual(["INTERNATIONAL_STUDENT"]);
  expect(next.interests).toEqual(expect.arrayContaining(["sports", "opt", "f1"]));
  expect(next.quietHoursEnabled).toBe(true);
});

test("removing a preset keeps user choices and topics another preset owns", () => {
  let s = applyPreset(base, "investor"); // money, property
  s = applyPreset(s, "techie"); // jobs, money, education
  s = { ...s, interests: [...s.interests, "travel"] }; // user's own pick
  s = removePreset(s, "investor");
  expect(s.interests).toEqual(expect.arrayContaining(["sports", "travel", "money", "jobs"]));
  expect(s.interests).not.toContain("property");
  expect(s.alertTopics.money).toBe(true);
  expect(s.alertTopics.property).toBe(false);
  expect(s.alertTopics.sports).toBe(true);
});

test("a topic the user already had stays after removal", () => {
  const withMoney = { ...base, interests: ["money"], alertTopics: { money: true } };
  const s = removePreset(applyPreset(withMoney, "investor"), "investor");
  expect(s.interests).toContain("money");
  expect(s.alertTopics.money).toBe(true);
  expect(s.applied).toEqual({});
});

test("quiet hours the user already set are left alone", () => {
  const custom = { ...base, quietHoursEnabled: true, quietHoursStart: "23:00", quietHoursEnd: "06:00" };
  const s = removePreset(applyPreset(custom, "student"), "student");
  expect(s.quietHoursEnabled).toBe(true);
  expect(s.quietHoursStart).toBe("23:00");
  expect(s.lifeStages).toEqual([]);
});
