import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { STUDENT_TOPIC_SLUGS } from "@teluguvarta/domain";
import React, { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

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
import { typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

type Styles = ReturnType<typeof createStyles>;

// §3.1: every step skippable, "continue without login" always available and
// never blocking browsing. The step index and draft answers are local
// component state — nothing is persisted until a step is confirmed or the
// whole flow is skipped, so backing out mid-flow (app kill) never leaves a
// half-written profile behind.
const STEP_COUNT = 7; // welcome, location, life stage, student, interests, language, notifications

export function OnboardingScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  // headerShown is false for this route, so nothing else keeps the skip
  // link out from under the status bar / Dynamic Island.
  const insets = useSafeAreaInsets();
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
    <View style={[styles.container, { paddingTop: insets.top }]}>
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
          <StepShell title="Welcome to TTE" styles={styles}>
            <Text style={styles.body}>
              News for the Telugu diaspora, in English and Telugu. Browsing never requires an
              account. A few optional questions help personalize your feed — skip any of them at
              any time.
            </Text>
          </StepShell>
        )}

        {step === 1 && (
          <StepShell title="Where are you based? (optional)" styles={styles}>
            <TextInput
              value={profile.residenceCountry ?? ""}
              onChangeText={(v) => setProfileDraft({ ...profile, residenceCountry: v })}
              placeholder="Country"
              placeholderTextColor={ui.textTertiary}
              accessibilityLabel="Country of residence"
              style={styles.input}
            />
            <TextInput
              value={profile.homeRegion ?? ""}
              onChangeText={(v) => setProfileDraft({ ...profile, homeRegion: v })}
              placeholder="State / region"
              placeholderTextColor={ui.textTertiary}
              accessibilityLabel="Home state or region"
              style={styles.input}
            />
            <TextInput
              value={profile.homeCity ?? ""}
              onChangeText={(v) => setProfileDraft({ ...profile, homeCity: v })}
              placeholder="City"
              placeholderTextColor={ui.textTertiary}
              accessibilityLabel="Home city"
              style={styles.input}
            />
          </StepShell>
        )}

        {step === 2 && (
          <StepShell title="Which best describes you? (optional)" styles={styles}>
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
                  <Text style={styles.optionLabel}>{option.label}</Text>
                </Pressable>
              );
            })}
          </StepShell>
        )}

        {step === 3 && (
          <StepShell title="A bit more about your studies (optional)" styles={styles}>
            <Text style={styles.hint}>
              We never ask for your university name or immigration documents.
            </Text>
            <TextInput
              value={profile.student?.studyCountry ?? ""}
              onChangeText={(v) =>
                setProfileDraft({ ...profile, student: { ...profile.student, studyCountry: v } })
              }
              placeholder="Country of study"
              placeholderTextColor={ui.textTertiary}
              accessibilityLabel="Country of study"
              style={styles.input}
            />
            <TextInput
              value={profile.student?.studyRegion ?? ""}
              onChangeText={(v) =>
                setProfileDraft({ ...profile, student: { ...profile.student, studyRegion: v } })
              }
              placeholder="State / region of study"
              placeholderTextColor={ui.textTertiary}
              accessibilityLabel="State or region of study"
              style={styles.input}
            />
            <TextInput
              value={profile.student?.studyMetro ?? ""}
              onChangeText={(v) =>
                setProfileDraft({ ...profile, student: { ...profile.student, studyMetro: v } })
              }
              placeholder="Nearest city / metro"
              placeholderTextColor={ui.textTertiary}
              accessibilityLabel="Nearest city or metro area"
              style={styles.input}
            />
            <TextInput
              value={profile.student?.degreeLevel ?? ""}
              onChangeText={(v) =>
                setProfileDraft({ ...profile, student: { ...profile.student, degreeLevel: v } })
              }
              placeholder="Degree level (e.g. Master's)"
              placeholderTextColor={ui.textTertiary}
              accessibilityLabel="Degree level"
              style={styles.input}
            />
          </StepShell>
        )}

        {step === 4 && (
          <StepShell title="What are you interested in? (optional)" styles={styles}>
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
              styles={styles}
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
                  styles={styles}
                />
              </>
            )}
          </StepShell>
        )}

        {step === 5 && (
          <StepShell title="Preferred language" styles={styles}>
            <LanguageChoice
              value={profile.language}
              onChange={(language) => setProfileDraft({ ...profile, language })}
              styles={styles}
            />
          </StepShell>
        )}

        {step === 6 && (
          <StepShell title="Notification preferences (optional)" styles={styles}>
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
          <Text style={styles.footerButtonText}>{step === 0 ? "Get started" : "Skip"}</Text>
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
  styles,
}: {
  topics: TopicOut[];
  selectedSlugs: string[];
  onToggle: (slug: string, wasSelected: boolean) => void;
  styles: Styles;
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
            <Text style={styles.chipText}>{topic.name}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function StepShell({ title, children, styles }: { title: string; children: React.ReactNode; styles: Styles }) {
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
  styles,
}: {
  value: OnboardingProfile["language"];
  onChange: (v: OnboardingProfile["language"]) => void;
  styles: Styles;
}) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>English</Text>
      <Switch
        value={value === "te"}
        onValueChange={(isTelugu) => onChange(isTelugu ? "te" : "en")}
        accessibilityLabel="Toggle preferred language between English and Telugu"
        accessibilityRole="switch"
        accessibilityState={{ checked: value === "te" }}
      />
      <Text style={styles.rowLabel}>తెలుగు</Text>
    </View>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    skipAll: { alignSelf: "flex-end", minHeight: 44, justifyContent: "center", paddingHorizontal: 16 },
    skipAllText: { color: ui.actionText },
    content: { padding: 16, flexGrow: 1 },
    step: { gap: 12 },
    stepTitle: { ...typography.headline, color: colors.text },
    body: { ...typography.body, color: ui.textSecondary },
    hint: { ...typography.meta, textTransform: "none", color: ui.textTertiary },
    input: {
      minHeight: 44,
      paddingHorizontal: 12,
      borderRadius: 8,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
      color: colors.text,
    },
    optionRow: {
      minHeight: 44,
      justifyContent: "center",
      paddingHorizontal: 12,
      borderRadius: 8,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
    },
    optionRowActive: { backgroundColor: ui.actionPrimarySoft, borderColor: ui.actionPrimary },
    optionLabel: { ...typography.body, color: colors.text },
    chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    chip: {
      minHeight: 44,
      justifyContent: "center",
      paddingHorizontal: 14,
      borderRadius: 16,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
    },
    chipActive: { backgroundColor: ui.actionPrimarySoft, borderColor: ui.actionPrimary },
    chipText: { ...typography.body, color: colors.text },
    row: { flexDirection: "row", alignItems: "center", gap: 12 },
    rowLabel: { ...typography.body, color: colors.text },
    footer: {
      flexDirection: "row",
      justifyContent: "flex-end",
      gap: 12,
      padding: 16,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderColor: ui.borderSubtle,
      backgroundColor: colors.bg,
    },
    footerButton: {
      minHeight: 44,
      justifyContent: "center",
      alignItems: "center",
      paddingHorizontal: 16,
      borderRadius: 8,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
    },
    footerButtonText: { color: colors.text },
    footerButtonPrimary: { backgroundColor: ui.actionPrimary, borderColor: ui.actionPrimary },
    footerButtonPrimaryText: { color: ui.actionPrimaryText, fontWeight: "600" },
  });
}
