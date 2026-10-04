import type { Metadata } from "next";

import { VisaBulletinBoard } from "@/components/VisaBulletinBoard";
import { PageHeader } from "@/components/StoryGrid";
import { duringBuild, getLatestVisaBulletin, listExamDeadlines } from "@/lib/api";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Visa bulletin & exam dates",
  description: "Latest visa bulletin cutoffs and upcoming exam dates, from official sources.",
};

// P07/ADR-041: editor-entered from official notices and approved before they
// appear here. Following and alerts are in the mobile app.
export default async function TrackersPage() {
  const [bulletin, deadlines] = await Promise.all([
    getLatestVisaBulletin().catch(duringBuild(null)),
    listExamDeadlines().catch(duringBuild([])),
  ]);
  return (
    <>
      <PageHeader eyebrow="Trackers" title="Visa bulletin & exam dates">
        Entered from official notices and reviewed by our editors. Always confirm on the official source.
      </PageHeader>

      <section aria-labelledby="visa-title">
        <div className="section-head">
          <h2 id="visa-title">Visa bulletin</h2>
        </div>
        {!bulletin || bulletin.entries.length === 0 ? (
          <div className="empty-state">No bulletin has been published yet.</div>
        ) : (
          <VisaBulletinBoard month={bulletin.month} entries={bulletin.entries} sourceUrl={bulletin.source_url} />
        )}
      </section>

      <section aria-labelledby="exam-title">
        <div className="section-head">
          <h2 id="exam-title">Upcoming exam dates</h2>
        </div>
        {deadlines.length === 0 ? (
          <div className="empty-state">No upcoming dates are listed yet.</div>
        ) : (
          <ul>
            {deadlines.map((d) => (
              <li key={d.id}>
                <strong>{d.exam}</strong> · <time dateTime={d.deadline}>{d.deadline}</time> ·{" "}
                <a href={d.source_url} rel="noopener noreferrer">{d.title}</a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
