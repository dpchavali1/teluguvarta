import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AccessibilityInfo, Linking, Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";

import { getLatestVisaBulletin, listExamDeadlines, type ExamDeadlineOut, type VisaBulletinOut } from "../lib/api";
import { syncSavedStories } from "../lib/notificationSync";
import {
  getFollowedExams,
  getFollowedVisa,
  saveFollowedExams,
  saveFollowedVisa,
} from "../lib/storage";
import {
  cutoffLabel,
  MAX_EXAM_FOLLOWS,
  MAX_VISA_FOLLOWS,
  VISA_CATEGORIES,
  VISA_COUNTRIES,
  visaLabel,
  type FollowedExam,
  type FollowedVisa,
} from "../lib/trackers";
import { radius, spacing, typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

const MOVEMENT: Record<string, string> = { FORWARD: "moved forward", BACKWARD: "moved back", SAME: "no change", NEW: "new" };

type Entry = VisaBulletinOut["entries"][number];

// P07/ADR-041: approved, editor-entered visa bulletin cutoffs and exam dates.
// Follows stay on this device; only keys and the alert switch sync.
export function TrackersScreen() {
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const [visa, setVisa] = useState<FollowedVisa[]>([]);
  const [exams, setExams] = useState<FollowedExam[]>([]);
  const [bulletin, setBulletin] = useState<VisaBulletinOut | null>(null);
  const [deadlines, setDeadlines] = useState<ExamDeadlineOut[]>([]);
  const [category, setCategory] = useState<string>(VISA_CATEGORIES[0]);
  const [country, setCountry] = useState<string>("ALL");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    getFollowedVisa().then(setVisa).catch(() => {});
    getFollowedExams().then(setExams).catch(() => {});
    getLatestVisaBulletin().then(setBulletin).catch(() => {}); // 404 until a month is approved
    listExamDeadlines().then(setDeadlines).catch(() => {}).finally(() => setLoaded(true));
  }, []);

  const persistVisa = useCallback(async (next: FollowedVisa[]) => {
    setVisa(await saveFollowedVisa(next));
    syncSavedStories();
  }, []);
  const persistExams = useCallback(async (next: FollowedExam[]) => {
    setExams(await saveFollowedExams(next));
    syncSavedStories();
  }, []);

  const entryFor = (v: FollowedVisa): Entry | undefined =>
    bulletin?.entries.find((e) => e.category === v.category && e.country === v.country && e.chart === "FINAL_ACTION");

  const visaFull = visa.length >= MAX_VISA_FOLLOWS;
  const alreadyVisa = visa.some((v) => v.category === category && v.country === country);
  const examKeys = useMemo(() => [...new Set(deadlines.map((d) => d.exam))].sort(), [deadlines]);
  const examFull = exams.length >= MAX_EXAM_FOLLOWS;

  function followVisa() {
    if (visaFull || alreadyVisa) return;
    persistVisa([...visa, { category, country, alerts: false }]);
    AccessibilityInfo.announceForAccessibility(`Following ${visaLabel({ category, country })}.`);
  }

  function toggleExam(exam: string) {
    const on = exams.some((e) => e.exam === exam);
    if (!on && examFull) return;
    persistExams(on ? exams.filter((e) => e.exam !== exam) : [...exams, { exam, alerts: false }]);
  }

  const chip = (label: string, selected: boolean, onPress: () => void) => (
    <Pressable
      key={label}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected }}
      style={[styles.chip, selected && styles.chipOn]}
    >
      <Text style={styles.buttonText}>{label}</Text>
    </Pressable>
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.intro}>
        Dates come from official notices, entered and approved by our editors. Always confirm on the official source.
      </Text>

      <Text style={styles.groupLabel} accessibilityRole="header">{`VISA BULLETIN${bulletin ? ` · ${bulletin.month}` : ""}`}</Text>
      {visa.length === 0 ? (
        <Text style={styles.hint}>You don't follow any visa categories yet.</Text>
      ) : (
        <View style={styles.group}>
          {visa.map((v, i) => {
            const entry = entryFor(v);
            const label = visaLabel(v);
            return (
              <View key={`${v.category}-${v.country}`} style={[styles.row, i < visa.length - 1 && styles.divider]}>
                <View style={styles.grow}>
                  <Text style={styles.rowLabel}>{label}</Text>
                  <Text style={styles.rowMeta}>
                    {entry
                      ? `Final action: ${cutoffLabel(entry.cutoff)} (${MOVEMENT[entry.movement] ?? entry.movement})`
                      : "No approved bulletin yet"}
                  </Text>
                </View>
                <View style={styles.alertGroup}>
                  <Text style={styles.rowMeta}>Alerts</Text>
                  <Switch
                    value={v.alerts}
                    onValueChange={(alerts) => persistVisa(visa.map((x) => (x === v ? { ...x, alerts } : x)))}
                    accessibilityLabel={`Alerts for ${label}`}
                  />
                </View>
                <Pressable
                  onPress={() => persistVisa(visa.filter((x) => x !== v))}
                  accessibilityRole="button"
                  accessibilityLabel={`Stop following ${label}`}
                  style={styles.button}
                >
                  <Text style={styles.buttonText}>Remove</Text>
                </Pressable>
              </View>
            );
          })}
        </View>
      )}
      {visaFull ? <Text style={styles.hint}>You're following the maximum of {MAX_VISA_FOLLOWS}.</Text> : null}
      <Text style={styles.rowMeta}>Category</Text>
      <View style={styles.chips}>{VISA_CATEGORIES.map((c) => chip(c, c === category, () => setCategory(c)))}</View>
      <Text style={styles.rowMeta}>Country of chargeability</Text>
      <View style={styles.chips}>{VISA_COUNTRIES.map((c) => chip(c === "ALL" ? "All" : c[0] + c.slice(1).toLowerCase(), c === country, () => setCountry(c)))}</View>
      <Pressable
        onPress={followVisa}
        disabled={visaFull || alreadyVisa}
        accessibilityRole="button"
        accessibilityLabel={`Follow ${visaLabel({ category, country })}`}
        accessibilityState={{ disabled: visaFull || alreadyVisa }}
        style={[styles.button, (visaFull || alreadyVisa) && styles.disabled]}
      >
        <Text style={styles.buttonText}>{alreadyVisa ? "Already following" : "Follow"}</Text>
      </Pressable>

      <Text style={styles.groupLabel} accessibilityRole="header">{`EXAM DATES (${exams.length}/${MAX_EXAM_FOLLOWS} followed)`}</Text>
      {loaded && deadlines.length === 0 ? <Text style={styles.hint}>No upcoming dates are listed yet.</Text> : null}
      {examKeys.map((exam) => {
        const follow = exams.find((e) => e.exam === exam);
        return (
          <View key={exam} style={styles.group}>
            <View style={styles.row}>
              <Text style={[styles.rowLabel, styles.grow]} accessibilityRole="header">{exam}</Text>
              {follow ? (
                <View style={styles.alertGroup}>
                  <Text style={styles.rowMeta}>Alerts</Text>
                  <Switch
                    value={follow.alerts}
                    onValueChange={(alerts) => persistExams(exams.map((e) => (e.exam === exam ? { ...e, alerts } : e)))}
                    accessibilityLabel={`Alerts for ${exam}`}
                  />
                </View>
              ) : null}
              <Pressable
                onPress={() => toggleExam(exam)}
                disabled={!follow && examFull}
                accessibilityRole="button"
                accessibilityLabel={follow ? `Stop following ${exam}` : `Follow ${exam}`}
                style={[styles.button, !follow && examFull && styles.disabled]}
              >
                <Text style={styles.buttonText}>{follow ? "Remove" : "Follow"}</Text>
              </Pressable>
            </View>
            {deadlines.filter((d) => d.exam === exam).map((d) => (
              <Pressable
                key={d.id}
                onPress={() => Linking.openURL(d.source_url).catch(() => {})}
                accessibilityRole="link"
                accessibilityLabel={`${d.title}, ${d.deadline}. Opens the official source`}
                style={[styles.row, styles.divider]}
              >
                <Text style={[styles.rowLabel, styles.grow]}>{d.title}</Text>
                <Text style={styles.rowMeta}>{d.deadline}</Text>
              </Pressable>
            ))}
          </View>
        );
      })}
    </ScrollView>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.bg },
    content: { padding: spacing.md, gap: spacing.md, paddingBottom: spacing.xl },
    intro: { ...typography.body, color: ui.textSecondary },
    hint: { ...typography.body, color: ui.textSecondary },
    groupLabel: { ...typography.meta, color: ui.textSecondary, fontWeight: "700" },
    group: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderSubtle,
      overflow: "hidden",
    },
    row: { minHeight: 56, flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.xs },
    divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderColor: ui.borderSubtle },
    grow: { flex: 1 },
    rowLabel: { ...typography.body, color: colors.text, flexShrink: 1 },
    rowMeta: { ...typography.meta, color: ui.textSecondary },
    alertGroup: { alignItems: "center" },
    chips: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
    chip: {
      minHeight: 44,
      justifyContent: "center",
      paddingHorizontal: spacing.md,
      borderRadius: radius.md,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
    },
    chipOn: { backgroundColor: colors.surface, borderColor: colors.text, borderWidth: 2 },
    button: {
      minHeight: 44,
      justifyContent: "center",
      paddingHorizontal: spacing.md,
      borderRadius: radius.md,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
    },
    disabled: { opacity: 0.4 },
    buttonText: { color: colors.text, fontWeight: "600" },
  });
}
