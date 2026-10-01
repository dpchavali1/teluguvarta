import { STUDENT_TOPIC_SLUGS } from "@teluguvarta/domain";
import React, { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { getConfig, type TopicOut } from "../lib/api";
import { LIFE_STAGES, type OnboardingProfile } from "../lib/storage";
import { typography } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

// The profile questions, shared by onboarding (one per step) and Settings →
// "Your profile" (all on one page). Each section edits a draft profile and
// hands back the whole next draft; persisting is the caller's job.

type SectionProps = {
  profile: OnboardingProfile;
  onChange: (next: OnboardingProfile) => void;
};

const isStudentTopic = (slug: string) =>
  STUDENT_TOPIC_SLUGS.includes(slug as (typeof STUDENT_TOPIC_SLUGS)[number]);

// Topics come from /v1/config; on failure the interests section is just empty.
export function useConfigTopics(): TopicOut[] {
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
  return topics;
}

export function useProfileFieldStyles() {
  const { colors, ui } = useAppTheme();
  return useMemo(() => createStyles(colors, ui), [colors, ui]);
}

export function LocationFields({ profile, onChange }: SectionProps) {
  const styles = useProfileFieldStyles();
  const { ui } = useAppTheme();
  return (
    <>
      <TextInput
        value={profile.residenceCountry ?? ""}
        onChangeText={(v) => onChange({ ...profile, residenceCountry: v })}
        placeholder="Country"
        placeholderTextColor={ui.textTertiary}
        accessibilityLabel="Country of residence"
        style={styles.input}
      />
      <TextInput
        value={profile.homeRegion ?? ""}
        onChangeText={(v) => onChange({ ...profile, homeRegion: v })}
        placeholder="State / region"
        placeholderTextColor={ui.textTertiary}
        accessibilityLabel="Home state or region"
        style={styles.input}
      />
      <TextInput
        value={profile.homeCity ?? ""}
        onChangeText={(v) => onChange({ ...profile, homeCity: v })}
        placeholder="City"
        placeholderTextColor={ui.textTertiary}
        accessibilityLabel="Home city"
        style={styles.input}
      />
    </>
  );
}

export function LifeStageFields({ profile, onChange }: SectionProps) {
  const styles = useProfileFieldStyles();
  return (
    <>
      <Text style={styles.hint}>Select every option that applies — you're not just one thing.</Text>
      {LIFE_STAGES.map((option) => {
        const selected = profile.lifeStages.includes(option.value);
        return (
          <Pressable
            key={option.value}
            onPress={() =>
              onChange({
                ...profile,
                lifeStages: selected
                  ? profile.lifeStages.filter((s) => s !== option.value)
                  : [...profile.lifeStages, option.value],
              })
            }
            accessibilityRole="checkbox"
            accessibilityState={{ checked: selected }}
            accessibilityLabel={option.label}
            style={[styles.optionRow, selected && styles.optionRowActive]}
          >
            <Text style={styles.optionLabel}>{option.label}</Text>
          </Pressable>
        );
      })}
    </>
  );
}

export function StudentFields({ profile, onChange }: SectionProps) {
  const styles = useProfileFieldStyles();
  const { ui } = useAppTheme();
  const field = (key: "studyCountry" | "studyRegion" | "studyMetro" | "degreeLevel", placeholder: string, label: string) => (
    <TextInput
      value={profile.student?.[key] ?? ""}
      onChangeText={(v) => onChange({ ...profile, student: { ...profile.student, [key]: v } })}
      placeholder={placeholder}
      placeholderTextColor={ui.textTertiary}
      accessibilityLabel={label}
      style={styles.input}
    />
  );
  return (
    <>
      <Text style={styles.hint}>We never ask for your university name or immigration documents.</Text>
      {field("studyCountry", "Country of study", "Country of study")}
      {field("studyRegion", "State / region of study", "State or region of study")}
      {field("studyMetro", "Nearest city / metro", "Nearest city or metro area")}
      {field("degreeLevel", "Degree level (e.g. Master's)", "Degree level")}
    </>
  );
}

export function InterestFields({ profile, onChange, topics }: SectionProps & { topics: TopicOut[] }) {
  const styles = useProfileFieldStyles();
  const toggle = (slug: string, selected: boolean) =>
    onChange({
      ...profile,
      interestTopicSlugs: selected
        ? profile.interestTopicSlugs.filter((s) => s !== slug)
        : [...profile.interestTopicSlugs, slug],
    });
  const studentTopics = topics.filter((t) => isStudentTopic(t.slug));
  return (
    <>
      <TopicChips
        topics={topics.filter((t) => !isStudentTopic(t.slug))}
        selectedSlugs={profile.interestTopicSlugs}
        onToggle={toggle}
        styles={styles}
      />
      {/* S2: student topics (F-1, OPT, campus safety, etc.) are the same kind
          of Topic row as the general ones above, shown as a separate group per
          §3.1 rather than mixed in — selecting or clearing this group never
          touches interestTopicSlugs entries from the general group. */}
      {studentTopics.length > 0 && (
        <>
          <Text style={styles.hint}>Student topics</Text>
          <TopicChips topics={studentTopics} selectedSlugs={profile.interestTopicSlugs} onToggle={toggle} styles={styles} />
        </>
      )}
    </>
  );
}

function TopicChips({
  topics,
  selectedSlugs,
  onToggle,
  styles,
}: {
  topics: TopicOut[];
  selectedSlugs: string[];
  onToggle: (slug: string, wasSelected: boolean) => void;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <View style={styles.chipWrap}>
      {topics.map((topic) => {
        const selected = selectedSlugs.includes(topic.slug);
        return (
          <Pressable
            key={topic.slug}
            onPress={() => onToggle(topic.slug, selected)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: selected }}
            accessibilityLabel={topic.name}
            style={[styles.chip, selected && styles.chipActive]}
          >
            <Text style={styles.chipText}>{topic.name}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    hint: { ...typography.meta, textTransform: "none", color: ui.textTertiary },
    input: {
      minHeight: 44,
      paddingHorizontal: 12,
      borderRadius: 8,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
      color: colors.text,
    },
    optionRow: {
      minHeight: 44,
      justifyContent: "center",
      paddingHorizontal: 12,
      borderRadius: 8,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
    },
    optionRowActive: { backgroundColor: ui.actionPrimarySoft, borderColor: ui.actionPrimary },
    optionLabel: { ...typography.body, color: colors.text },
    chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    chip: {
      minHeight: 44,
      justifyContent: "center",
      paddingHorizontal: 14,
      borderRadius: 16,
      borderCurve: "continuous",
      borderWidth: 1,
      borderColor: ui.borderControl,
    },
    chipActive: { backgroundColor: ui.actionPrimarySoft, borderColor: ui.actionPrimary },
    chipText: { ...typography.body, color: colors.text },
  });
}
