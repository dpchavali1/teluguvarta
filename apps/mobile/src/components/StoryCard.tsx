import { topicLabel } from "@teluguvarta/domain";
import React, { useEffect, useMemo, useState } from "react";
import { AccessibilityInfo, DeviceEventEmitter, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { REPORT_CATEGORIES, reportIssue, trackEvent, type Language, type ReportCategory, type StoryOut } from "../lib/api";
import { shareStory } from "../lib/share";
import { getProfile, setLanguage as persistLanguage, LANGUAGE_CHANGE_EVENT } from "../lib/storage";
import { useStoryCache } from "../lib/StoryCacheContext";
import { radius, spacing, typography, typographyFor, typographyTe } from "../theme/tokens";
import { useAppTheme, type AppTheme } from "../theme/useAppTheme";

const STATUS_LABEL: Record<string, string | undefined> = {
  RETRACTED: "Retracted",
  UPDATED: "Updated / corrected",
  CORRECTION_PENDING: "Correction pending",
};

// NON_NEGOTIABLES #5: sensitivity != "NONE" can never reach a published
// state without passing the human-review gate (apps/api/app/jobs/
// publish.py:83), so surfacing sensitivity here is a truthful trust signal.
const REVIEWED_SENSITIVITIES = new Set(["IMMIGRATION", "LEGAL", "FINANCIAL", "BREAKING", "OBITUARY_ACCUSATION"]);

// Not `new URL()`: React Native's URL doesn't implement `hostname`.
function sourceDomain(url: string): string {
  return url.replace(/^[a-z][a-z0-9+.-]*:\/\//i, "").split(/[/?#:]/)[0].replace(/^www\./i, "") || url;
}

// Mirrors apps/web/src/components/StoryCard.tsx's fields/behavior (T15
// acceptance criterion, refined by ADR-014's StoryLead/StoryBrief/
// StoryActions/LanguageControl contract): labels, retracted/updated
// notice, headline + summary + why-matters, a prominent source link, an
// EN/Telugu toggle only in the detail-view exception path, native share,
// and save.
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
  // ADR-014 StoryLead/StoryBrief/StoryActions: "hero" is the lead story on
  // Home — bigger display-scale headline, no box chrome, a rule line
  // instead of a border, full StoryActions (Share/Save/Report). "detail" is
  // the story-detail screen — same rich chrome as hero, full StoryActions,
  // plus the one place a per-story LanguageControl exception is allowed.
  // "compact" (StoryBrief) is every other list row (Search/Saved/Topic/
  // StoryList, and the default for back-compat) — action-light: Save only,
  // no per-card language toggle, per the ADR's scanability fix.
  layout?: "hero" | "detail" | "compact";
}) {
  const isCompact = layout === "compact";
  const showFullActions = !isCompact;
  const showLanguageToggle = layout === "detail";
  const { colors, ui } = useAppTheme();
  const styles = useMemo(() => createStyles(colors, ui), [colors, ui]);
  const cache = useStoryCache();
  const [language, setLanguage] = useState<Language>("en");
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportCategory, setReportCategory] = useState<ReportCategory | null>(null);
  const [reportText, setReportText] = useState("");
  const [reportBusy, setReportBusy] = useState(false);
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
  const labels = isCompact
    ? (story.topics.length > 0 ? story.topics.slice(0, 1).map(topicLabel) : story.countries.slice(0, 1))
    : [...story.countries.slice(0, 1), ...story.topics.slice(0, 1).map(topicLabel)];

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

  async function handleReportSubmit() {
    if (reportBusy || !reportCategory) return;
    setReportBusy(true);
    try {
      await reportIssue(story.id, { category: reportCategory, description: reportText.trim(), language });
      setReportOpen(false);
      setReportCategory(null);
      setReportText("");
      setActionStatus("Report received. Our editors will look at it. Thank you.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Couldn't send your report. Please try again.";
      setActionStatus(`${message} Your report is still here.`);
    } finally { setReportBusy(false); }
  }

  return (
    <View style={[styles.card, isCompact ? styles.cardCompact : styles.cardRich]} accessible={false}>
      <View style={isCompact ? styles.compactContent : styles.richContent}>
        <View style={styles.labels}>
          {labels.map((label) => (
            <View key={label} style={styles.pill}>
              <Text style={styles.pillText}>{label}</Text>
            </View>
          ))}
        </View>

        {story.published_at && <Text style={styles.date}>{new Date(story.published_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</Text>}
        {language !== renderedLanguage && <Text style={styles.date}>Telugu translation isn’t available yet. Showing English.</Text>}
        {story.personalization?.explanation && <Text style={styles.date}>{story.personalization.explanation}</Text>}
        {isHumanReviewed && (
          <View style={styles.reviewedBadge}>
            <Text style={styles.reviewedBadgeText}>✓ Human-reviewed</Text>
          </View>
        )}
        {/* ADR-019: a link-first brief — short, no "why this matters"; the full story is at the source link. */}
        {story.format === "BRIEF" && (
          <View style={styles.reviewedBadge} accessibilityLabel="Brief. The full story is at the source link.">
            <Text style={styles.reviewedBadgeText}>Brief</Text>
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
            <Text style={[styles.headline, isCompact ? type.headline : type.display]}>{variant.headline}</Text>
          </Pressable>
        ) : (
          <Text style={[styles.headline, isCompact ? type.headline : type.display]} accessibilityRole="header">
            {variant.headline}
          </Text>
        )}

        <Text style={[styles.body, type.body]}>{variant.summary}</Text>
        {!isCompact && whyMatters ? (
          <Text style={[styles.why, !isCompact && styles.whyRich, renderedLanguage === "te" && styles.whyTe]}>
            Why this matters: {whyMatters}
          </Text>
        ) : null}

        {!isCompact && primarySource && (
          <Pressable
            onPress={() => onOpenSource(primarySource.url)}
            accessibilityRole="link"
            accessibilityLabel={`Read the original source${primarySource.title ? `: ${primarySource.title}` : ""}`}
            style={styles.touchTarget}
          >
            {/* R9: in a feed (onOpen set) attribution stays compact; the full
                source title shows on story detail and in the label. */}
            <Text style={styles.sourceLink}>
              {onOpen
                ? `Read the original source · ${sourceDomain(primarySource.url)} ↗`
                : `Read the original source${primarySource.title ? `: ${primarySource.title}` : ""} ↗`}
            </Text>
          </Pressable>
        )}

        {actionStatus && <Text accessibilityLiveRegion="polite">{actionStatus}</Text>}
        <View style={styles.actions}>
          {showLanguageToggle && hasTelugu && (
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
          {showFullActions && (
            <Pressable
              onPress={handleShare}
              accessibilityRole="button"
              accessibilityLabel={`Share: ${variant.headline}`}
              style={[styles.actionButton, styles.actionButtonShare]}
            >
              <Text style={styles.actionButtonText}>Share</Text>
            </Pressable>
          )}
          <Pressable
            onPress={handleSaveToggle}
            disabled={saving}
            accessibilityRole="button"
            accessibilityState={{ selected: saved }}
            accessibilityLabel={saved ? `Unsave: ${variant.headline}` : `Save: ${variant.headline}`}
            style={[styles.actionButton, saved && styles.actionButtonSaved]}
          >
            <Text style={[styles.actionButtonText, saved && styles.actionButtonTextActive]}>
              {saved ? "Saved" : "Save"}
            </Text>
          </Pressable>
          {showFullActions && (
            <Pressable
              onPress={() => setReportOpen((open) => !open)}
              accessibilityRole="button"
              accessibilityState={{ expanded: reportOpen }}
              accessibilityLabel={`Report an issue: ${variant.headline}`}
              style={[styles.actionButton, styles.actionButtonReport]}
            >
              <Text style={styles.actionButtonText}>Report</Text>
            </Pressable>
          )}
        </View>
        {showFullActions && reportOpen && (
          <View style={styles.reportPanel}>
            <Text style={styles.reportHeading} accessibilityRole="header">What&apos;s the problem?</Text>
            <View accessibilityRole="radiogroup" style={styles.reportChoices}>
              {REPORT_CATEGORIES.map((category) => {
                const selected = reportCategory === category.value;
                return (
                  <Pressable
                    key={category.value}
                    onPress={() => setReportCategory(category.value)}
                    accessibilityRole="radio"
                    accessibilityState={{ checked: selected, disabled: reportBusy }}
                    accessibilityLabel={category.label}
                    disabled={reportBusy}
                    style={[styles.actionButton, selected && styles.langButtonActive]}
                  >
                    <Text style={[styles.actionButtonText, selected && styles.langButtonTextActive]}>{category.label}</Text>
                  </Pressable>
                );
              })}
            </View>
            <TextInput
              value={reportText}
              onChangeText={setReportText}
              placeholder="Details (optional)"
              placeholderTextColor={colors.muted}
              accessibilityLabel="Details (optional)"
              accessibilityHint="Only our editors see reports. Please don't include your name, email or phone number."
              multiline
              maxLength={2000}
              editable={!reportBusy}
              style={styles.reportInput}
            />
            <Text style={styles.reportNote}>Only our editors see reports. Please don&apos;t include your name, email or phone number.</Text>
            <View style={styles.actions}>
              <Pressable
                onPress={handleReportSubmit}
                accessibilityRole="button"
                accessibilityLabel="Send report"
                accessibilityState={{ disabled: reportBusy || !reportCategory }}
                disabled={reportBusy || !reportCategory}
                style={[styles.actionButton, styles.langButtonActive, (reportBusy || !reportCategory) && styles.disabled]}
              >
                <Text style={[styles.actionButtonText, styles.langButtonTextActive]}>{reportBusy ? "Sending…" : "Send report"}</Text>
              </Pressable>
              <Pressable onPress={() => setReportOpen(false)} accessibilityRole="button" style={styles.actionButton}>
                <Text style={styles.actionButtonText}>Cancel</Text>
              </Pressable>
            </View>
          </View>
        )}
      </View>
    </View>
  );
}

// §9.2 accessibility: every interactive element has a >=44pt touch target.
function createStyles(colors: AppTheme["colors"], ui: AppTheme["ui"]) {
  return StyleSheet.create({
    card: { backgroundColor: colors.surface },
    // Rich: StoryLead (hero) and the detail screen — no box chrome, a rule
    // line below instead of a border, more breathing room. Reads as a lead
    // newspaper story, not a bordered card.
    cardRich: {
      margin: spacing.md,
      marginBottom: spacing.md,
      paddingBottom: spacing.lg,
      borderBottomWidth: 2,
      borderBottomColor: colors.rule,
    },
    richContent: { gap: spacing.sm },
    // Compact (StoryBrief): every other list row — a slim accent bar
    // instead of a full border/shadow card, tighter padding, a hairline
    // divider below.
    cardCompact: {
      marginHorizontal: spacing.md,
      paddingVertical: spacing.md,
      borderBottomWidth: 1,
      borderBottomColor: ui.borderSubtle,
    },
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
    // Hero/detail pull-quote: wider, a thick rust rule instead of the
    // compact card's thin ink border — the same "why this matters"
    // emphasis treatment web's hero story gets in parallel.
    whyRich: {
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
    reportPanel: { gap: spacing.sm, paddingTop: spacing.sm },
    reportHeading: { ...typography.meta, textTransform: "none", color: colors.text, fontWeight: "700" },
    reportChoices: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
    reportInput: {
      ...typography.body,
      color: colors.text,
      minHeight: 88,
      padding: spacing.sm,
      borderWidth: 1,
      borderColor: ui.borderControl,
      borderRadius: radius.md,
      textAlignVertical: "top",
    },
    reportNote: { ...typography.meta, textTransform: "none", color: colors.muted },
    disabled: { opacity: 0.5 },
  });
}
