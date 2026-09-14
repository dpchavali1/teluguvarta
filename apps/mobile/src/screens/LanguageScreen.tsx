import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { EMPTY_PROFILE, getProfile, setLanguage, type OnboardingProfile } from "../lib/storage";
import { colors, radius, spacing, typography, ui } from "../theme/tokens";

const OPTIONS: { value: OnboardingProfile["language"]; label: string }[] = [
  { value: "en", label: "English" },
  { value: "te", label: "తెలుగు (Telugu)" },
];

export function LanguageScreen() {
  const [profile, setProfileState] = useState<OnboardingProfile>(EMPTY_PROFILE);

  useEffect(() => {
    getProfile().then(setProfileState);
  }, []);

  async function choose(language: OnboardingProfile["language"]) {
    setProfileState({ ...profile, language });
    await setLanguage(language);
  }

  return (
    <View style={styles.container}>
      <Text style={styles.groupLabel}>DISPLAY LANGUAGE</Text>
      <View style={styles.group}>
        {OPTIONS.map((option, index) => (
          <Pressable
            key={option.value}
            onPress={() => choose(option.value)}
            accessibilityRole="radio"
            accessibilityState={{ selected: profile.language === option.value }}
            accessibilityLabel={option.label}
            style={[styles.row, index < OPTIONS.length - 1 && styles.rowDivider, profile.language === option.value && styles.rowActive]}
          >
            <Text style={styles.label}>{option.label}</Text>
            {profile.language === option.value && <Text>✓</Text>}
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: spacing.md },
  groupLabel: {
    ...typography.meta,
    textTransform: "uppercase",
    letterSpacing: 1.2,
    color: colors.faint,
    paddingHorizontal: spacing.sm,
    paddingBottom: spacing.xs,
  },
  group: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderCurve: "continuous",
    borderWidth: 1,
    borderColor: ui.borderSubtle,
    overflow: "hidden",
  },
  row: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
  },
  rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: ui.borderSubtle },
  rowActive: { backgroundColor: ui.actionPrimarySoft },
  label: { ...typography.body },
});
