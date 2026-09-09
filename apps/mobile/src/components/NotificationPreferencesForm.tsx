import React, { useEffect, useState } from "react";
import { StyleSheet, Switch, Text, TextInput, View } from "react-native";

import { getConfig, type TopicOut } from "../lib/api";
import type { NotificationPreferences } from "../lib/storage";

// §3.1/§9.2: independent per-topic toggles, quiet hours, max alert
// frequency, and disable-all-without-losing-news-access. `disableAll` only
// ever gates push delivery (T17) — it never touches feed/browsing access,
// so it's rendered here with no interaction with any other screen's data.
export function NotificationPreferencesForm({
  value,
  onChange,
}: {
  value: NotificationPreferences;
  onChange: (next: NotificationPreferences) => void;
}) {
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

  function set<K extends keyof NotificationPreferences>(key: K, v: NotificationPreferences[K]) {
    onChange({ ...value, [key]: v });
  }

  function setTopicEnabled(slug: string, enabled: boolean) {
    onChange({ ...value, topics: { ...value.topics, [slug]: enabled } });
  }

  return (
    <View style={styles.container}>
      <Row label="Enable notifications" accessibilityLabel="Enable notifications, does not affect browsing the feed">
        <Switch
          value={!value.disableAll}
          onValueChange={(enabled) => set("disableAll", !enabled)}
        />
      </Row>
      <Text style={styles.hint}>
        Turning this off stops all alerts. You can keep reading the feed either way.
      </Text>

      <Row label="Breaking news alerts">
        <Switch value={value.breakingEnabled} onValueChange={(v) => set("breakingEnabled", v)} />
      </Row>
      <Row label="Daily briefing">
        <Switch
          value={value.dailyBriefingEnabled}
          onValueChange={(v) => set("dailyBriefingEnabled", v)}
        />
      </Row>

      {topics.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Topics</Text>
          {topics.map((topic) => (
            <Row key={topic.slug} label={topic.name}>
              <Switch
                value={value.topics[topic.slug] ?? true}
                onValueChange={(v) => setTopicEnabled(topic.slug, v)}
              />
            </Row>
          ))}
        </View>
      )}

      <View style={styles.section}>
        <Row label="Quiet hours">
          <Switch
            value={value.quietHoursEnabled}
            onValueChange={(v) => set("quietHoursEnabled", v)}
          />
        </Row>
        {value.quietHoursEnabled && (
          <View style={styles.timeRow}>
            <TextInput
              value={value.quietHoursStart}
              onChangeText={(v) => set("quietHoursStart", v)}
              accessibilityLabel="Quiet hours start time"
              placeholder="22:00"
              style={styles.timeInput}
            />
            <Text>to</Text>
            <TextInput
              value={value.quietHoursEnd}
              onChangeText={(v) => set("quietHoursEnd", v)}
              accessibilityLabel="Quiet hours end time"
              placeholder="07:00"
              style={styles.timeInput}
            />
          </View>
        )}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Max alerts per day</Text>
        <TextInput
          value={String(value.maxPerDay)}
          onChangeText={(text) => {
            const n = Number.parseInt(text, 10);
            set("maxPerDay", Number.isFinite(n) && n >= 0 ? n : 0);
          }}
          keyboardType="number-pad"
          accessibilityLabel="Maximum alerts per day"
          style={styles.numberInput}
        />
      </View>
    </View>
  );
}

function Row({
  label,
  accessibilityLabel,
  children,
}: {
  label: string;
  accessibilityLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.row} accessible accessibilityLabel={accessibilityLabel ?? label}>
      <Text style={styles.rowLabel}>{label}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 8 },
  row: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 6,
  },
  rowLabel: { fontSize: 16, flexShrink: 1, paddingRight: 12 },
  hint: { fontSize: 13, color: "#666", marginBottom: 8 },
  section: { marginTop: 16 },
  sectionTitle: { fontSize: 15, fontWeight: "700", marginBottom: 4 },
  timeRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  timeInput: {
    minHeight: 44,
    minWidth: 80,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#ccc",
  },
  numberInput: {
    minHeight: 44,
    width: 80,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#ccc",
  },
});
