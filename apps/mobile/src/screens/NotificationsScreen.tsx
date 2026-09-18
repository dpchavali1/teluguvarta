import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

import type { RootStackParamList } from "../navigation/types";
import { spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

// Push delivery itself is T17 (not started) — this is the inbox shell the
// spec's §9.2 screen list calls for, with nothing to deliver into it yet.
// Preferences are editable here regardless, since disabling/tuning alerts
// must never be blocked on notifications actually existing yet.
export function NotificationsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>You&apos;re all caught up</Text>
      <Text style={styles.body}>
        Push notifications aren&apos;t live yet. When they are, alerts you&apos;ve subscribed to
        will show up here.
      </Text>
      <Pressable
        onPress={() => navigation.navigate("NotificationPreferences")}
        accessibilityRole="button"
        accessibilityLabel="Edit notification preferences"
        style={styles.button}
      >
        <Text style={styles.buttonText}>Edit notification preferences</Text>
      </Pressable>
    </ScrollView>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flexGrow: 1, padding: spacing.lg, gap: spacing.md, backgroundColor: colors.bg },
    title: { ...typography.headline, color: colors.text },
    body: { ...typography.body, color: ui.textSecondary },
    button: {
      minHeight: 44,
      justifyContent: "center",
      alignItems: "center",
      paddingHorizontal: 16,
      borderRadius: 8,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
      alignSelf: "flex-start",
    },
    buttonText: { color: colors.text, fontWeight: "600" },
  });
}
