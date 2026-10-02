import { STUDENT_TOPIC_SLUGS } from "@teluguvarta/domain";
import React, { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";

import { getConfig, type TopicOut } from "../lib/api";
import { pushProjectId } from "../lib/push";
import type { NotificationPreferences } from "../lib/storage";
import { radius, spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

type Styles = ReturnType<typeof createStyles>;

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
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const [topics, setTopics] = useState<TopicOut[]>([]);
  const [topicsFailed, setTopicsFailed] = useState(false);
  const [pushServiceEnabled, setPushServiceEnabled] = useState<boolean | null>(null);
  const [search, setSearch] = useState("");
  const [selectedOnly, setSelectedOnly] = useState(false);
  const selectedCount = topics.filter((topic) => value.topics[topic.slug] === true).length;
  const query = search.trim().toLocaleLowerCase();
  const visibleTopics = topics.filter((topic) =>
    (!selectedOnly || value.topics[topic.slug] === true)
    && (query === "" || topic.name.toLocaleLowerCase().includes(query) || topic.slug.toLocaleLowerCase().includes(query))
  );
  const generalTopics = visibleTopics.filter((topic) => !STUDENT_TOPIC_SLUGS.includes(topic.slug as (typeof STUDENT_TOPIC_SLUGS)[number]));
  const studentTopics = visibleTopics.filter((topic) => STUDENT_TOPIC_SLUGS.includes(topic.slug as (typeof STUDENT_TOPIC_SLUGS)[number]));

  useEffect(() => {
    let cancelled = false;
    getConfig()
      .then((config) => {
        if (!cancelled) {
          setTopics(config.topics);
          setPushServiceEnabled(config.features?.push_notifications_enabled ?? null);
        }
      })
      .catch(() => {
        if (!cancelled) setTopicsFailed(true);
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
      <Text style={styles.groupLabel} accessibilityRole="header">PUSH ALERTS</Text>
      {(pushServiceEnabled === false || !pushProjectId()) && (
        <Text style={styles.hint} accessibilityRole="alert">
          Push alerts are not available yet. Your choices will be saved, but notifications will not arrive until delivery is set up.
        </Text>
      )}
      <View style={styles.group}>
        <Row label="Send alerts" styles={styles}>
          <Switch
            value={!value.disableAll}
            onValueChange={(enabled) => set("disableAll", !enabled)}
            accessibilityLabel="Send alerts"
          />
        </Row>
      </View>
      <Text style={styles.hint}>
        {value.disableAll
          ? "Alerts are paused. Your choices below are saved for when you turn them back on. You can still read every story."
          : "Your phone must also allow notifications for this app."}
      </Text>

      <Text style={styles.groupLabel} accessibilityRole="header">WHAT YOU GET</Text>
      <View style={styles.group}>
        <Row label="Breaking news" divider disabled={value.disableAll} styles={styles}>
          <Switch value={value.breakingEnabled} onValueChange={(v) => set("breakingEnabled", v)} disabled={value.disableAll} accessibilityLabel="Breaking news alerts" />
        </Row>
        <Row label="Daily briefing" disabled={value.disableAll} styles={styles}>
          <Switch
            value={value.dailyBriefingEnabled}
            onValueChange={(v) => set("dailyBriefingEnabled", v)}
            disabled={value.disableAll}
            accessibilityLabel="Daily briefing alerts"
          />
        </Row>
      </View>
      <Text style={styles.groupLabel} accessibilityRole="header">WHEN YOU GET THEM</Text>
      <View style={styles.group}>
        <Row label="Pause overnight" divider={value.quietHoursEnabled} disabled={value.disableAll} styles={styles}>
          <Switch
            value={value.quietHoursEnabled}
            onValueChange={(v) => set("quietHoursEnabled", v)}
            disabled={value.disableAll}
            accessibilityLabel="Pause alerts overnight"
          />
        </Row>
        {value.quietHoursEnabled && (
          <>
            <View style={[styles.timeRow, value.disableAll && styles.disabled]}>
              <Text style={styles.rowLabel}>From</Text>
              <HourStepper label="Quiet hours start" value={value.quietHoursStart} onChange={(v) => set("quietHoursStart", v)} disabled={value.disableAll} styles={styles} />
            </View>
            <View style={[styles.timeRow, value.disableAll && styles.disabled]}>
              <Text style={styles.rowLabel}>Until</Text>
              <HourStepper label="Quiet hours end" value={value.quietHoursEnd} onChange={(v) => set("quietHoursEnd", v)} disabled={value.disableAll} styles={styles} />
            </View>
          </>
        )}
        <View style={styles.rowDivider} />
        <View style={[styles.timeRow, value.disableAll && styles.disabled]}>
          <Text style={styles.rowLabel}>Max alerts per day</Text>
          <NumberStepper label="Maximum alerts per day" value={value.maxPerDay} min={0} onChange={(v) => set("maxPerDay", v)} disabled={value.disableAll} styles={styles} />
        </View>
      </View>
      <Text style={styles.hint}>0 means no alerts. Overnight times use whole hours on your phone.</Text>

      <Text style={styles.groupLabel} accessibilityRole="header">TOPIC ALERTS</Text>
      {topics.length > 0 ? (
        <>
          <Text style={styles.hint}>Turn on the topics you want alerts about. {selectedCount} selected.</Text>
          <View style={styles.searchRow}>
            <TextInput
              value={search}
              onChangeText={setSearch}
              placeholder="Search topics"
              placeholderTextColor={ui.textTertiary}
              accessibilityLabel="Search alert topics"
              autoCorrect={false}
              returnKeyType="search"
              style={styles.searchInput}
            />
            {search !== "" ? (
              <Pressable accessibilityRole="button" accessibilityLabel="Clear topic search" onPress={() => setSearch("")} style={styles.clearButton}>
                <Text style={styles.clearText}>Clear</Text>
              </Pressable>
            ) : null}
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={selectedOnly ? "Show all alert topics" : "Show selected alert topics only"}
            accessibilityState={{ selected: selectedOnly }}
            onPress={() => setSelectedOnly((current) => !current)}
            style={[styles.filterButton, selectedOnly && styles.filterButtonActive]}
          >
            <Text style={[styles.filterText, selectedOnly && styles.filterTextActive]}>
              {selectedOnly ? "Showing selected topics" : `Show selected only (${selectedCount})`}
            </Text>
          </Pressable>
          {visibleTopics.length === 0 ? (
            <Text style={styles.hint}>{selectedOnly && selectedCount === 0 ? "No topics selected yet. Show all topics to choose some." : "No topics match your search."}</Text>
          ) : null}
          <TopicSection title="General" topics={generalTopics} value={value} onToggle={setTopicEnabled} disabled={value.disableAll} styles={styles} />
          {/* S2: student alert topics remain independent entries in `value.topics`. */}
          <TopicSection title="Student" topics={studentTopics} value={value} onToggle={setTopicEnabled} disabled={value.disableAll} styles={styles} />
        </>
      ) : topicsFailed ? (
        <Text style={styles.hint} accessibilityRole="alert">Topic choices are unavailable right now. Your saved choices are kept.</Text>
      ) : (
        <Text style={styles.hint}>Loading topics…</Text>
      )}
    </View>
  );
}

function TopicSection({
  title,
  topics,
  value,
  onToggle,
  disabled,
  styles,
}: {
  title: string;
  topics: TopicOut[];
  value: NotificationPreferences;
  onToggle: (slug: string, enabled: boolean) => void;
  disabled: boolean;
  styles: Styles;
}) {
  if (topics.length === 0) return null;
  return (
    <>
      <Text style={styles.groupLabel} accessibilityRole="header">{title.toUpperCase()}</Text>
      <View style={styles.group}>
        {topics.map((topic, index) => (
          <Row key={topic.slug} label={topic.name} divider={index < topics.length - 1} disabled={disabled} styles={styles}>
            <Switch
              value={value.topics[topic.slug] ?? false}
              onValueChange={(v) => onToggle(topic.slug, v)}
              disabled={disabled}
              accessibilityLabel={`${topic.name} alerts`}
            />
          </Row>
        ))}
      </View>
    </>
  );
}

function Row({
  label,
  divider,
  disabled,
  children,
  styles,
}: {
  label: string;
  divider?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  styles: Styles;
}) {
  return (
    <View style={[styles.row, divider && styles.rowDivider, disabled && styles.disabled]}>
      <Text style={styles.rowLabel}>{label}</Text>
      {children}
    </View>
  );
}

function hourLabel(hour: number): string {
  const twelveHour = hour % 12 || 12;
  return `${twelveHour} ${hour < 12 ? "AM" : "PM"}`;
}

function HourStepper({ label, value, onChange, disabled, styles }: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  styles: Styles;
}) {
  const parsed = Number.parseInt(value.split(":")[0] ?? "", 10);
  const hour = Number.isFinite(parsed) && parsed >= 0 && parsed < 24 ? parsed : 0;
  const adjust = (direction: number) => onChange(`${String((hour + direction + 24) % 24).padStart(2, "0")}:00`);
  return (
    <View style={styles.stepper}>
      <Pressable style={styles.stepperButton} disabled={disabled} accessibilityRole="button" accessibilityLabel={`${label} one hour earlier`} onPress={() => adjust(-1)}>
        <Text style={styles.stepperButtonText}>−</Text>
      </Pressable>
      <Text style={styles.stepperValue} accessibilityLabel={`${label}: ${hourLabel(hour)}`}>{hourLabel(hour)}</Text>
      <Pressable style={styles.stepperButton} disabled={disabled} accessibilityRole="button" accessibilityLabel={`${label} one hour later`} onPress={() => adjust(1)}>
        <Text style={styles.stepperButtonText}>+</Text>
      </Pressable>
    </View>
  );
}

function NumberStepper({ label, value, min, onChange, disabled, styles }: {
  label: string;
  value: number;
  min: number;
  onChange: (value: number) => void;
  disabled: boolean;
  styles: Styles;
}) {
  return (
    <View style={styles.stepper}>
      <Pressable style={styles.stepperButton} disabled={disabled || value <= min} accessibilityRole="button" accessibilityLabel={`Decrease ${label.toLowerCase()}`} onPress={() => onChange(Math.max(min, value - 1))}>
        <Text style={styles.stepperButtonText}>−</Text>
      </Pressable>
      <Text style={styles.stepperValue} accessibilityLabel={`${label}: ${value}`}>{value}</Text>
      <Pressable style={styles.stepperButton} disabled={disabled} accessibilityRole="button" accessibilityLabel={`Increase ${label.toLowerCase()}`} onPress={() => onChange(value + 1)}>
        <Text style={styles.stepperButtonText}>+</Text>
      </Pressable>
    </View>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
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
    rowLabel: { ...typography.body, color: colors.text, flexShrink: 1, paddingRight: 12 },
    disabled: { opacity: 0.48 },
    hint: { ...typography.meta, textTransform: "none", color: ui.textTertiary, paddingHorizontal: spacing.sm },
    searchRow: { minHeight: 48, flexDirection: "row", alignItems: "center", backgroundColor: colors.surface, borderRadius: radius.lg, borderCurve: "continuous", borderWidth: 1, borderColor: ui.borderControl },
    searchInput: { ...typography.body, flex: 1, minHeight: 48, color: colors.text, paddingHorizontal: spacing.md },
    clearButton: { minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.md },
    clearText: { ...typography.body, color: colors.accent, fontWeight: "600" },
    filterButton: { minHeight: 44, alignSelf: "flex-start", justifyContent: "center", paddingHorizontal: spacing.md, borderRadius: radius.pill, borderCurve: "continuous", borderWidth: 1, borderColor: ui.borderControl, backgroundColor: colors.surface },
    filterButtonActive: { backgroundColor: colors.accentSoft, borderColor: colors.accent },
    filterText: { ...typography.meta, textTransform: "none", color: colors.text },
    filterTextActive: { color: colors.accentInk },
    timeRow: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 8, paddingVertical: spacing.xs },
    stepper: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
    stepperButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center", borderRadius: radius.md, borderCurve: "continuous", borderWidth: 1, borderColor: ui.borderControl },
    stepperButtonText: { ...typography.body, color: colors.text, fontWeight: "700" },
    stepperValue: { ...typography.body, color: colors.text, minWidth: 50, textAlign: "center", fontVariant: ["tabular-nums"] },
  });
}
