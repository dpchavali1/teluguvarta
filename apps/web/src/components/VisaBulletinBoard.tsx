"use client";

import { useState } from "react";

type Entry = { chart: string; category: string; country: string; cutoff: string; movement: string };
type Props = { month: string; entries: Entry[]; sourceUrl: string };

const CHARTS = [
  {
    key: "FINAL_ACTION",
    label: "Final action dates",
    help: "A green card can be issued only if your priority date is earlier than the date shown.",
  },
  {
    key: "DATES_FOR_FILING",
    label: "Dates for filing",
    help: "You may start filing once your priority date is earlier than the date shown. USCIS announces each month whether adjustment of status uses this chart.",
  },
] as const;

const COUNTRIES = [
  { key: "ALL", label: "Rest of world" },
  { key: "CHINA", label: "China" },
  { key: "INDIA", label: "India" },
  { key: "MEXICO", label: "Mexico" },
  { key: "PHILIPPINES", label: "Philippines" },
];

const CHIP_ORDER = ["INDIA", "CHINA", "MEXICO", "PHILIPPINES", "ALL"];

const GROUPS = [
  {
    title: "Employment-based",
    rows: [
      ["EB1", "Priority workers"],
      ["EB2", "Advanced degree or exceptional ability"],
      ["EB3", "Skilled workers and professionals"],
      ["EB3-OW", "Other workers"],
      ["EB4", "Special immigrants"],
      ["EB5", "Investors (unreserved)"],
    ],
  },
  {
    title: "Family-sponsored",
    rows: [
      ["F1", "Unmarried sons and daughters of U.S. citizens"],
      ["F2A", "Spouses and children of permanent residents"],
      ["F2B", "Unmarried adult children of permanent residents"],
      ["F3", "Married sons and daughters of U.S. citizens"],
      ["F4", "Siblings of U.S. citizens"],
    ],
  },
];

const formatDate = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

const monthName = (month: string) =>
  new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });

function Cell({ entry }: { entry: Entry | undefined }) {
  if (!entry) return <span className="vb-none">—</span>;
  const arrow =
    entry.movement === "FORWARD" ? (
      <span className="vb-move vb-move--up" title="Moved forward since last month" aria-label="moved forward">▲</span>
    ) : entry.movement === "BACKWARD" ? (
      <span className="vb-move vb-move--down" title="Moved back since last month" aria-label="moved back">▼</span>
    ) : null;
  if (entry.cutoff === "C") return <><span className="badge badge--success">Current</span>{arrow}</>;
  if (entry.cutoff === "U") return <><span className="badge badge--danger">Unavailable</span>{arrow}</>;
  return <><span className="vb-date">{formatDate(entry.cutoff)}</span>{arrow}</>;
}

// P07/ADR-041/ADR-049: approved, editor-entered cutoffs.
export function VisaBulletinBoard({ month, entries, sourceUrl }: Props) {
  const [chart, setChart] = useState<(typeof CHARTS)[number]["key"]>("FINAL_ACTION");
  const [country, setCountry] = useState("ALL_COLUMNS");
  const columns = country === "ALL_COLUMNS" ? COUNTRIES : COUNTRIES.filter((c) => c.key === country);
  const active = CHARTS.find((c) => c.key === chart) ?? CHARTS[0];
  const has = (key: string) => entries.some((e) => e.chart === key);

  return (
    <div className="vb">
      <div className="vb-top">
        <h3 className="vb-month">{monthName(month)} Visa Bulletin</h3>
        <a href={sourceUrl} rel="noopener noreferrer" className="vb-source">Official notice ↗</a>
      </div>

      <div className="chip-list" role="group" aria-label="Chart">
        {CHARTS.filter((c) => has(c.key)).map((c) => (
          <button key={c.key} type="button" className="chip" aria-pressed={chart === c.key} onClick={() => setChart(c.key)}>
            {c.label}
          </button>
        ))}
      </div>
      <p className="vb-help">{active.help}</p>

      <div className="chip-list" role="group" aria-label="Country">
        <button type="button" className="chip" aria-pressed={country === "ALL_COLUMNS"} onClick={() => setCountry("ALL_COLUMNS")}>
          All countries
        </button>
        {CHIP_ORDER.flatMap((key) => COUNTRIES.filter((c) => c.key === key)).map((c) => (
          <button key={c.key} type="button" className="chip" aria-pressed={country === c.key} onClick={() => setCountry(c.key)}>
            {c.label}
          </button>
        ))}
      </div>

      {GROUPS.map((group) => (
        <section key={group.title} className="vb-card" aria-label={group.title}>
          <h4>{group.title}</h4>
          <div className="vb-scroll">
            <table className="vb-table">
              <caption className="visually-hidden">{`${group.title}, ${active.label}`}</caption>
              <thead>
                <tr>
                  <th scope="col">Category</th>
                  {columns.map((c) => <th scope="col" key={c.key}>{c.label}</th>)}
                </tr>
              </thead>
              <tbody>
                {group.rows.map(([code, name]) => (
                  <tr key={code}>
                    <th scope="row">
                      <span className="vb-code">{code}</span>
                      <span className="vb-name">{name}</span>
                    </th>
                    {columns.map((c) => (
                      <td key={c.key}>
                        <Cell entry={entries.find((e) => e.chart === chart && e.category === code && e.country === c.key)} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
      <p className="vb-help">▲ moved forward · ▼ moved back since last month. Always confirm on the official notice.</p>
    </div>
  );
}
