import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React from "react";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

import type { RootStackParamList } from "../navigation/types";

// Push delivery itself is T17 (not started) — this is the inbox shell the
// spec's §9.2 screen list calls for, with nothing to deliver into it yet.
// Preferences are editable here regardless, since disabling/tuning alerts
// must never be blocked on notifications actually existing yet.
export function NotificationsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

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
        <Text>Edit notification preferences</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 12 },
  title: { fontSize: 18, fontWeight: "700" },
  body: { fontSize: 15, color: "#444" },
  button: {
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#ccc",
    alignSelf: "flex-start",
  },
});
