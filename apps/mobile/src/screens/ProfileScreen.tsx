import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  InterestFields,
  LifeStageFields,
  LocationFields,
  StudentFields,
  useConfigTopics,
} from "../components/ProfileFields";
import type { RootStackParamList } from "../navigation/types";
import { asksStudentDetails, getProfile, saveProfileEdits, type OnboardingProfile } from "../lib/storage";
import { typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

// Settings → "Your profile": the onboarding answers on one page, editable
// without redoing onboarding. Nothing is written until Save; going back
// discards the draft. Language and notifications have their own screens.
export function ProfileScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const insets = useSafeAreaInsets();
  const topics = useConfigTopics();
  const [draft, setDraft] = useState<OnboardingProfile | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getProfile().then((profile) => {
      if (!cancelled) setDraft(profile);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (draft === null) {
    return (
      <View style={[styles.container, styles.centered]}>
        <ActivityIndicator accessibilityLabel="Loading" />
      </View>
    );
  }

  async function save() {
    if (draft === null || saving) return;
    setSaving(true);
    try {
      await saveProfileEdits(draft);
      navigation.goBack();
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.intro}>
          These answers stay on this phone and only shape your Home feed. Every one is optional.
        </Text>
        <Section title="Where you're based" styles={styles}>
          <LocationFields profile={draft} onChange={setDraft} />
        </Section>
        <Section title="Which best describes you" styles={styles}>
          <LifeStageFields profile={draft} onChange={setDraft} />
        </Section>
        {asksStudentDetails(draft.lifeStages) && (
          <Section title="Your studies" styles={styles}>
            <StudentFields profile={draft} onChange={setDraft} />
          </Section>
        )}
        <Section title="Interests" styles={styles}>
          <InterestFields profile={draft} onChange={setDraft} topics={topics} />
        </Section>
      </ScrollView>
      <View style={[styles.footer, { paddingBottom: 16 + insets.bottom }]}>
        <Pressable
          onPress={save}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel="Save profile"
          accessibilityState={{ disabled: saving, busy: saving }}
          style={styles.saveButton}
        >
          <Text style={styles.saveButtonText}>Save</Text>
        </Pressable>
      </View>
    </View>
  );
}

function Section({
  title,
  children,
  styles,
}: {
  title: string;
  children: React.ReactNode;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle} accessibilityRole="header">
        {title}
      </Text>
      {children}
    </View>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    centered: { alignItems: "center", justifyContent: "center" },
    content: { padding: 16, gap: 24 },
    intro: { ...typography.body, color: ui.textSecondary },
    section: { gap: 12 },
    sectionTitle: { ...typography.headline, color: colors.text },
    footer: {
      flexDirection: "row",
      justifyContent: "flex-end",
      padding: 16,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderColor: ui.borderSubtle,
      backgroundColor: colors.bg,
    },
    saveButton: {
      minHeight: 44,
      justifyContent: "center",
      alignItems: "center",
      paddingHorizontal: 24,
      borderRadius: 8,
      borderCurve: "continuous",
      backgroundColor: ui.actionPrimary,
    },
    saveButtonText: { color: ui.actionPrimaryText, fontWeight: "600" },
  });
}
