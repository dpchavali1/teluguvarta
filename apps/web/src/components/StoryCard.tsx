"use client";

import Link from "next/link";
import { topicLabel } from "@teluguvarta/domain";
import { useEffect, useState, type FormEvent } from "react";

import { Icon } from "@/components/Icon";
import { TimeAgo } from "@/components/TimeAgo";
import { reportIssue, storyUrl, type Language, type StoryOut } from "@/lib/api";
import { formatDate, sourceDomain } from "@/lib/format";
import { SAVED_CHANGE_EVENT, isSaved, toggleSaved } from "@/lib/saved";
import { track } from "@/lib/analytics";
import { getPreferredLanguage, LANGUAGE_CHANGE_EVENT, setPreferredLanguage } from "@/lib/onboarding";

const STATUS_LABEL: Record<string, { text: string; className: string } | undefined> = {
  RETRACTED: { text: "Retracted", className: "badge--danger" },
  UPDATED: { text: "Updated / corrected", className: "badge--accent" },
  CORRECTION_PENDING: { text: "Correction pending", className: "badge--accent" },
};

// NON_NEGOTIABLES #5: sensitivity != "NONE" can never reach a published
// state without passing the human-review gate (see apps/api/app/jobs/
// publish.py:83), so surfacing sensitivity here is a truthful trust signal,
// not a claim we have to separately track.
const REVIEWED_SENSITIVITIES = new Set(["IMMIGRATION", "LEGAL", "FINANCIAL", "BREAKING", "OBITUARY_ACCUSATION"]);

type Display = "default" | "lead" | "brief";

