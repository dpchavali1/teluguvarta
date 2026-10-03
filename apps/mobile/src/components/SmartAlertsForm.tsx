import React, { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { getConfig, type TopicOut } from "../lib/api";
import {
  MAX_KEYWORD_LENGTH,
  MAX_KEYWORDS,
  type NotificationPreferences,
  type TopicUrgency,
} from "../lib/storage";
import { radius, spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

// P02: per-topic urgency, twice-daily digest, keyword follows and the two
// time zones quiet hours/digests use. Persisting/syncing is the caller's job.
const URGENCY_LABEL: Record<TopicUrgency, string> = {
  INSTANT: "Instant",
  BREAKING_ONLY: "Breaking only",
  DIGEST: "Digest",
};
const URGENCY_NEXT: Record<TopicUrgency, TopicUrgency> = {
  INSTANT: "BREAKING_ONLY",
  BREAKING_ONLY: "DIGEST",
  DIGEST: "INSTANT",
};

export function isValidTimeZone(tz: string): boolean {
  try {
    new Intl.DateTimeFormat("en", { timeZone: tz });
    return tz.includes("/") || tz === "UTC";
  } catch {
    return false;
  }
}

export function deviceTimeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone ?? null;
  } catch {
    return null;
  }
}

function hourLabel(hour: number): string {
  return `${hour % 12 || 12} ${hour < 12 ? "AM" : "PM"}`;
}

