import { STUDENT_TOPIC_SLUGS } from "@teluguvarta/domain";
import React, { useEffect, useState } from "react";
import { StyleSheet, Switch, Text, TextInput, View } from "react-native";

import { getConfig, type TopicOut } from "../lib/api";
import type { NotificationPreferences } from "../lib/storage";
import { colors, radius, spacing, typography, ui } from "../theme/tokens";

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
      <Text style={styles.groupLabel}>ALERTS</Text>
      <View style={styles.group}>
        <Row label="Enable notifications" accessibilityLabel="Enable notifications, does not affect browsing the feed" divider>
          <Switch
            value={!value.disableAll}
            onValueChange={(enabled) => set("disableAll", !enabled)}
          />
        </Row>
        <Row label="Breaking news alerts" divider>
          <Switch value={value.breakingEnabled} onValueChange={(v) => set("breakingEnabled", v)} />
        </Row>
        <Row label="Daily briefing">
          <Switch
            value={value.dailyBriefingEnabled}
            onValueChange={(v) => set("dailyBriefingEnabled", v)}
          />
        </Row>
      </View>
      <Text style={styles.hint}>
        Turning notifications off stops all alerts. You can keep reading the feed either way.
      </Text>

      {topics.length > 0 && (
        <TopicSection
          title="Topics"
          topics={topics.filter((t) => !STUDENT_TOPIC_SLUGS.includes(t.slug as (typeof STUDENT_TOPIC_SLUGS)[number]))}
          value={value}
          onToggle={setTopicEnabled}
        />
      )}

      {/* S2: student alert topics (F-1, OPT, campus safety, etc.) toggle
          independently of the general topics above — unsubscribing from all
          of one group leaves the other group's switches untouched, since
          each is just its own entry in `value.topics`. */}
      {topics.some((t) => STUDENT_TOPIC_SLUGS.includes(t.slug as (typeof STUDENT_TOPIC_SLUGS)[number])) && (
        <TopicSection
          title="Student topics"
          topics={topics.filter((t) => STUDENT_TOPIC_SLUGS.includes(t.slug as (typeof STUDENT_TOPIC_SLUGS)[number]))}
          value={value}
          onToggle={setTopicEnabled}
        />
      )}

      <Text style={styles.groupLabel}>TIMING</Text>
      <View style={styles.group}>
        <Row label="Quiet hours" divider={value.quietHoursEnabled}>
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
        <View style={styles.rowDivider} />
        <View style={styles.timeRow}>
          <Text style={styles.rowLabel}>Max alerts per day</Text>
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
    </View>
  );
}

function TopicSection({
  title,
  topics,
  value,
  onToggle,
}: {
  title: string;
  topics: TopicOut[];
  value: NotificationPreferences;
  onToggle: (slug: string, enabled: boolean) => void;
}) {
  if (topics.length === 0) return null;
  return (
    <>
      <Text style={styles.groupLabel}>{title.toUpperCase()}</Text>
      <View style={styles.group}>
        {topics.map((topic, index) => (
          <Row key={topic.slug} label={topic.name} divider={index < topics.length - 1}>
            <Switch
              value={value.topics[topic.slug] ?? true}
              onValueChange={(v) => onToggle(topic.slug, v)}
            />
          </Row>
        ))}
      </View>
    </>
  );
}

function Row({
  label,
  accessibilityLabel,
  divider,
  children,
}: {
  label: string;
  accessibilityLabel?: string;
  divider?: boolean;
  children: React.ReactNode;
}) {
  return (
    <View style={[styles.row, divider && styles.rowDivider]} accessible accessibilityLabel={accessibilityLabel ?? label}>
      <Text style={styles.rowLabel}>{label}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: spacing.md },
  // Grouped-list pattern: a rounded, bordered container per group with
  // hairline dividers between rows, matching Settings/Language screens.
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
    paddingHorizontal: spacing.md,
  },
  row: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: ui.borderSubtle },
  rowLabel: { ...typography.body, flexShrink: 1, paddingRight: 12 },
  hint: { ...typography.meta, textTransform: "none", color: ui.textTertiary, paddingHorizontal: spacing.sm },
  timeRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8, paddingVertical: spacing.sm },
  timeInput: {
    minHeight: 44,
    minWidth: 80,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderCurve: "continuous",
    borderWidth: 1,
    borderColor: ui.borderControl,
  },
  numberInput: {
    minHeight: 44,
    width: 80,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderCurve: "continuous",
    borderWidth: 1,
    borderColor: ui.borderControl,
  },
});
