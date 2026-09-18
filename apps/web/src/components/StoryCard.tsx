"use client";

import Link from "next/link";
import { topicLabel } from "@teluguvarta/domain";
import { useEffect, useState, type FormEvent } from "react";

import { reportIssue, storyUrl, type Language, type StoryOut } from "@/lib/api";
import { SAVED_CHANGE_EVENT, isSaved, toggleSaved } from "@/lib/saved";
import { track } from "@/lib/analytics";
import { getPreferredLanguage, LANGUAGE_CHANGE_EVENT, setPreferredLanguage } from "@/lib/onboarding";

const STATUS_LABEL: Record<string, { text: string; className: string } | undefined> = {
  RETRACTED: { text: "Retracted", className: "story-card__notice--retracted" },
  UPDATED: { text: "Updated / corrected", className: "story-card__notice--updated" },
  CORRECTION_PENDING: { text: "Correction pending", className: "story-card__notice--updated" },
};

// NON_NEGOTIABLES #5: sensitivity != "NONE" can never reach a published
// state without passing the human-review gate (see apps/api/app/jobs/
// publish.py:83), so surfacing sensitivity here is a truthful trust signal,
// not a claim we have to separately track.
const REVIEWED_SENSITIVITIES = new Set(["IMMIGRATION", "LEGAL", "FINANCIAL", "BREAKING", "OBITUARY_ACCUSATION"]);

