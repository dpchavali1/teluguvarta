import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { getProfile, setLanguage, type OnboardingProfile } from "../lib/storage";
import { colors, spacing } from "../theme/tokens";

// Design-review fix: on web this is a one-tap, persistent header control.
// On mobile it was two taps deep in Settings, the biggest cross-surface IA
// gap the design review found for a bilingual-content product. Mirrors
// apps/web/src/components/LanguageToggle.tsx's EN/తె two-button group,
// mounted in MainTabs' header so it's visible from every main tab.
export function LanguageToggle() {
  const [language, setLanguageState] = useState<OnboardingProfile["language"]>("en");

  useEffect(() => {
    getProfile().then((profile) => setLanguageState(profile.language));
  }, []);

  async function choose(next: OnboardingProfile["language"]) {
    setLanguageState(next);
    await setLanguage(next);
  }

  return (
    <View style={styles.group} accessibilityRole="radiogroup" accessibilityLabel="App language">
      <Pressable
        onPress={() => choose("en")}
        accessibilityRole="radio"
        accessibilityState={{ selected: language === "en" }}
        accessibilityLabel="English"
        style={[styles.button, language === "en" && styles.buttonActive]}
      >
        <Text style={[styles.buttonText, language === "en" && styles.buttonTextActive]}>EN</Text>
      </Pressable>
      <Pressable
        onPress={() => choose("te")}
        accessibilityRole="radio"
        accessibilityState={{ selected: language === "te" }}
        accessibilityLabel="తెలుగు"
        style={[styles.button, styles.buttonRight, language === "te" && styles.buttonActive]}
      >
        <Text style={[styles.buttonText, language === "te" && styles.buttonTextActive]}>తె</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  group: {
    flexDirection: "row",
    borderWidth: 1,
    borderColor: colors.rule,
    marginRight: spacing.md,
  },
  button: {
    minHeight: 32,
    minWidth: 36,
    paddingHorizontal: spacing.xs,
    justifyContent: "center",
    alignItems: "center",
  },
  buttonRight: { borderLeftWidth: 1, borderLeftColor: colors.rule },
  // Matches web's toggle "pressed" convention: accent fill, ink text.
  buttonActive: { backgroundColor: colors.accent },
  buttonText: { fontSize: 13, fontWeight: "600", color: colors.text },
  buttonTextActive: { color: colors.accentContrast },
});