export function SmartAlertsForm({
  value,
  onChange,
}: {
  value: NotificationPreferences;
  onChange: (next: NotificationPreferences) => void;
}) {
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [topics, setTopics] = useState<TopicOut[]>([]);
  const [keywordDraft, setKeywordDraft] = useState("");
  const [tzDraft, setTzDraft] = useState({ home: value.homeTz ?? "", residence: value.residenceTz ?? "" });
  const disabled = value.disableAll;

  useEffect(() => {
    let cancelled = false;
    getConfig().then((c) => { if (!cancelled) setTopics(c.topics); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const enabledTopics = topics.filter((t) => value.topics[t.slug] === true);

  // A digest needs a zone to know what "morning" means; default to the phone's.
  function setDigest(key: "digestMorningHour" | "digestEveningHour", hour: number | null) {
    const residenceTz = value.residenceTz ?? (hour !== null ? deviceTimeZone() : null);
    if (residenceTz && !value.residenceTz) setTzDraft((d) => ({ ...d, residence: residenceTz }));
    onChange({ ...value, [key]: hour, residenceTz });
  }

  function addKeyword() {
    const keyword = keywordDraft.trim().toLowerCase().slice(0, MAX_KEYWORD_LENGTH);
    if (!keyword || value.keywords.includes(keyword) || value.keywords.length >= MAX_KEYWORDS) return;
    onChange({ ...value, keywords: [...value.keywords, keyword] });
    setKeywordDraft("");
  }

  function setTz(which: "home" | "residence", text: string) {
    setTzDraft((d) => ({ ...d, [which]: text }));
    const trimmed = text.trim();
    const key = which === "home" ? "homeTz" : "residenceTz";
    if (trimmed === "") onChange({ ...value, [key]: null });
    else if (isValidTimeZone(trimmed)) onChange({ ...value, [key]: trimmed });
  }

  return (
    <View style={[styles.container, disabled && styles.disabled]}>
      <Text style={styles.groupLabel} accessibilityRole="header">HOW OFTEN, PER TOPIC</Text>
      {enabledTopics.length === 0 ? (
        <Text style={styles.hint}>Turn on topic alerts above to choose how often each one reaches you.</Text>
      ) : (
        <View style={styles.group}>
          {enabledTopics.map((topic, i) => {
            const urgency = value.topicUrgency[topic.slug] ?? "INSTANT";
            return (
              <View key={topic.slug} style={[styles.row, i < enabledTopics.length - 1 && styles.divider]}>
                <Text style={styles.label}>{topic.name}</Text>
                <Pressable
                  disabled={disabled}
                  accessibilityRole="button"
                  accessibilityLabel={`${topic.name} alerts: ${URGENCY_LABEL[urgency]}. Tap to change`}
                  onPress={() => onChange({ ...value, topicUrgency: { ...value.topicUrgency, [topic.slug]: URGENCY_NEXT[urgency] } })}
                  style={styles.pill}
                >
                  <Text style={styles.pillText}>{URGENCY_LABEL[urgency]}</Text>
                </Pressable>
              </View>
            );
          })}
        </View>
      )}

      <Text style={styles.groupLabel} accessibilityRole="header">DIGEST</Text>
      <View style={styles.group}>
        <DigestRow label="Morning digest" hour={value.digestMorningHour} base={6} onChange={(h) => setDigest("digestMorningHour", h)} disabled={disabled} styles={styles} divider />
        <DigestRow label="Evening digest" hour={value.digestEveningHour} base={18} onChange={(h) => setDigest("digestEveningHour", h)} disabled={disabled} styles={styles} />
      </View>
      <Text style={styles.hint}>One notification with the stories you haven&apos;t already been alerted about. Times use your residence time zone.</Text>

      <Text style={styles.groupLabel} accessibilityRole="header">KEYWORDS</Text>
      <View style={styles.searchRow}>
        <TextInput
          value={keywordDraft}
          onChangeText={setKeywordDraft}
          onSubmitEditing={addKeyword}
          editable={!disabled}
          maxLength={MAX_KEYWORD_LENGTH}
          placeholder="e.g. H-1B, Hyderabad metro"
          placeholderTextColor={ui.textTertiary}
          accessibilityLabel="Add a keyword to follow"
          autoCorrect={false}
          returnKeyType="done"
          style={styles.input}
        />
        <Pressable accessibilityRole="button" accessibilityLabel="Add keyword" disabled={disabled} onPress={addKeyword} style={styles.pill}>
          <Text style={styles.pillText}>Add</Text>
        </Pressable>
      </View>
      <View style={styles.chips}>
        {value.keywords.map((k) => (
          <Pressable
            key={k}
            disabled={disabled}
            accessibilityRole="button"
            accessibilityLabel={`Stop following ${k}`}
            onPress={() => onChange({ ...value, keywords: value.keywords.filter((x) => x !== k) })}
            style={styles.pill}
          >
            <Text style={styles.pillText}>{k} ✕</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.hint}>Up to {MAX_KEYWORDS} keywords. Matched against story headlines; sensitive stories still need editor review before any alert.</Text>

      <Text style={styles.groupLabel} accessibilityRole="header">TIME ZONES</Text>
      <View style={styles.group}>
        <TzRow label="Residence" value={tzDraft.residence} placeholder={deviceTimeZone() ?? "America/Chicago"} onChange={(t) => setTz("residence", t)} disabled={disabled} styles={styles} ui={ui} divider />
        <TzRow label="Home" value={tzDraft.home} placeholder="Asia/Kolkata" onChange={(t) => setTz("home", t)} disabled={disabled} styles={styles} ui={ui} />
      </View>
      <Text style={styles.hint}>Quiet hours pause alerts when either zone is in the quiet window. Use names like America/Chicago; leave empty to skip.</Text>
    </View>
  );
}

type Styles = ReturnType<typeof createStyles>;

function DigestRow({ label, hour, base, onChange, disabled, styles, divider }: {
  label: string; hour: number | null; base: number; onChange: (h: number | null) => void;
  disabled: boolean; styles: Styles; divider?: boolean;
}) {
  const step = (d: number) => onChange((((hour ?? base) + d) % 24 + 24) % 24);
  return (
    <View style={[styles.row, divider && styles.divider]}>
      <Text style={styles.label}>{label}</Text>
      {hour === null ? (
        <Pressable disabled={disabled} accessibilityRole="button" accessibilityLabel={`Turn on ${label}`} onPress={() => onChange(base)} style={styles.pill}>
          <Text style={styles.pillText}>Off</Text>
        </Pressable>
      ) : (
        <View style={styles.stepper}>
          <Pressable disabled={disabled} accessibilityRole="button" accessibilityLabel={`${label} one hour earlier`} onPress={() => step(-1)} style={styles.pill}><Text style={styles.pillText}>−</Text></Pressable>
          <Text style={styles.label} accessibilityLabel={`${label}: ${hourLabel(hour)}`}>{hourLabel(hour)}</Text>
          <Pressable disabled={disabled} accessibilityRole="button" accessibilityLabel={`${label} one hour later`} onPress={() => step(1)} style={styles.pill}><Text style={styles.pillText}>+</Text></Pressable>
          <Pressable disabled={disabled} accessibilityRole="button" accessibilityLabel={`Turn off ${label}`} onPress={() => onChange(null)} style={styles.pill}><Text style={styles.pillText}>Off</Text></Pressable>
        </View>
      )}
    </View>
  );
}

function TzRow({ label, value, placeholder, onChange, disabled, styles, ui, divider }: {
  label: string; value: string; placeholder: string; onChange: (t: string) => void;
  disabled: boolean; styles: Styles; ui: AppTheme["ui"]; divider?: boolean;
}) {
  const invalid = value.trim() !== "" && !isValidTimeZone(value.trim());
  return (
    <View style={[styles.row, divider && styles.divider]}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChange}
        editable={!disabled}
        autoCapitalize="none"
        autoCorrect={false}
        placeholder={placeholder}
        placeholderTextColor={ui.textTertiary}
        accessibilityLabel={`${label} time zone`}
        accessibilityHint={invalid ? "Not a valid time zone name" : undefined}
        style={[styles.input, styles.tzInput, invalid && styles.invalid]}
      />
    </View>
  );
}

function createStyles(colors: AppTheme["colors"]) {
  return StyleSheet.create({
    container: { gap: spacing.md },
    disabled: { opacity: 0.5 },
    groupLabel: { ...typography.meta, textTransform: "uppercase", letterSpacing: 1.2, color: colors.faint, paddingHorizontal: spacing.sm },
    group: { backgroundColor: colors.surface, borderRadius: radius.lg, borderCurve: "continuous", borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, overflow: "hidden" },
    row: { minHeight: 52, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, gap: spacing.sm },
    divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    label: { color: colors.text, fontSize: 16, flexShrink: 1 },
    hint: { color: colors.muted, fontSize: 13, lineHeight: 18, paddingHorizontal: spacing.sm },
    pill: { minHeight: 44, minWidth: 44, justifyContent: "center", alignItems: "center", paddingHorizontal: 12, borderRadius: 22, borderWidth: 1, borderColor: colors.border },
    pillText: { color: colors.text, fontSize: 14, fontWeight: "600" },
    stepper: { flexDirection: "row", alignItems: "center", gap: 6 },
    searchRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
    chips: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    input: { flex: 1, minHeight: 44, color: colors.text, fontSize: 16, paddingHorizontal: 12, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface },
    tzInput: { flex: 0, minWidth: 180, textAlign: "right" },
    invalid: { borderColor: colors.danger },
  });
}
