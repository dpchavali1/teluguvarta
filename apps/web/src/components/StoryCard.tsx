"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";

import { storyUrl, type Language, type StoryOut } from "@/lib/api";
import { isSaved, toggleSaved } from "@/lib/saved";
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

export function StoryCard({ story, headingLevel = "h2" }: { story: StoryOut; headingLevel?: "h1" | "h2" }) {
  const [language, setLanguage] = useState<Language>("en");
  const [saved, setSaved] = useState(false);
  const [shareStatus, setShareStatus] = useState<string | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportText, setReportText] = useState("");
  const [reportStatus, setReportStatus] = useState<string | null>(null);
  const hasTelugu = Boolean(story.variants.te);
  const isHumanReviewed = REVIEWED_SENSITIVITIES.has(story.sensitivity);

  useEffect(() => {
    setSaved(isSaved(story.id));
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
      } catch {
        // user cancelled or share failed — fall through to copy-link
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
    const nowSaved = toggleSaved(story.id);
    setSaved(nowSaved);
    if (nowSaved) track("story_save", { story_id: story.id });
  }

  function handleLanguageSwitch(next: Language) {
    if (next !== language) track("language_switch", { story_id: story.id, language: next });
    setLanguage(next);
    setPreferredLanguage(next);
  }

  function handleReportSubmit(event: FormEvent) {
    event.preventDefault();
    track("report_issue", { story_id: story.id, description: reportText });
    setReportOpen(false);
    setReportText("");
    setReportStatus("Thanks — we've logged this for review.");
  }

  return (
    <article className="story-card" aria-labelledby={`story-${story.id}-headline`}>
      <div className="story-card__labels">
        {story.countries.map((c) => (
          <span className="pill" key={c}>{c}</span>
        ))}
        {story.topics.map((t) => (
          <span className="pill" key={t}>{t}</span>
        ))}
      </div>

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

      <Heading className="story-card__headline" id={`story-${story.id}-headline`} lang={language}>
        <Link href={`/story/${story.canonical_slug}`}>{variant.headline}</Link>
      </Heading>

      <p lang={language}>{variant.summary}</p>
      {variant.why_matters && (
        <p className="story-card__why" lang={language}>
          <strong>Why this matters:</strong> {variant.why_matters}
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
        {hasTelugu && (
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
        <button type="button" onClick={handleShare} aria-label={`Share: ${variant.headline}`}>
          Share
        </button>
        <button
          type="button"
          onClick={handleSaveToggle}
          aria-pressed={saved}
          aria-label={saved ? `Unsave: ${variant.headline}` : `Save: ${variant.headline}`}
        >
          {saved ? "Saved" : "Save"}
        </button>
        <button
          type="button"
          onClick={() => setReportOpen((open) => !open)}
          aria-expanded={reportOpen}
          aria-label={`Report an issue: ${variant.headline}`}
        >
          Report an issue
        </button>
      </div>

      {shareStatus && (
        <p className="story-card__inline-status" role="status">
          {shareStatus}
        </p>
      )}

      {reportOpen && (
        <form className="story-card__report" onSubmit={handleReportSubmit}>
          <label htmlFor={`report-${story.id}`}>Describe the issue with this story</label>
          <textarea
            id={`report-${story.id}`}
            value={reportText}
            onChange={(event) => setReportText(event.target.value)}
            rows={2}
          />
          <div className="story-card__report-actions">
            <button type="submit">Submit</button>
            <button type="button" onClick={() => setReportOpen(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      {reportStatus && (
        <p className="story-card__inline-status" role="status">
          {reportStatus}
        </p>
      )}
    </article>
  );
}
