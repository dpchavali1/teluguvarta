/**
 * P01 persona presets. A preset is only a shortcut that sets explicit
 * choices (interest topics, alert topics, quiet hours) on the existing
 * preference stores. Nothing here infers or stores a persona server-side
 * (ADR-005, §3.1); the client keeps a local record of what each applied
 * preset added so removing it undoes only those choices.
 */
export type PersonaPresetId =
  | "student"
  | "h1b-green-card"
  | "family-back-home"
  | "farmer"
  | "investor"
  | "techie"
  | "movie-fan";

export type PersonaPreset = {
  id: PersonaPresetId;
  label: string;
  description: string;
  topics: readonly string[];
  /** Adds the INTERNATIONAL_STUDENT life stage so S1/S2 student flows apply. */
  student?: boolean;
  quietHours?: { start: string; end: string };
};

export const PERSONA_PRESETS: readonly PersonaPreset[] = [
  {
    id: "student",
    label: "Student (F-1 / OPT / H-1B)",
    description: "Visa, OPT, jobs, housing and campus updates.",
    topics: ["f1", "cpt", "opt", "stem-opt", "h1b-transition", "internships", "international-student-jobs", "scholarships"],
    student: true,
    quietHours: { start: "22:00", end: "07:00" },
  },
  {
    id: "h1b-green-card",
    label: "H-1B / Green Card holder",
    description: "Immigration, money, jobs and property.",
    topics: ["immigration", "money", "jobs", "property", "taxes"],
    quietHours: { start: "22:00", end: "07:00" },
  },
  {
    id: "family-back-home",
    label: "Family back home",
    description: "Andhra Pradesh, Telangana, Hyderabad and parents.",
    topics: ["andhra-pradesh", "telangana", "hyderabad", "parents", "community"],
  },
  {
    id: "farmer",
    label: "Farmer",
    description: "Andhra Pradesh and Telangana news and money.",
    topics: ["andhra-pradesh", "telangana", "money"],
  },
  {
    id: "investor",
    label: "Investor",
    description: "Money and property.",
    topics: ["money", "property"],
  },
  {
    id: "techie",
    label: "Techie",
    description: "Jobs, money and education.",
    topics: ["jobs", "money", "education"],
  },
  {
    id: "movie-fan",
    label: "Movie fan",
    description: "Entertainment and sports.",
    topics: ["entertainment", "sports"],
  },
];

/** What one applied preset added; removal reverts only these. */
export type AppliedPreset = {
  interests: string[];
  alertTopics: string[];
  lifeStage?: boolean;
  quietHours?: { start: string; end: string };
};

export type PersonaState = {
  interests: string[];
  lifeStages: string[];
  alertTopics: Record<string, boolean>;
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
  applied: Partial<Record<PersonaPresetId, AppliedPreset>>;
};

export function findPreset(id: PersonaPresetId): PersonaPreset | undefined {
  return PERSONA_PRESETS.find((p) => p.id === id);
}

const STUDENT_STAGE = "INTERNATIONAL_STUDENT";

// Another applied preset still wants this topic, whether or not it was the
// one that originally added it.
function ownedByOthers(state: PersonaState, skip: PersonaPresetId, slug: string) {
  return Object.keys(state.applied).some(
    (id) => id !== skip && findPreset(id as PersonaPresetId)?.topics.includes(slug),
  );
}

export function applyPreset(state: PersonaState, id: PersonaPresetId): PersonaState {
  const preset = findPreset(id);
  if (!preset || state.applied[id]) return state;
  const record: AppliedPreset = { interests: [], alertTopics: [] };
  const interests = [...state.interests];
  const alertTopics = { ...state.alertTopics };
  for (const slug of preset.topics) {
    if (!interests.includes(slug)) {
      interests.push(slug);
      record.interests.push(slug);
    }
    if (alertTopics[slug] !== true) {
      alertTopics[slug] = true;
      record.alertTopics.push(slug);
    }
  }
  const lifeStages = [...state.lifeStages];
  if (preset.student && !lifeStages.includes(STUDENT_STAGE)) {
    lifeStages.push(STUDENT_STAGE);
    record.lifeStage = true;
  }
  let { quietHoursEnabled, quietHoursStart, quietHoursEnd } = state;
  if (preset.quietHours && !quietHoursEnabled) {
    quietHoursEnabled = true;
    quietHoursStart = preset.quietHours.start;
    quietHoursEnd = preset.quietHours.end;
    record.quietHours = { ...preset.quietHours };
  }
  return {
    interests, lifeStages, alertTopics, quietHoursEnabled, quietHoursStart, quietHoursEnd,
    applied: { ...state.applied, [id]: record },
  };
}

export function removePreset(state: PersonaState, id: PersonaPresetId): PersonaState {
  const record = state.applied[id];
  if (!record) return state;
  const interests = state.interests.filter(
    (slug) => !record.interests.includes(slug) || ownedByOthers(state, id, slug),
  );
  const alertTopics = { ...state.alertTopics };
  for (const slug of record.alertTopics) {
    if (!ownedByOthers(state, id, slug)) alertTopics[slug] = false;
  }
  const stillStudent = Object.entries(state.applied).some(
    ([other, rec]) => other !== id && rec?.lifeStage,
  );
  const lifeStages = record.lifeStage && !stillStudent
    ? state.lifeStages.filter((s) => s !== STUDENT_STAGE)
    : state.lifeStages;
  let { quietHoursEnabled, quietHoursStart, quietHoursEnd } = state;
  const q = record.quietHours;
  const otherQuiet = Object.entries(state.applied).some(([other, rec]) => other !== id && rec?.quietHours);
  if (q && !otherQuiet && quietHoursStart === q.start && quietHoursEnd === q.end) {
    quietHoursEnabled = false;
  }
  const applied = { ...state.applied };
  delete applied[id];
  return { interests, lifeStages, alertTopics, quietHoursEnabled, quietHoursStart, quietHoursEnd, applied };
}
