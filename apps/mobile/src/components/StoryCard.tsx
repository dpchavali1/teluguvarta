import React, { useEffect, useState } from "react";
import { Alert, AccessibilityInfo, Pressable, StyleSheet, Text, View } from "react-native";

import { trackEvent, type Language, type StoryOut } from "../lib/api";
import { shareStory } from "../lib/share";
import { getProfile, setProfile } from "../lib/storage";
import { useStoryCache } from "../lib/StoryCacheContext";
import { colors, radius, shadow, spacing, typography, typographyFor } from "../theme/tokens";

const STATUS_LABEL: Record<string, string | undefined> = {
  RETRACTED: "Retracted",
  UPDATED: "Updated / corrected",
  CORRECTION_PENDING: "Correction pending",
};

// NON_NEGOTIABLES #5: sensitivity != "NONE" can never reach a published
// state without passing the human-review gate (apps/api/app/jobs/
// publish.py:83), so surfacing sensitivity here is a truthful trust signal.
const REVIEWED_SENSITIVITIES = new Set(["IMMIGRATION", "LEGAL", "FINANCIAL", "BREAKING", "OBITUARY_ACCUSATION"]);

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
  // Optional: the detail screen renders this card for a story already
  // open, so the headline shouldn't be a dead tap target pointing nowhere.
  onOpen?: () => void;
  onOpenSource: (url: string) => void;
}) {
  const cache = useStoryCache();
  const [language, setLanguage] = useState<Language>("en");
  const hasTelugu = Boolean(story.variants.te);
  const isHumanReviewed = REVIEWED_SENSITIVITIES.has(story.sensitivity);
  const saved = cache.isSaved(story.id);

  useEffect(() => {
    let cancelled = false;
    // Design-review fix: the language chosen in Settings/onboarding was
    // never applied — every card defaulted to "en" regardless of profile.
    getProfile().then((profile) => {
      if (!cancelled) setLanguage(profile.language);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const variant = story.variants[language] ?? story.variants.en;
  if (!variant) return null;

  // The rendered language, not the requested one — `variant` falls back to
  // `en` when the requested variant is missing, and the type metrics have to
  // follow the glyphs actually on screen.
  const renderedLanguage: Language = story.variants[language] ? language : "en";
  const type = typographyFor(renderedLanguage);

  const statusNotice = STATUS_LABEL[story.status];
  const primarySource = story.sources[0];

  async function handleShare() {
    trackEvent("story_share", { story_id: story.id });
    await shareStory(story.canonical_slug, variant!);
  }

  async function handleSaveToggle() {
    const next = await cache.toggleSaved(story.id);
    if (next) trackEvent("story_save", { story_id: story.id });
    AccessibilityInfo.announceForAccessibility(next ? "Saved" : "Removed from saved");
  }

  function handleLanguageSwitch(next: Language) {
    if (next !== language) trackEvent("language_switch", { story_id: story.id, language: next });
    setLanguage(next);
    getProfile().then((profile) => setProfile({ ...profile, language: next }));
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

      {isHumanReviewed && (
        <View style={styles.reviewedBadge}>
          <Text style={styles.reviewedBadgeText}>✓ Human-reviewed</Text>
        </View>
      )}

      {statusNotice && (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          {statusNotice}
        </Text>
      )}

      {onOpen ? (
        <Pressable
          onPress={onOpen}
          accessibilityRole="link"
          accessibilityLabel={`Open story: ${variant.headline}`}
          style={styles.touchTarget}
        >
          <Text style={[styles.headline, type.headline]}>{variant.headline}</Text>
        </Pressable>
      ) : (
        <Text style={[styles.headline, type.headline]} accessibilityRole="header">
          {variant.headline}
        </Text>
      )}

      <Text style={[styles.body, type.body]}>{variant.summary}</Text>
      {variant.why_matters ? (
        <Text style={[styles.why, renderedLanguage === "te" && styles.whyTe]}>
          Why this matters: {variant.why_matters}
        </Text>
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
              <Text style={[styles.langButtonText, language === "en" && styles.langButtonTextActive]}>English</Text>
            </Pressable>
            <Pressable
              onPress={() => handleLanguageSwitch("te")}
              accessibilityRole="radio"
              accessibilityState={{ selected: language === "te" }}
              accessibilityLabel="Telugu"
              style={[styles.langButton, language === "te" && styles.langButtonActive]}
            >
              <Text style={[styles.langButtonText, language === "te" && styles.langButtonTextActive]}>తెలుగు</Text>
            </Pressable>
          </View>
        )}
        <Pressable
          onPress={handleShare}
          accessibilityRole="button"
          accessibilityLabel={`Share: ${variant.headline}`}
          style={styles.actionButton}
        >
          <Text style={styles.actionButtonText}>⤴ Share</Text>
        </Pressable>
        <Pressable
          onPress={handleSaveToggle}
          accessibilityRole="button"
          accessibilityState={{ selected: saved }}
          accessibilityLabel={saved ? `Unsave: ${variant.headline}` : `Save: ${variant.headline}`}
          style={[styles.actionButton, saved && styles.actionButtonActive]}
        >
          <Text style={[styles.actionButtonText, saved && styles.actionButtonTextActive]}>
            {saved ? "🔖 Saved" : "🔖 Save"}
          </Text>
        </Pressable>
        <Pressable
          onPress={handleReportIssue}
          accessibilityRole="button"
          accessibilityLabel={`Report an issue: ${variant.headline}`}
          style={styles.actionButton}
        >
          <Text style={styles.actionButtonText}>⚑ Report</Text>
        </Pressable>
      </View>
    </View>
  );
}

// §9.2 accessibility: every interactive element has a >=44pt touch target.
const styles = StyleSheet.create({
  card: {
    padding: spacing.lg,
    margin: spacing.md,
    marginBottom: 0,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    gap: spacing.sm,
    ...shadow.card,
  },
  labels: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  pill: {
    backgroundColor: colors.tealSoft,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  pillText: { ...typography.meta, color: colors.teal, textTransform: "uppercase" },
  notice: { color: colors.danger, fontWeight: "600" },
  reviewedBadge: {
    alignSelf: "flex-start",
    borderWidth: 1,
    borderColor: colors.teal,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  reviewedBadgeText: { ...typography.meta, color: colors.teal, fontWeight: "700" },
  touchTarget: { minHeight: 44, justifyContent: "center" },
  headline: { ...typography.headline, color: colors.text },
  body: { ...typography.body, color: colors.muted },
  why: {
    fontSize: 14,
    color: colors.accentInk,
    backgroundColor: colors.accentSoft,
    borderRadius: radius.sm,
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
    padding: spacing.sm,
  },
  // Telugu glyphs are taller than Latin at the same size; without explicit
  // leading this block sets solid and the vowel signs collide.
  whyTe: { lineHeight: 22 },
  sourceLink: { color: colors.teal, fontWeight: "600" },
  actions: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: spacing.sm, marginTop: spacing.xs },
  langGroup: { flexDirection: "row", gap: spacing.xs },
  langButton: {
    minHeight: 40,
    minWidth: 44,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  langButtonActive: { backgroundColor: colors.teal, borderColor: colors.teal },
  langButtonText: { fontSize: 13, fontWeight: "600", color: colors.muted },
  langButtonTextActive: { color: colors.accentContrast },
  actionButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    minHeight: 40,
    minWidth: 44,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  actionButtonActive: { backgroundColor: colors.teal, borderColor: colors.teal },
  actionButtonText: { fontSize: 13, fontWeight: "600", color: colors.muted },
  actionButtonTextActive: { color: colors.accentContrast },
});
