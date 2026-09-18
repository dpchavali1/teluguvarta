import React, { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { getProfile, setLanguage, type OnboardingProfile } from "../lib/storage";
import { spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

// Design-review fix: on web this is a one-tap, persistent header control.
// On mobile it was two taps deep in Settings, the biggest cross-surface IA
// gap the design review found for a bilingual-content product. Mirrors
// apps/web/src/components/LanguageToggle.tsx's EN/తె two-button group,
// mounted in MainTabs' header so it's visible from every main tab.
export function LanguageToggle() {
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
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

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    group: {
      flexDirection: "row",
      borderWidth: 1,
      borderColor: ui.borderControl,
      marginRight: spacing.md,
    },
    button: {
      // 44x44 matches the touch-target minimum used everywhere else in the
      // app (StoryCard, forms, screens) — this was the one outlier at 32x36.
      minHeight: 44,
      minWidth: 44,
      paddingHorizontal: spacing.xs,
      justifyContent: "center",
      alignItems: "center",
    },
    buttonRight: { borderLeftWidth: 1, borderLeftColor: ui.borderControl },
    // Matches web's toggle "pressed" convention: accent fill, ink text.
    buttonActive: { backgroundColor: ui.actionPrimarySoft },
    buttonText: { ...typography.meta, textTransform: "none", color: colors.text },
    buttonTextActive: { color: ui.actionText },
  });
}