// ADR-014 component contract, one component per surface role:
//   display="lead"    -> StoryLead  (full StoryActions)
//   display="brief"   -> StoryBrief (Save only; whole card is the link)
//   display="default" -> story detail (full StoryActions + per-story
//                        language override, the only place it's offered)
export function StoryCard({ story, headingLevel = "h2", display = "default" }: { story: StoryOut; headingLevel?: "h1" | "h2" | "h3"; display?: Display }) {
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
  const href = `/story/${story.canonical_slug}`;
  const kicker = story.topics[0] ? topicLabel(story.topics[0]) : story.countries[0];
  const country = story.topics.length > 0 ? story.countries[0] : undefined;
  const isBrief = display === "brief";
  const isDetail = display === "default";

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

  const saveButton = (
    <button
      className="story-card__action story-card__action--save"
      type="button"
      onClick={handleSaveToggle}
      aria-pressed={saved}
      aria-label={saved ? `Unsave: ${variant.headline}` : `Save: ${variant.headline}`}
      title={saved ? "Saved" : "Save for later"}
    >
      <Icon name="bookmark" size={17} filled={saved} />
      <span className={isBrief ? "visually-hidden" : undefined}>{saved ? "Saved" : "Save"}</span>
    </button>
  );

  const badges = (story.sensitivity === "BREAKING" || isHumanReviewed || statusNotice) && (
    <div className="story-card__badges">
      {story.sensitivity === "BREAKING" && <span className="badge badge--hot"><span className="badge__pulse" aria-hidden="true" />Breaking</span>}
      {statusNotice && <span className={`badge ${statusNotice.className}`} role="status">{statusNotice.text}</span>}
      {isHumanReviewed && <span className="badge badge--success story-card__reviewed"><Icon name="check" size={13} /> Human-reviewed</span>}
    </div>
  );

  const meta = (
    <p className="story-card__meta">
      {kicker && <span className="story-card__kicker">{kicker}</span>}
      {country && !isBrief && <span className="story-card__country">{country}</span>}
      {story.published_at && <span className="story-card__date"><TimeAgo iso={story.published_at} /></span>}
    </p>
  );

  const variantClass = display === "lead" ? " story-card--lead" : isBrief ? " story-card--brief" : " story-card--detail";

  return (
    <article className={`story-card${variantClass}`} aria-labelledby={`story-${story.id}-headline`}>
      {meta}
      {badges}

      <Heading className="story-card__headline" id={`story-${story.id}-headline`} lang={renderedLanguage}>
        {isDetail ? variant.headline : <Link className="story-card__link" href={href}>{variant.headline}</Link>}
      </Heading>

      {language !== renderedLanguage && <p className="story-card__notice" role="status">Telugu translation isn’t available yet. Showing English.</p>}

      <p className="story-card__summary" lang={renderedLanguage}>{variant.summary}</p>

      {isDetail && (
        <div className="story-card__detail-meta">
          {story.published_at && <span>Published <time dateTime={story.published_at}>{formatDate(story.published_at)}</time></span>}
          {story.status === "UPDATED" && story.updated_at && <span>Updated <time dateTime={story.updated_at}>{formatDate(story.updated_at)}</time></span>}
          {/* ADR-014: the per-story language override is a story-detail
              exception; list items follow the edition-level header control. */}
          {hasTelugu && (
            <div className="segmented" role="group" aria-label="Language">
              <button type="button" aria-pressed={language === "en"} onClick={() => handleLanguageSwitch("en")}>English</button>
              <button type="button" aria-pressed={language === "te"} onClick={() => handleLanguageSwitch("te")} lang="te">తెలుగు</button>
            </div>
          )}
        </div>
      )}

      {!isBrief && story.personalization?.explanation && (
        <p className="story-card__recommendation" lang="en"><Icon name="sparkle" size={15} /> {story.personalization.explanation}</p>
      )}

      {!isBrief && whyMatters && (
        <aside className="story-card__why" lang={renderedLanguage}>
          <strong lang="en">Why this matters</strong>
          <p>{whyMatters}</p>
        </aside>
      )}

      {isDetail && story.sources.length > 0 && (
        <section className="sources" aria-labelledby={`sources-${story.id}`}>
          <h2 id={`sources-${story.id}`} className="sources__title">Original reporting</h2>
          <ul>
            {story.sources.map((source) => (
              <li key={source.url}>
                <a className="sources__link story-card__source-link" href={source.url} target="_blank" rel="noopener noreferrer">
                  <span className="sources__domain">{sourceDomain(source.url)}</span>
                  <span className="sources__name">Read the original source{source.title ? `: ${source.title}` : ""}</span>
                  <Icon name="external" size={16} />
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      {isBrief ? (
        <div className="story-card__footer">
          {primarySource && (
            <a className="story-card__source" href={primarySource.url} target="_blank" rel="noopener noreferrer" aria-label={`Read the original source${primarySource.title ? `: ${primarySource.title}` : ""} (${sourceDomain(primarySource.url)})`}>
              {sourceDomain(primarySource.url)} <Icon name="external" size={13} />
            </a>
          )}
          {saveButton}
        </div>
      ) : (
        <>
          {display === "lead" && primarySource && (
            <a className="story-card__source-link story-card__source-link--lead" href={primarySource.url} target="_blank" rel="noopener noreferrer">
              <span className="sources__domain">{sourceDomain(primarySource.url)}</span>
              Read the original source{primarySource.title ? `: ${primarySource.title}` : ""}
              <Icon name="external" size={14} />
            </a>
          )}
          {/* ADR-014 StoryActions: full set (Share/Save/Report) on StoryLead
              and story-detail; StoryBrief list items get Save only. */}
          <div className="story-card__actions">
            <button className="story-card__action story-card__action--share" type="button" onClick={handleShare} aria-label={`Share: ${variant.headline}`}>
              <Icon name="share" size={17} /><span>Share</span>
            </button>
            {saveButton}
            <button
              className="story-card__action story-card__action--report"
              type="button"
              onClick={() => setReportOpen((open) => !open)}
              aria-expanded={reportOpen}
              aria-label={`Report an issue: ${variant.headline}`}
            >
              <Icon name="flag" size={17} /><span>Report an issue</span>
            </button>
          </div>
        </>
      )}

      {saveError && <p className="story-card__inline-status" role="alert">{saveError}</p>}
      {shareStatus && <p className="story-card__inline-status" role="status">{shareStatus}</p>}

      {!isBrief && reportOpen && (
        <form className="story-card__report" onSubmit={handleReportSubmit}>
          <label htmlFor={`report-${story.id}`}>Describe the issue with this story</label>
          <textarea
            id={`report-${story.id}`}
            value={reportText}
            onChange={(event) => setReportText(event.target.value)}
            rows={3}
            maxLength={2000}
            required
            disabled={reportBusy}
          />
          <div className="story-card__report-actions">
            <button className="button button--primary" type="submit" disabled={reportBusy || !reportText.trim()}>{reportBusy ? "Sending…" : "Submit"}</button>
            <button className="button" type="button" onClick={() => setReportOpen(false)}>Cancel</button>
          </div>
        </form>
      )}

      {!isBrief && reportStatus && <p className="story-card__inline-status" role="status">{reportStatus}</p>}
    </article>
  );
}
