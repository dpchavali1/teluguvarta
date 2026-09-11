import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { EMPTY_PROFILE, getProfile, setLanguage, type OnboardingProfile } from "../lib/storage";

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
      {OPTIONS.map((option) => (
        <Pressable
          key={option.value}
          onPress={() => choose(option.value)}
          accessibilityRole="radio"
          accessibilityState={{ selected: profile.language === option.value }}
          accessibilityLabel={option.label}
          style={[styles.row, profile.language === option.value && styles.rowActive]}
        >
          <Text style={styles.label}>{option.label}</Text>
          {profile.language === option.value && <Text>✓</Text>}
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 8 },
  row: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: "#ddd",
  },
  rowActive: { backgroundColor: "#f0f6ff" },
  label: { fontSize: 16 },
});
