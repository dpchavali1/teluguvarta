import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { RootStackParamList } from "../navigation/types";

export function SettingsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  return (
    <View style={styles.container}>
      <SettingsRow
        label="Notification preferences"
        onPress={() => navigation.navigate("NotificationPreferences")}
      />
      <SettingsRow label="Language" onPress={() => navigation.navigate("Language")} />
      <SettingsRow label="Privacy & delete account" onPress={() => navigation.navigate("Privacy")} />
    </View>
  );
}

function SettingsRow({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={styles.row}
    >
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.chevron}>›</Text>
    </Pressable>
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
  rowLabel: { fontSize: 16 },
  chevron: { fontSize: 18, color: "#999" },
});
