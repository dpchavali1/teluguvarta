import { topicLabel } from "@teluguvarta/domain";
import React, { useEffect, useState } from "react";
import { Alert, AccessibilityInfo, DeviceEventEmitter, Pressable, StyleSheet, Text, View } from "react-native";

import { reportIssue, trackEvent, type Language, type StoryOut } from "../lib/api";
import { shareStory } from "../lib/share";
import { getProfile, setLanguage as persistLanguage, LANGUAGE_CHANGE_EVENT } from "../lib/storage";
import { useStoryCache } from "../lib/StoryCacheContext";
import { colors, radius, spacing, typography, typographyFor, typographyTe, ui } from "../theme/tokens";

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
  layout = "compact",
}: {
  story: StoryOut;
  // Optional: the detail screen renders this card for a story already
  // open, so the headline shouldn't be a dead tap target pointing nowhere.
  onOpen?: () => void;
  onOpenSource: (url: string) => void;
  // "hero": the lead story on Home — bigger display-scale headline, no box
  // chrome, a rule line instead of a border. "compact": every other list
  // row (Search/Saved/Topic/StoryList, and the default for back-compat) —
  // same content, a slim accent bar instead of a full card border.
  layout?: "hero" | "compact";
}) {
  const isHero = layout === "hero";
  const cache = useStoryCache();
  const [language, setLanguage] = useState<Language>("en");
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
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
    // Design-review fix: a card already on screen only picked up a language
    // change made elsewhere (the header toggle, Settings) on its next
    // mount. Mirrors apps/web's StoryCard listening for LANGUAGE_CHANGE_EVENT.
    const subscription = DeviceEventEmitter.addListener(LANGUAGE_CHANGE_EVENT, (next: Language) => {
      if (!cancelled) setLanguage(next);
    });
    return () => {
      cancelled = true;
      subscription.remove();
    };
  }, []);

  const variant = story.variants[language] ?? story.variants.en;
  if (!variant) return null;

  // The rendered language, not the requested one — `variant` falls back to
  // `en` when the requested variant is missing, and the type metrics have to
  // follow the glyphs actually on screen.
  const renderedLanguage: Language = story.variants[language] ? language : "en";
  const type = typographyFor(renderedLanguage);
  const whyMatters = renderedLanguage === "en" ? story.personalization?.why_matters ?? variant.why_matters : variant.why_matters;

  const statusNotice = STATUS_LABEL[story.status];
  const primarySource = story.sources[0];

  async function handleShare() {
    trackEvent("story_share", { story_id: story.id });
    await shareStory(story.canonical_slug, variant!);
  }

  async function handleSaveToggle() {
    if (saving) return;
    setSaving(true);
    try {
      const next = await cache.toggleSaved(story.id);
      if (next) trackEvent("story_save", { story_id: story.id });
      setActionStatus(next ? "Saved" : "Removed from saved");
      AccessibilityInfo.announceForAccessibility(next ? "Saved" : "Removed from saved");
    } catch { setActionStatus("Couldn't save this change on your device. Please try again."); }
    finally { setSaving(false); }
  }

  function handleLanguageSwitch(next: Language) {
    if (next !== language) trackEvent("language_switch", { story_id: story.id, language: next });
    setLanguage(next);
    persistLanguage(next);
  }

  function handleReportIssue() {
    Alert.alert("Report an issue", "Let us know this story has a problem?", [
      { text: "Cancel", style: "cancel" },
      { text: "Report", onPress: async () => {
        try { await reportIssue(story.id); setActionStatus("Report received. Thank you."); }
        catch { setActionStatus("Couldn’t send your report. Tap Report to try again."); }
      } },
    ]);
  }

  return (
    <View style={[styles.card, isHero ? styles.cardHero : styles.cardCompact]} accessible={false}>
      {!isHero && <View style={styles.accentBar} />}
      <View style={isHero ? styles.heroContent : styles.compactContent}>
        <View style={styles.labels}>
          {[...story.countries, ...story.topics.map(topicLabel)].map((label) => (
            <View key={label} style={styles.pill}>
              <Text style={styles.pillText}>{label}</Text>
            </View>
          ))}
        </View>

        {story.published_at && <Text style={styles.date}>{new Date(story.published_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</Text>}
        {language !== renderedLanguage && <Text>Telugu translation isn’t available yet. Showing English.</Text>}
        {story.personalization?.explanation && <Text style={styles.date}>{story.personalization.explanation}</Text>}
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
            <Text style={[styles.headline, isHero ? type.display : type.headline]}>{variant.headline}</Text>
          </Pressable>
        ) : (
          <Text style={[styles.headline, isHero ? type.display : type.headline]} accessibilityRole="header">
            {variant.headline}
          </Text>
        )}

        <Text style={[styles.body, type.body]}>{variant.summary}</Text>
        {whyMatters ? (
          <Text style={[styles.why, isHero && styles.whyHero, renderedLanguage === "te" && styles.whyTe]}>
            Why this matters: {whyMatters}
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

        {actionStatus && <Text accessibilityLiveRegion="polite">{actionStatus}</Text>}
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
            style={[styles.actionButton, styles.actionButtonShare]}
          >
            <Text style={styles.actionButtonText}>⤴ Share</Text>
          </Pressable>
          <Pressable
            onPress={handleSaveToggle}
            disabled={saving}
            accessibilityRole="button"
            accessibilityState={{ selected: saved }}
            accessibilityLabel={saved ? `Unsave: ${variant.headline}` : `Save: ${variant.headline}`}
            style={[styles.actionButton, saved && styles.actionButtonSaved]}
          >
            <Text style={[styles.actionButtonText, saved && styles.actionButtonTextActive]}>
              {saved ? "🔖 Saved" : "🔖 Save"}
            </Text>
          </Pressable>
          <Pressable
            onPress={handleReportIssue}
            accessibilityRole="button"
            accessibilityLabel={`Report an issue: ${variant.headline}`}
            style={[styles.actionButton, styles.actionButtonReport]}
          >
            <Text style={styles.actionButtonText}>⚑ Report</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

// §9.2 accessibility: every interactive element has a >=44pt touch target.
const styles = StyleSheet.create({
  card: { backgroundColor: colors.surface },
  // Hero: the lead story — no box chrome, a rule line below instead of a
  // border, more breathing room. Reads as a lead newspaper story, not a
  // bordered card.
  cardHero: {
    margin: spacing.md,
    marginBottom: spacing.md,
    paddingBottom: spacing.lg,
    borderBottomWidth: 2,
    borderBottomColor: colors.rule,
  },
  heroContent: { gap: spacing.sm },
  // Compact: every other list row — a slim accent bar instead of a full
  // border/shadow card, tighter padding, a hairline divider below.
  cardCompact: {
    flexDirection: "row",
    marginHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: ui.borderSubtle,
    gap: spacing.sm,
  },
  accentBar: { width: 3, borderRadius: 2, borderCurve: "continuous", backgroundColor: colors.hot, alignSelf: "stretch" },
  compactContent: { flex: 1, gap: spacing.xs },
  date: { ...typography.meta, color: colors.muted, textTransform: "none" },
  labels: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  // Matches web's plain .pill: a neutral outlined tag, not a colored fill —
  // Folio has one accent color and one danger color, no third family.
  pill: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: ui.borderControl,
    borderRadius: radius.sm,
    borderCurve: "continuous",
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  pillText: { ...typography.meta, color: colors.faint, textTransform: "uppercase" },
  notice: { color: ui.danger, fontWeight: "600" },
  // Matches web's .story-card__reviewed: ink outline, transparent fill.
  reviewedBadge: {
    alignSelf: "flex-start",
    borderWidth: 1,
    borderColor: colors.rule,
    borderRadius: radius.sm,
    borderCurve: "continuous",
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  reviewedBadgeText: { ...typography.meta, color: colors.text, fontWeight: "700" },
  touchTarget: { minHeight: 44, justifyContent: "center" },
  headline: { ...typography.headline, color: colors.text },
  body: { ...typography.body, color: colors.muted },
  why: {
    ...typography.body,
    fontWeight: "600",
    color: ui.actionText,
    backgroundColor: ui.actionPrimarySoft,
    borderRadius: radius.sm,
    borderCurve: "continuous",
    borderLeftWidth: 3,
    // Raw `accent` on `accentSoft` is low contrast — the border would be
    // nearly invisible. Use ink instead (see design-review finding #4, same
    // defect as apps/web/src/app/globals.css:896).
    borderLeftColor: colors.rule,
    padding: spacing.sm,
  },
  // Telugu glyphs are taller than Latin at the same size; without explicit
  // leading this block sets solid and the vowel signs collide.
  whyTe: { lineHeight: typographyTe.body.lineHeight },
  // Hero pull-quote: wider, a thick rust rule instead of the compact card's
  // thin ink border — the same "why this matters" emphasis treatment web's
  // hero story gets in parallel.
  whyHero: {
    backgroundColor: "transparent",
    borderRadius: 0,
    borderLeftWidth: 4,
    borderLeftColor: colors.hot,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  sourceLink: { color: colors.text, fontWeight: "600", textDecorationLine: "underline" },
  actions: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: spacing.sm, marginTop: spacing.xs },
  langGroup: { flexDirection: "row", gap: spacing.xs },
  langButton: {
    minHeight: 44,
    minWidth: 44,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: spacing.sm,
    borderRadius: radius.pill,
    borderCurve: "continuous",
    borderWidth: 1,
    borderColor: ui.borderControl,
  },
  // Matches web's toggle "pressed" convention: accent fill, ink text.
  langButtonActive: { backgroundColor: ui.actionPrimarySoft, borderColor: ui.actionPrimary },
  langButtonText: { ...typography.meta, textTransform: "none", color: colors.muted },
  langButtonTextActive: { color: ui.actionText },
  actionButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    minHeight: 44,
    minWidth: 44,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderCurve: "continuous",
    borderWidth: 1,
    borderColor: ui.borderControl,
    backgroundColor: colors.surface,
  },
  actionButtonShare: { backgroundColor: colors.surface },
  actionButtonSaved: { backgroundColor: ui.successSoft, borderColor: ui.success },
  actionButtonReport: { borderColor: ui.borderSubtle },
  actionButtonText: { ...typography.meta, textTransform: "none", color: colors.muted },
  actionButtonTextActive: { color: ui.success },
});
