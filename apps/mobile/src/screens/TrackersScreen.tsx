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

  const [chart, setChart] = useState<string>("FINAL_ACTION");
  const [boardCountry, setBoardCountry] = useState("INDIA");
  const renderCutoff = (e: Entry | undefined) => {
    if (!e) return <Text style={styles.rowMeta}>—</Text>;
    const arrow =
      e.movement === "FORWARD" ? <Text style={styles.up}> ▲</Text> : e.movement === "BACKWARD" ? <Text style={styles.down}> ▼</Text> : null;
    if (e.cutoff === "C") return <Text style={[styles.pill, styles.pillOk]}>Current{arrow}</Text>;
    if (e.cutoff === "U") return <Text style={[styles.pill, styles.pillBad]}>Unavailable{arrow}</Text>;
    return <Text style={styles.dateText}>{cutoffLong(e.cutoff)}{arrow}</Text>;
  };
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

  const chip = (label: string, selected: boolean, onPress: () => void, a11y?: string) => (
    <Pressable
      key={label}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={a11y ?? label}
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
      {bulletin ? (
        <>
          <Text style={styles.rowLabel}>{`${monthName(bulletin.month)} Visa Bulletin`}</Text>
          <View style={styles.chipRow}>
            {CHARTS.map((c) => chip(c.label, chart === c.key, () => setChart(c.key)))}
          </View>
          <Text style={styles.hint}>{CHARTS.find((c) => c.key === chart)?.help}</Text>
          <View style={styles.chipRow}>
            {[["ALL_COLUMNS", "All countries"], ...BOARD_COUNTRIES].map(([key, name]) =>
              chip(name as string, boardCountry === key, () => setBoardCountry(key as string), `Show ${name}`),
            )}
          </View>
          {BOARD_GROUPS.map((group) => (
            <View key={group.title} style={styles.group} accessibilityRole="summary" accessibilityLabel={group.title}>
              <Text style={styles.groupHead}>{group.title.toUpperCase()}</Text>
              <ScrollView horizontal={boardCountry === "ALL_COLUMNS"} showsHorizontalScrollIndicator={false}>
                <View style={boardCountry === "ALL_COLUMNS" ? styles.wideTable : styles.fullWidth}>
                  {boardCountry === "ALL_COLUMNS" ? (
                    <View style={styles.boardRow}>
                      <View style={styles.boardLabel} />
                      {BOARD_COUNTRIES.map(([key, name]) => (
                        <Text key={key} style={[styles.tableHead, styles.boardCol]}>{name}</Text>
                      ))}
                    </View>
                  ) : null}
                  {group.rows.map(([code, name]) => (
                    <View key={code} style={[styles.boardRow, styles.divider]}>
                      <View style={styles.boardLabel}>
                        <Text style={styles.rowLabel}>{code}</Text>
                        <Text style={styles.rowMeta}>{name}</Text>
                      </View>
                      {(boardCountry === "ALL_COLUMNS" ? BOARD_COUNTRIES : BOARD_COUNTRIES.filter(([k]) => k === boardCountry)).map(([key]) => (
                        <View key={key} style={boardCountry === "ALL_COLUMNS" ? styles.boardCol : styles.boardSingle}>
                          {renderCutoff(bulletin.entries.find((e) => e.chart === chart && e.category === code && e.country === key))}
                        </View>
                      ))}
                    </View>
                  ))}
                </View>
              </ScrollView>
            </View>
          ))}
          <Text style={styles.rowMeta}>▲ moved forward · ▼ moved back since last month.</Text>
        </>
      ) : null}
      {visa.length === 0 ? (
        <Text style={styles.hint}>Follow a category below to track it and get alerts.</Text>
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

const CHARTS = [
  { key: "FINAL_ACTION", label: "Final action dates", help: "A green card can be issued only if your priority date is earlier than the date shown." },
  { key: "DATES_FOR_FILING", label: "Dates for filing", help: "You may start filing once your priority date is earlier than the date shown. USCIS says each month which chart applies." },
];
const BOARD_COUNTRIES: [string, string][] = [["INDIA", "India"], ["CHINA", "China"], ["MEXICO", "Mexico"], ["PHILIPPINES", "Philippines"], ["ALL", "Rest of world"]];
const BOARD_GROUPS: { title: string; rows: [string, string][] }[] = [
  {
    title: "Employment-based",
    rows: [["EB1", "Priority workers"], ["EB2", "Advanced degree or exceptional ability"], ["EB3", "Skilled workers and professionals"], ["EB3-OW", "Other workers"], ["EB4", "Special immigrants"], ["EB5", "Investors (unreserved)"]],
  },
  {
    title: "Family-sponsored",
    rows: [["F1", "Unmarried sons and daughters of U.S. citizens"], ["F2A", "Spouses and children of permanent residents"], ["F2B", "Unmarried adult children of permanent residents"], ["F3", "Married sons and daughters of U.S. citizens"], ["F4", "Siblings of U.S. citizens"]],
  },
];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

// "2023-07-01" -> "Jul 1, 2023"; "2026-10" -> "October 2026".
function cutoffLong(value: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return m ? `${MONTHS[Number(m[2]) - 1] ?? m[2]} ${Number(m[3])}, ${m[1]}` : value;
}
function monthName(value: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(value);
  return m ? `${MONTHS_LONG[Number(m[2]) - 1] ?? m[2]} ${m[1]}` : value;
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
    chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    groupHead: { ...typography.meta, color: ui.textSecondary, fontWeight: "700", letterSpacing: 0.5, paddingHorizontal: 12, paddingTop: 10, paddingBottom: 4 },
    wideTable: { minWidth: 640 },
    fullWidth: { alignSelf: "stretch" },
    boardRow: { flexDirection: "row", alignItems: "center", paddingVertical: 10, paddingHorizontal: 12, gap: 8 },
    boardLabel: { width: 150, flexShrink: 1, flexGrow: 1 },
    boardCol: { width: 92, alignItems: "flex-start" },
    boardSingle: { alignItems: "flex-end" },
    tableHead: { ...typography.meta, color: ui.textSecondary, fontWeight: "600" },
    dateText: { ...typography.body, color: colors.text, fontWeight: "600" },
    pill: { ...typography.meta, fontWeight: "700", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999, overflow: "hidden" },
    pillOk: { backgroundColor: ui.successSoft, color: ui.success },
    pillBad: { backgroundColor: ui.dangerSoft, color: ui.danger },
    up: { color: ui.success, fontWeight: "700" },
    down: { color: ui.danger, fontWeight: "700" },
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
