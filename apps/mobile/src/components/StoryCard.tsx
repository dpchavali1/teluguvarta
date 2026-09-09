import React, { useEffect, useState } from "react";
import { Alert, AccessibilityInfo, Pressable, StyleSheet, Text, View } from "react-native";

import { trackEvent, type Language, type StoryOut } from "../lib/api";
import { shareStory } from "../lib/share";
import { isSaved, toggleSaved } from "../lib/storage";

const STATUS_LABEL: Record<string, string | undefined> = {
  RETRACTED: "Retracted",
  UPDATED: "Updated / corrected",
  CORRECTION_PENDING: "Correction pending",
};

// Mirrors apps/web/src/components/StoryCard.tsx's fields/behavior exactly
// (T15 acceptance criterion): labels, retracted/updated notice, headline +
// summary + why-matters, a prominent source link, an EN/Telugu toggle when a
// QA-passed `te` variant exists, native share, and save.
export function StoryCard({
  story,
  onOpen,
  onOpenSource,
}: {
  story: StoryOut;
  onOpen: () => void;
  onOpenSource: (url: string) => void;
}) {
  const [language, setLanguage] = useState<Language>("en");
  const [saved, setSaved] = useState(false);
  const hasTelugu = Boolean(story.variants.te);

  useEffect(() => {
    let cancelled = false;
    isSaved(story.id).then((value) => {
      if (!cancelled) setSaved(value);
    });
    return () => {
      cancelled = true;
    };
  }, [story.id]);

  const variant = story.variants[language] ?? story.variants.en;
  if (!variant) return null;

  const statusNotice = STATUS_LABEL[story.status];
  const primarySource = story.sources[0];

  async function handleShare() {
    trackEvent("story_share", { story_id: story.id });
    await shareStory(story.canonical_slug, variant!);
  }

  async function handleSaveToggle() {
    const next = await toggleSaved(story.id);
    setSaved(next);
    if (next) trackEvent("story_save", { story_id: story.id });
    AccessibilityInfo.announceForAccessibility(next ? "Saved" : "Removed from saved");
  }

  function handleLanguageSwitch(next: Language) {
    if (next !== language) trackEvent("language_switch", { story_id: story.id, language: next });
    setLanguage(next);
  }

  function handleReportIssue() {
    Alert.alert("Report an issue", "Let us know this story has a problem?", [
      { text: "Cancel", style: "cancel" },
      { text: "Report", onPress: () => trackEvent("report_issue", { story_id: story.id }) },
    ]);
  }

  return (
    <View style={styles.card} accessible={false}>
      <View style={styles.labels}>
        {[...story.countries, ...story.topics].map((label) => (
          <View key={label} style={styles.pill}>
            <Text style={styles.pillText}>{label}</Text>
          </View>
        ))}
      </View>

      {statusNotice && (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          {statusNotice}
        </Text>
      )}

      <Pressable
        onPress={onOpen}
        accessibilityRole="link"
        accessibilityLabel={`Open story: ${variant.headline}`}
        style={styles.touchTarget}
      >
        <Text style={styles.headline}>{variant.headline}</Text>
      </Pressable>

      <Text style={styles.body}>{variant.summary}</Text>
      {variant.why_matters ? (
        <Text style={styles.why}>Why this matters: {variant.why_matters}</Text>
      ) : null}

      {primarySource && (
        <Pressable
          onPress={() => onOpenSource(primarySource.url)}
          accessibilityRole="link"
          accessibilityLabel={`Read the original source${primarySource.title ? `: ${primarySource.title}` : ""}`}
          style={styles.touchTarget}
        >
          <Text style={styles.sourceLink}>
            Read the original source{primarySource.title ? `: ${primarySource.title}` : ""} ↗
          </Text>
        </Pressable>
      )}

      <View style={styles.actions}>
        {hasTelugu && (
          <View accessibilityRole="radiogroup" accessibilityLabel="Language" style={styles.langGroup}>
            <Pressable
              onPress={() => handleLanguageSwitch("en")}
              accessibilityRole="radio"
              accessibilityState={{ selected: language === "en" }}
              accessibilityLabel="English"
              style={[styles.langButton, language === "en" && styles.langButtonActive]}
            >
              <Text>English</Text>
            </Pressable>
            <Pressable
              onPress={() => handleLanguageSwitch("te")}
              accessibilityRole="radio"
              accessibilityState={{ selected: language === "te" }}
              accessibilityLabel="Telugu"
              style={[styles.langButton, language === "te" && styles.langButtonActive]}
            >
              <Text>తెలుగు</Text>
            </Pressable>
          </View>
        )}
        <Pressable
          onPress={handleShare}
          accessibilityRole="button"
          accessibilityLabel={`Share: ${variant.headline}`}
          style={styles.actionButton}
        >
          <Text>Share</Text>
        </Pressable>
        <Pressable
          onPress={handleSaveToggle}
          accessibilityRole="button"
          accessibilityState={{ selected: saved }}
          accessibilityLabel={saved ? `Unsave: ${variant.headline}` : `Save: ${variant.headline}`}
          style={styles.actionButton}
        >
          <Text>{saved ? "Saved" : "Save"}</Text>
        </Pressable>
        <Pressable
          onPress={handleReportIssue}
          accessibilityRole="button"
          accessibilityLabel={`Report an issue: ${variant.headline}`}
          style={styles.actionButton}
        >
          <Text>Report an issue</Text>
        </Pressable>
      </View>
    </View>
  );
}

// §9.2 accessibility: every interactive element has a >=44pt touch target.
const styles = StyleSheet.create({
  card: { padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: "#ddd", gap: 8 },
  labels: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  pill: { backgroundColor: "#eee", borderRadius: 12, paddingHorizontal: 8, paddingVertical: 2 },
  pillText: { fontSize: 12 },
  notice: { color: "#b00", fontWeight: "600" },
  touchTarget: { minHeight: 44, justifyContent: "center" },
  headline: { fontSize: 18, fontWeight: "700" },
  body: { fontSize: 15 },
  why: { fontSize: 14, fontStyle: "italic", color: "#444" },
  sourceLink: { color: "#0645ad" },
  actions: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8, marginTop: 4 },
  langGroup: { flexDirection: "row", gap: 4 },
  langButton: {
    minHeight: 44,
    minWidth: 44,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#ccc",
  },
  langButtonActive: { backgroundColor: "#e6efff", borderColor: "#0645ad" },
  actionButton: {
    minHeight: 44,
    minWidth: 44,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#ccc",
  },
});
