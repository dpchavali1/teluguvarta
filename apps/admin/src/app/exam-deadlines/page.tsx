"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { components } from "@teluguvarta/contracts";
import { useRouter } from "next/navigation";

import { Badge, EmptyState, Field, PageHeader } from "@/components/ui";
import { adminFetch, SessionExpired } from "@/lib/reports";

type Deadline = components["schemas"]["ExamDeadlineOut"];

const KINDS = ["REGISTRATION_DEADLINE", "EXAM_DATE", "RESULT_DATE", "APPLICATION_DEADLINE"];
const EMPTY = { exam: "", kind: KINDS[0], title: "", deadline: "", source_url: "" };

// ADR-041 addendum: editor-entered exam/deadline reminders; only approved, upcoming dates are public.
export default function ExamDeadlinesPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Deadline[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState<string | null>(null);

  const fail = useCallback(
    (err: unknown) => {
      if (err instanceof SessionExpired) router.replace("/login");
      else setError(err instanceof Error ? err.message : "Request failed");
    },
    [router],
  );
  const load = useCallback(
    () => adminFetch<Deadline[]>("/v1/admin/exam-deadlines", {}, "Failed to load deadlines").then(setRows).catch(fail),
    [fail],
  );
  useEffect(() => void load(), [load]);

  const set = (key: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  async function act(path: string, init: RequestInit, done: string) {
    setError(null);
    setNotice(null);
    try {
      await adminFetch(path, init, "Request failed");
      setNotice(done);
      if (init.method !== "POST" || path === "/v1/admin/exam-deadlines") {
        setForm(EMPTY);
        setEditing(null);
      }
      await load();
    } catch (err) {
      fail(err);
    }
  }

  function save(event: FormEvent) {
    event.preventDefault();
    const body = JSON.stringify({ ...form, exam: form.exam.trim().toUpperCase() });
    return editing
      ? act(`/v1/admin/exam-deadlines/${editing}`, { method: "PUT", body }, "Draft updated.")
      : act("/v1/admin/exam-deadlines", { method: "POST", body }, "Saved as a draft. Check it against the source, then approve.");
  }

  return (
    <main>
      <PageHeader title="Exam deadlines" subtitle="Enter dates from the official source. Approving queues alerts; 7- and 1-day reminders follow automatically." />
      {error ? <p role="alert">{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      <form onSubmit={save}>
        <Field label="Exam key" htmlFor="ed-exam" hint="Upper-case, e.g. GRE or TOEFL (2–20 letters, digits, hyphen)">
          <input id="ed-exam" value={form.exam} onChange={set("exam")} pattern="[A-Za-z0-9][A-Za-z0-9-]{1,19}" required />
        </Field>
        <Field label="Kind" htmlFor="ed-kind">
          <select id="ed-kind" value={form.kind} onChange={set("kind")}>
            {KINDS.map((kind) => <option key={kind} value={kind}>{kind}</option>)}
          </select>
        </Field>
        <Field label="Title" htmlFor="ed-title">
          <input id="ed-title" value={form.title} onChange={set("title")} maxLength={160} required />
        </Field>
        <Field label="Date" htmlFor="ed-date">
          <input id="ed-date" type="date" value={form.deadline} onChange={set("deadline")} required />
        </Field>
        <Field label="Official source link" htmlFor="ed-source" hint="https link to the exam body's page">
          <input id="ed-source" type="url" value={form.source_url} onChange={set("source_url")} maxLength={500} required />
        </Field>
        <button type="submit">{editing ? "Update draft" : "Save draft"}</button>
        {editing ? <button type="button" onClick={() => { setEditing(null); setForm(EMPTY); }}>Cancel edit</button> : null}
      </form>
      {rows === null && !error ? (
        <p className="state-note">Loading…</p>
      ) : rows?.length === 0 ? (
        <EmptyState title="No deadlines entered yet" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Exam</th><th>Title</th><th>Date</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {(rows ?? []).map((row) => (
                <tr key={row.id}>
                  <td>{row.exam}</td>
                  <td><a href={row.source_url} rel="noreferrer noopener" target="_blank">{row.title}</a><span className="reason-help">{row.kind}</span></td>
                  <td>{row.deadline}</td>
                  <td><Badge tone={row.status === "APPROVED" ? "ok" : row.status === "WITHDRAWN" ? "danger" : "warn"}>{row.status}</Badge></td>
                  <td>
                    {row.status === "DRAFT" ? (
                      <>
                        <button onClick={() => { setEditing(row.id); setForm({ exam: row.exam, kind: row.kind, title: row.title, deadline: row.deadline, source_url: row.source_url }); }}>Edit</button>{" "}
                      </>
                    ) : null}
                    {row.status !== "APPROVED" && row.status !== "WITHDRAWN" ? <button onClick={() => act(`/v1/admin/exam-deadlines/${row.id}/approve`, { method: "POST" }, "Approved. Follower alerts are queued.")}>Approve</button> : null}
                    {row.status === "APPROVED" ? <button onClick={() => act(`/v1/admin/exam-deadlines/${row.id}/withdraw`, { method: "POST" }, "Withdrawn.")}>Withdraw</button> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
