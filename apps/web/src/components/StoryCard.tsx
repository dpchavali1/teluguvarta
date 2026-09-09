"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { storyUrl, type Language, type StoryOut } from "@/lib/api";
import { isSaved, toggleSaved } from "@/lib/saved";
import { track } from "@/lib/analytics";

const STATUS_LABEL: Record<string, { text: string; className: string } | undefined> = {
  RETRACTED: { text: "Retracted", className: "story-card__notice--retracted" },
  UPDATED: { text: "Updated / corrected", className: "story-card__notice--updated" },
  CORRECTION_PENDING: { text: "Correction pending", className: "story-card__notice--updated" },
};

export function StoryCard({ story, headingLevel = "h2" }: { story: StoryOut; headingLevel?: "h1" | "h2" }) {
  const [language, setLanguage] = useState<Language>("en");
  const [saved, setSaved] = useState(false);
  const hasTelugu = Boolean(story.variants.te);

  useEffect(() => {
    setSaved(isSaved(story.id));
  }, [story.id]);

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
      window.alert("Link copied to clipboard.");
    } catch {
      window.prompt("Copy this link:", url);
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
  }

  function handleReportIssue() {
    const description = window.prompt("Describe the issue with this story:");
    if (description === null) return;
    track("report_issue", { story_id: story.id, description });
    window.alert("Thanks — we've logged this for review.");
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

      {statusNotice && (
        <p className={`story-card__notice ${statusNotice.className}`} role="status">
          {statusNotice.text}
        </p>
      )}

      <Heading className="story-card__headline" id={`story-${story.id}-headline`}>
        <Link href={`/story/${story.canonical_slug}`}>{variant.headline}</Link>
      </Heading>

      <p>{variant.summary}</p>
      {variant.why_matters && <p className="story-card__why">Why this matters: {variant.why_matters}</p>}

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
        <button type="button" onClick={handleReportIssue} aria-label={`Report an issue: ${variant.headline}`}>
          Report an issue
        </button>
      </div>
    </article>
  );
}
