import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { STUDENT_TOPIC_SLUGS } from "@teluguvarta/domain";
import React, { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";

import { NotificationPreferencesForm } from "../components/NotificationPreferencesForm";
import { getConfig, trackEvent, type TopicOut } from "../lib/api";
import type { RootStackParamList } from "../navigation/types";
import {
  DEFAULT_NOTIFICATION_PREFERENCES,
  EMPTY_PROFILE,
  LIFE_STAGES,
  setNotificationPreferences,
  setOnboarded,
  setProfile,
  type NotificationPreferences,
  type OnboardingProfile,
} from "../lib/storage";
import { ui } from "../theme/tokens";

// §3.1: every step skippable, "continue without login" always available and
// never blocking browsing. The step index and draft answers are local
// component state — nothing is persisted until a step is confirmed or the
// whole flow is skipped, so backing out mid-flow (app kill) never leaves a
// half-written profile behind.
const STEP_COUNT = 7; // welcome, location, life stage, student, interests, language, notifications

export function OnboardingScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [step, setStep] = useState(0);
  const [profile, setProfileDraft] = useState<OnboardingProfile>(EMPTY_PROFILE);
  const [prefs, setPrefsDraft] = useState<NotificationPreferences>(DEFAULT_NOTIFICATION_PREFERENCES);
  const [topics, setTopics] = useState<TopicOut[]>([]);

  useEffect(() => {
    let cancelled = false;
    getConfig()
      .then((config) => {
        if (!cancelled) setTopics(config.topics);
      })
      .catch(() => {
        if (!cancelled) setTopics([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function finish(finalProfile: OnboardingProfile, finalPrefs: NotificationPreferences) {
    await setProfile(finalProfile);
    await setNotificationPreferences(finalPrefs);
    await setOnboarded(true);
    // A person can select more than one life stage now (ADR-005 addendum);
    // report the full set plus the primary one the API's `segment` param
    // will actually use, rather than silently dropping every stage but one.
    trackEvent("onboarding_complete", {
      life_stages: finalProfile.lifeStages.join(","),
      life_stage_count: finalProfile.lifeStages.length,
    });
    navigation.reset({ index: 0, routes: [{ name: "Main" }] });
  }

  function next() {
    const isStudentStep = step === 2 && !profile.lifeStages.includes("INTERNATIONAL_STUDENT");
    const nextStep = isStudentStep ? step + 2 : step + 1;
    if (nextStep >= STEP_COUNT) {
      finish(profile, prefs);
    } else {
      setStep(nextStep);
    }
  }

  function skipAll() {
    finish(profile, prefs);
  }

  return (
    <View style={styles.container}>
      <Pressable
        onPress={skipAll}
        accessibilityRole="button"
        accessibilityLabel="Continue without login"
        style={styles.skipAll}
      >
        <Text style={styles.skipAllText}>Continue without login</Text>
      </Pressable>

      <ScrollView contentContainerStyle={styles.content}>
        {step === 0 && (
          <StepShell title="Welcome to TTE">
            <Text style={styles.body}>
              News for the Telugu diaspora, in English and Telugu. Browsing never requires an
              account. A few optional questions help personalize your feed — skip any of them at
              any time.
            </Text>
          </StepShell>
        )}

        {step === 1 && (
          <StepShell title="Where are you based? (optional)">
            <TextInput
              value={profile.residenceCountry ?? ""}
              onChangeText={(v) => setProfileDraft({ ...profile, residenceCountry: v })}
              placeholder="Country"
              accessibilityLabel="Country of residence"
              style={styles.input}
            />
            <TextInput
              value={profile.homeRegion ?? ""}
              onChangeText={(v) => setProfileDraft({ ...profile, homeRegion: v })}
              placeholder="State / region"
              accessibilityLabel="Home state or region"
              style={styles.input}
            />
            <TextInput
              value={profile.homeCity ?? ""}
              onChangeText={(v) => setProfileDraft({ ...profile, homeCity: v })}
              placeholder="City"
              accessibilityLabel="Home city"
              style={styles.input}
            />
          </StepShell>
        )}

        {step === 2 && (
          <StepShell title="Which best describes you? (optional)">
            <Text style={styles.hint}>Select every option that applies — you're not just one thing.</Text>
            {LIFE_STAGES.map((option) => {
              const selected = profile.lifeStages.includes(option.value);
              return (
                <Pressable
                  key={option.value}
                  onPress={() =>
                    setProfileDraft({
                      ...profile,
                      lifeStages: selected
                        ? profile.lifeStages.filter((s) => s !== option.value)
                        : [...profile.lifeStages, option.value],
                    })
                  }
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: selected }}
                  accessibilityLabel={option.label}
                  style={[styles.optionRow, selected && styles.optionRowActive]}
                >
                  <Text>{option.label}</Text>
                </Pressable>
              );
            })}
          </StepShell>
        )}

        {step === 3 && (
          <StepShell title="A bit more about your studies (optional)">
            <Text style={styles.hint}>
              We never ask for your university name or immigration documents.
            </Text>
            <TextInput
              value={profile.student?.studyCountry ?? ""}
              onChangeText={(v) =>
                setProfileDraft({ ...profile, student: { ...profile.student, studyCountry: v } })
              }
              placeholder="Country of study"
              accessibilityLabel="Country of study"
              style={styles.input}
            />
            <TextInput
              value={profile.student?.studyRegion ?? ""}
              onChangeText={(v) =>
                setProfileDraft({ ...profile, student: { ...profile.student, studyRegion: v } })
              }
              placeholder="State / region of study"
              accessibilityLabel="State or region of study"
              style={styles.input}
            />
            <TextInput
              value={profile.student?.studyMetro ?? ""}
              onChangeText={(v) =>
                setProfileDraft({ ...profile, student: { ...profile.student, studyMetro: v } })
              }
              placeholder="Nearest city / metro"
              accessibilityLabel="Nearest city or metro area"
              style={styles.input}
            />
            <TextInput
              value={profile.student?.degreeLevel ?? ""}
              onChangeText={(v) =>
                setProfileDraft({ ...profile, student: { ...profile.student, degreeLevel: v } })
              }
              placeholder="Degree level (e.g. Master's)"
              accessibilityLabel="Degree level"
              style={styles.input}
            />
          </StepShell>
        )}

        {step === 4 && (
          <StepShell title="What are you interested in? (optional)">
            <TopicChips
              topics={topics.filter((t) => !STUDENT_TOPIC_SLUGS.includes(t.slug as (typeof STUDENT_TOPIC_SLUGS)[number]))}
              selectedSlugs={profile.interestTopicSlugs}
              onToggle={(slug, selected) =>
                setProfileDraft({
                  ...profile,
                  interestTopicSlugs: selected
                    ? profile.interestTopicSlugs.filter((s) => s !== slug)
                    : [...profile.interestTopicSlugs, slug],
                })
              }
            />
            {/* S2: student topics (F-1, OPT, campus safety, etc.) are the
                same kind of Topic row as the general ones above, shown as a
                separate group per §3.1 rather than mixed in — selecting or
                clearing this group never touches interestTopicSlugs entries
                from the general group. */}
            {topics.some((t) => STUDENT_TOPIC_SLUGS.includes(t.slug as (typeof STUDENT_TOPIC_SLUGS)[number])) && (
              <>
                <Text style={styles.hint}>Student topics</Text>
                <TopicChips
                  topics={topics.filter((t) => STUDENT_TOPIC_SLUGS.includes(t.slug as (typeof STUDENT_TOPIC_SLUGS)[number]))}
                  selectedSlugs={profile.interestTopicSlugs}
                  onToggle={(slug, selected) =>
                    setProfileDraft({
                      ...profile,
                      interestTopicSlugs: selected
                        ? profile.interestTopicSlugs.filter((s) => s !== slug)
                        : [...profile.interestTopicSlugs, slug],
                    })
                  }
                />
              </>
            )}
          </StepShell>
        )}

        {step === 5 && (
          <StepShell title="Preferred language">
            <LanguageChoice
              value={profile.language}
              onChange={(language) => setProfileDraft({ ...profile, language })}
            />
          </StepShell>
        )}

        {step === 6 && (
          <StepShell title="Notification preferences (optional)">
            <NotificationPreferencesForm value={prefs} onChange={setPrefsDraft} />
          </StepShell>
        )}
      </ScrollView>

      <View style={styles.footer}>
        <Pressable
          onPress={next}
          accessibilityRole="button"
          accessibilityLabel={step === 0 ? "Get started" : "Skip this step"}
          style={styles.footerButton}
        >
          <Text>{step === 0 ? "Get started" : "Skip"}</Text>
        </Pressable>
        {step > 0 && (
          <Pressable
            onPress={next}
            accessibilityRole="button"
            accessibilityLabel={step === STEP_COUNT - 1 ? "Finish" : "Continue"}
            style={[styles.footerButton, styles.footerButtonPrimary]}
          >
            <Text style={styles.footerButtonPrimaryText}>
              {step === STEP_COUNT - 1 ? "Finish" : "Continue"}
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

function TopicChips({
  topics,
  selectedSlugs,
  onToggle,
}: {
  topics: TopicOut[];
  selectedSlugs: string[];
  onToggle: (slug: string, wasSelected: boolean) => void;
}) {
  return (
    <View style={styles.chipWrap}>
      {topics.map((topic) => {
        const selected = selectedSlugs.includes(topic.slug);
        return (
          <Pressable
            key={topic.slug}
            onPress={() => onToggle(topic.slug, selected)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: selected }}
            accessibilityLabel={topic.name}
            style={[styles.chip, selected && styles.chipActive]}
          >
            <Text>{topic.name}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function StepShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.step}>
      <Text style={styles.stepTitle}>{title}</Text>
      {children}
    </View>
  );
}

function LanguageChoice({
  value,
  onChange,
}: {
  value: OnboardingProfile["language"];
  onChange: (v: OnboardingProfile["language"]) => void;
}) {
  return (
    <View style={styles.row}>
      <Text>English</Text>
      <Switch
        value={value === "te"}
        onValueChange={(isTelugu) => onChange(isTelugu ? "te" : "en")}
        accessibilityLabel="Toggle preferred language between English and Telugu"
        accessibilityRole="switch"
        accessibilityState={{ checked: value === "te" }}
      />
      <Text>తెలుగు</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  skipAll: { alignSelf: "flex-end", minHeight: 44, justifyContent: "center", paddingHorizontal: 16 },
  skipAllText: { color: ui.actionText },
  content: { padding: 16, flexGrow: 1 },
  step: { gap: 12 },
  stepTitle: { fontSize: 20, fontWeight: "700" },
  body: { fontSize: 15, color: ui.textSecondary },
  hint: { fontSize: 13, color: ui.textTertiary },
  input: {
    minHeight: 44,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: ui.borderControl,
  },
  optionRow: {
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: ui.borderControl,
  },
  optionRowActive: { backgroundColor: ui.actionPrimarySoft, borderColor: ui.actionPrimary },
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: ui.borderControl,
  },
  chipActive: { backgroundColor: ui.actionPrimarySoft, borderColor: ui.actionPrimary },
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  footer: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 12,
    padding: 16,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderColor: ui.borderSubtle,
  },
  footerButton: {
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: ui.borderControl,
  },
  footerButtonPrimary: { backgroundColor: ui.actionPrimary, borderColor: ui.actionPrimary },
  footerButtonPrimaryText: { color: ui.actionPrimaryText, fontWeight: "600" },
});