export function StoryCard({ story, headingLevel = "h2", display = "default" }: { story: StoryOut; headingLevel?: "h1" | "h2"; display?: "default" | "lead" | "brief" }) {
  const [language, setLanguage] = useState<Language>("en");
  const [saved, setSaved] = useState(false);
  const [shareStatus, setShareStatus] = useState<string | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportText, setReportText] = useState("");
  const [reportStatus, setReportStatus] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const hasTelugu = Boolean(story.variants.te);
  const isHumanReviewed = REVIEWED_SENSITIVITIES.has(story.sensitivity);

  useEffect(() => {
    const sync = () => setSaved(isSaved(story.id));
    sync();
    window.addEventListener(SAVED_CHANGE_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => { window.removeEventListener(SAVED_CHANGE_EVENT, sync); window.removeEventListener("storage", sync); };
  }, [story.id]);

  useEffect(() => {
    setLanguage(getPreferredLanguage());
    function onLanguageChange(event: Event) {
      const next = (event as CustomEvent<Language>).detail;
      if (next) setLanguage(next);
    }
    window.addEventListener(LANGUAGE_CHANGE_EVENT, onLanguageChange);
    return () => window.removeEventListener(LANGUAGE_CHANGE_EVENT, onLanguageChange);
  }, []);

  const variant = story.variants[language] ?? story.variants.en;
  if (!variant) return null;

  const renderedLanguage: Language = story.variants[language] ? language : "en";
  const whyMatters = renderedLanguage === "en" ? story.personalization?.why_matters ?? variant.why_matters : variant.why_matters;
  const url = storyUrl(story.canonical_slug);
  const statusNotice = STATUS_LABEL[story.status];
  const primarySource = story.sources[0];
  const Heading = headingLevel;

  async function handleShare() {
    track("story_share", { story_id: story.id });
    const shareData = { title: variant!.headline, text: variant!.summary, url };
    if (typeof navigator !== "undefined" && "share" in navigator) {
      try {
        await navigator.share(shareData);
        return;
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") return;
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setShareStatus("Link copied to clipboard.");
    } catch {
      setShareStatus(url);
    }
  }

  function handleSaveToggle() {
    try {
      const nowSaved = toggleSaved(story.id);
      setSaved(nowSaved);
      setSaveError(null);
      if (nowSaved) track("story_save", { story_id: story.id });
    } catch { setSaveError("Couldn’t save this change on your device. Please try again."); }
  }

  function handleLanguageSwitch(next: Language) {
    if (next !== language) track("language_switch", { story_id: story.id, language: next });
    setLanguage(next);
    setPreferredLanguage(next);
  }

  async function handleReportSubmit(event: FormEvent) {
    event.preventDefault();
    if (reportBusy) return;
    setReportBusy(true);
    setReportStatus(null);
    try {
      await reportIssue(story.id, reportText.trim());
      setReportOpen(false);
      setReportText("");
      setReportStatus("Report received. Thank you.");
    } catch { setReportStatus("Couldn't send your report. Your description is still here; please try again."); }
    finally { setReportBusy(false); }
  }

  const variantClass = display === "lead" ? " story-card--lead" : display === "brief" ? " story-card--brief" : "";

  return (
    <article className={`story-card${variantClass}`} aria-labelledby={`story-${story.id}-headline`}>
      <div className="story-card__labels">
        {story.countries.map((c) => (
          <span className="pill" key={c}>{c}</span>
        ))}
        {story.topics.map((t) => (
          <Link className="pill" key={t} href={`/topic/${t}`}>{topicLabel(t)}</Link>
        ))}
      </div>

      {story.published_at && <p className="story-card__date"><time dateTime={story.published_at}>{new Date(story.published_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })}</time>{story.status === "UPDATED" && story.updated_at && <> · Updated <time dateTime={story.updated_at}>{new Date(story.updated_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })}</time></>}</p>}
      {language !== renderedLanguage && <p role="status">Telugu translation isn’t available yet. Showing English.</p>}
      {story.personalization?.explanation && <p className="story-card__recommendation" lang="en">{story.personalization.explanation}</p>}
      {isHumanReviewed && (
        <p className="story-card__reviewed">
          <span aria-hidden="true">✓</span> Human-reviewed
        </p>
      )}

      {statusNotice && (
        <p className={`story-card__notice ${statusNotice.className}`} role="status">
          {statusNotice.text}
        </p>
      )}

      <Heading className="story-card__headline" id={`story-${story.id}-headline`} lang={renderedLanguage}>
        <Link href={`/story/${story.canonical_slug}`}>{variant.headline}</Link>
      </Heading>

      <p lang={renderedLanguage}>{variant.summary}</p>
      {whyMatters && (
        <p className="story-card__why" lang={renderedLanguage}>
          <strong lang="en">Why this matters:</strong> {whyMatters}
        </p>
      )}

      {primarySource && (
        <p>
          <a
            className="story-card__source-link"
            href={primarySource.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Read the original source{primarySource.title ? `: ${primarySource.title}` : ""} ↗
          </a>
        </p>
      )}

      <div className="story-card__actions">
        {/* ADR-014: LanguageControl is edition-level (SiteHeader); a per-card
            override is only offered as a story-detail exception, never on a
            StoryBrief/StoryLead list item. */}
        {display === "default" && hasTelugu && (
          <div role="group" aria-label="Language">
            <button
              type="button"
              aria-pressed={language === "en"}
              onClick={() => handleLanguageSwitch("en")}
            >
              English
            </button>
            <button
              type="button"
              aria-pressed={language === "te"}
              onClick={() => handleLanguageSwitch("te")}
              lang="te"
            >
              తెలుగు
            </button>
          </div>
        )}
        {/* ADR-014 StoryActions: full set (Share/Save/Report) on StoryLead and
            story-detail; StoryBrief list items get Save only. */}
        {display !== "brief" && (
          <button className="story-card__action story-card__action--share" type="button" onClick={handleShare} aria-label={`Share: ${variant.headline}`}>
            Share
          </button>
        )}
        <button
          className="story-card__action story-card__action--save"
          type="button"
          onClick={handleSaveToggle}
          aria-pressed={saved}
          aria-label={saved ? `Unsave: ${variant.headline}` : `Save: ${variant.headline}`}
        >
          {saved ? "Saved" : "Save"}
        </button>
        {display !== "brief" && (
          <button
            className="story-card__action story-card__action--report"
            type="button"
            onClick={() => setReportOpen((open) => !open)}
            aria-expanded={reportOpen}
            aria-label={`Report an issue: ${variant.headline}`}
          >
            Report an issue
          </button>
        )}
      </div>

      {saveError && <p role="alert">{saveError}</p>}
      {shareStatus && (
        <p className="story-card__inline-status" role="status">
          {shareStatus}
        </p>
      )}

      {display !== "brief" && reportOpen && (
        <form className="story-card__report" onSubmit={handleReportSubmit}>
          <label htmlFor={`report-${story.id}`}>Describe the issue with this story</label>
          <textarea
            id={`report-${story.id}`}
            value={reportText}
            onChange={(event) => setReportText(event.target.value)}
            rows={2}
            maxLength={2000}
            required
            disabled={reportBusy}
          />
          <div className="story-card__report-actions">
            <button type="submit" disabled={reportBusy || !reportText.trim()}>{reportBusy ? "Sending…" : "Submit"}</button>
            <button type="button" onClick={() => setReportOpen(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {display !== "brief" && reportStatus && (
        <p className="story-card__inline-status" role="status">
          {reportStatus}
        </p>
      )}
    </article>
  );
}
