import type { Metadata } from "next";

import { PageHeader } from "@/components/StoryGrid";
import { duringBuild, getLatestVisaBulletin, listExamDeadlines } from "@/lib/api";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Visa bulletin & exam dates",
  description: "Latest visa bulletin cutoffs and upcoming exam dates, from official sources.",
};

const COUNTRIES = ["ALL", "CHINA", "INDIA", "MEXICO", "PHILIPPINES"];
const MOVEMENT: Record<string, string> = { FORWARD: "▲ forward", BACKWARD: "▼ back", SAME: "no change", NEW: "" };
const label = (value: string) => (value === "ALL" ? "All" : value[0] + value.slice(1).toLowerCase());
const cutoff = (value: string) => (value === "C" ? "Current" : value === "U" ? "Unavailable" : value);

// P07/ADR-041: editor-entered from official notices and approved before they
// appear here. Following and alerts are in the mobile app.
export default async function TrackersPage() {
  const [bulletin, deadlines] = await Promise.all([
    getLatestVisaBulletin().catch(duringBuild(null)),
    listExamDeadlines().catch(duringBuild([])),
  ]);
  const final = bulletin?.entries.filter((e) => e.chart === "FINAL_ACTION") ?? [];
  const categories = [...new Set(final.map((e) => e.category))];

  return (
    <>
      <PageHeader eyebrow="Trackers" title="Visa bulletin & exam dates">
        Entered from official notices and reviewed by our editors. Always confirm on the official source.
      </PageHeader>

      <section aria-labelledby="visa-title">
        <div className="section-head">
          <h2 id="visa-title">{bulletin ? `Visa bulletin · ${bulletin.month}` : "Visa bulletin"}</h2>
        </div>
        {!bulletin || categories.length === 0 ? (
          <div className="empty-state">No bulletin has been published yet.</div>
        ) : (
          <>
            <div style={{ overflowX: "auto" }}>
              <table>
                <caption>Final action dates</caption>
                <thead>
                  <tr>
                    <th scope="col">Category</th>
                    {COUNTRIES.map((c) => <th scope="col" key={c}>{label(c)}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {categories.map((category) => (
                    <tr key={category}>
                      <th scope="row">{category}</th>
                      {COUNTRIES.map((country) => {
                        const entry = final.find((e) => e.category === category && e.country === country);
                        return (
                          <td key={country}>
                            {entry ? <>{cutoff(entry.cutoff)} <small>{MOVEMENT[entry.movement] ?? ""}</small></> : "—"}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p><a href={bulletin.source_url} rel="noopener noreferrer">Official notice (travel.state.gov)</a></p>
          </>
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
