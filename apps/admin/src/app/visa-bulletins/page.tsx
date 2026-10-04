"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { components } from "@teluguvarta/contracts";
import { useRouter } from "next/navigation";

import { Badge, EmptyState, Field, PageHeader } from "@/components/ui";
import { adminFetch, SessionExpired } from "@/lib/reports";

type Bulletin = components["schemas"]["VisaBulletinOut"];
type Parsed = components["schemas"]["VisaBulletinParseOut"];
type Entry = components["schemas"]["VisaBulletinIn"]["entries"][number];

const SAMPLE = "FINAL_ACTION EB2 INDIA 2012-01-01";

// One entry per line: CHART CATEGORY COUNTRY CUTOFF (cutoff = YYYY-MM-DD, C or U).
function parseEntries(text: string): Entry[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [chart, category, country, cutoff] = line.split(/\s+/);
      if (!chart || !category || !country || !cutoff) throw new Error(`Line ${index + 1}: need CHART CATEGORY COUNTRY CUTOFF`);
      return { chart, category, country, cutoff };
    });
}

// ADR-041: editors enter each month from the official travel.state.gov notice, then approve it.
export default function VisaBulletinsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Bulletin[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [month, setMonth] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [entries, setEntries] = useState("");
  const [pasted, setPasted] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);

  const fail = useCallback(
    (err: unknown) => {
      if (err instanceof SessionExpired) router.replace("/login");
      else setError(err instanceof Error ? err.message : "Request failed");
    },
    [router],
  );
  const load = useCallback(
    () => adminFetch<Bulletin[]>("/v1/admin/visa-bulletins", {}, "Failed to load visa bulletins").then(setRows).catch(fail),
    [fail],
  );
  useEffect(() => void load(), [load]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    try {
      await adminFetch(
        `/v1/admin/visa-bulletins/${month}`,
        { method: "PUT", body: JSON.stringify({ source_url: sourceUrl, entries: parseEntries(entries) }) },
        "Could not save the bulletin",
      );
      setNotice(`Saved ${month} as a draft. Check it against the official notice, then approve.`);
      await load();
    } catch (err) {
      fail(err);
    }
  }

  // ADR-049: text copied from the official PDF fills the form below; nothing is saved until "Save draft".
  async function fill(source: { text: string } | { pdf_base64: string }) {
    setError(null);
    setNotice(null);
    try {
      const parsed = await adminFetch<Parsed>(
        "/v1/admin/visa-bulletins/parse",
        { method: "POST", body: JSON.stringify(source) },
        "Could not read the bulletin",
      );
      if (parsed.month) setMonth(parsed.month);
      setEntries(parsed.entries.map((e) => `${e.chart} ${e.category} ${e.country} ${e.cutoff}`).join("\n"));
      setWarnings(parsed.warnings);
      setNotice(`Read ${parsed.entries.length} entries. Check every row against the official PDF, add the source link, then save.`);
    } catch (err) {
      fail(err);
    }
  }

  async function upload(file: File | undefined) {
    if (!file) return;
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    await fill({ pdf_base64: btoa(binary) });
  }

  async function approve(target: string) {
    setError(null);
    setNotice(null);
    try {
      await adminFetch(`/v1/admin/visa-bulletins/${target}/approve`, { method: "POST" }, "Could not approve the bulletin");
      setNotice(`Approved ${target}. Follower alerts are queued.`);
      await load();
    } catch (err) {
      fail(err);
    }
  }

  return (
    <main>
      <PageHeader title="Visa bulletins" subtitle="Enter each month from the official travel.state.gov notice. Only approved months are public." />
      {error ? <p role="alert">{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      <Field label="Upload the official PDF" htmlFor="vb-pdf" hint="Download the bulletin PDF from travel.state.gov, then choose it here. Fills the form below; saves nothing.">
        <input id="vb-pdf" type="file" accept="application/pdf,.pdf" onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = ""; }} />
      </Field>
      <Field label="Or paste the PDF text" htmlFor="vb-paste" hint="Select all in the PDF, copy, paste here.">
        <textarea id="vb-paste" rows={4} value={pasted} onChange={(e) => setPasted(e.target.value)} />
      </Field>
      <button type="button" onClick={() => void fill({ text: pasted })} disabled={!pasted.trim()}>Fill form from text</button>
      {warnings.length ? <ul role="alert">{warnings.map((w) => <li key={w}>{w}</li>)}</ul> : null}
      <form onSubmit={save}>
        <Field label="Month" htmlFor="vb-month" hint="YYYY-MM">
          <input id="vb-month" value={month} onChange={(e) => setMonth(e.target.value)} pattern="\d{4}-\d{2}" required />
        </Field>
        <Field label="Official source link" htmlFor="vb-source" hint="https travel.state.gov page">
          <input id="vb-source" type="url" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} required />
        </Field>
        <Field label="Entries" htmlFor="vb-entries" hint={`One per line: CHART CATEGORY COUNTRY CUTOFF, e.g. ${SAMPLE}. Charts: FINAL_ACTION, DATES_FOR_FILING. Cutoff: YYYY-MM-DD, C or U.`}>
          <textarea id="vb-entries" rows={8} value={entries} onChange={(e) => setEntries(e.target.value)} required />
        </Field>
        <button type="submit">Save draft</button>
      </form>
      {rows === null && !error ? (
        <p className="state-note">Loading…</p>
      ) : rows?.length === 0 ? (
        <EmptyState title="No bulletins entered yet" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Month</th><th>Entries</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {(rows ?? []).map((row) => (
                <tr key={row.id}>
                  <td>{row.month}</td>
                  <td>{row.entries.length}</td>
                  <td><Badge tone={row.status === "APPROVED" ? "ok" : "warn"}>{row.status}</Badge></td>
                  <td>{row.status !== "APPROVED" ? <button onClick={() => approve(row.month)}>Approve</button> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
