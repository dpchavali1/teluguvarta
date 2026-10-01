import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { NotificationPreferencesForm } from "../components/NotificationPreferencesForm";
import {
  InterestFields,
  LifeStageFields,
  LocationFields,
  StudentFields,
  useConfigTopics,
} from "../components/ProfileFields";
import { trackEvent } from "../lib/api";
import type { RootStackParamList } from "../navigation/types";
import {
  asksStudentDetails,
  DEFAULT_NOTIFICATION_PREFERENCES,
  EMPTY_PROFILE,
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
  const topics = useConfigTopics();

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
    const isStudentStep = step === 2 && !asksStudentDetails(profile.lifeStages);
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
            <LocationFields profile={profile} onChange={setProfileDraft} />
          </StepShell>
        )}

        {step === 2 && (
          <StepShell title="Which best describes you? (optional)" styles={styles}>
            <LifeStageFields profile={profile} onChange={setProfileDraft} />
          </StepShell>
        )}

        {step === 3 && (
          <StepShell title="A bit more about your studies (optional)" styles={styles}>
            <StudentFields profile={profile} onChange={setProfileDraft} />
          </StepShell>
        )}

        {step === 4 && (
          <StepShell title="What are you interested in? (optional)" styles={styles}>
            <InterestFields profile={profile} onChange={setProfileDraft} topics={topics} />
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
