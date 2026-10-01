"use client";

import Link from "next/link";
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";

export type Tone = "ok" | "warn" | "danger" | "neutral";

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`status-pill status-pill--${tone}`}>{children}</span>;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle ? <p className="page-header__sub">{subtitle}</p> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="empty-block">
      <strong>{title}</strong>
      {hint ? <p>{hint}</p> : null}
      {action}
    </div>
  );
}

export function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: ReactNode }) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint ? <p className="field__hint">{hint}</p> : null}
    </div>
  );
}

interface ToastItem {
  id: number;
  tone: "ok" | "danger";
  message: string;
}

const ToastContext = createContext<(tone: "ok" | "danger", message: string) => void>(() => {});

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((tone: "ok" | "danger", message: string) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, tone, message }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), tone === "danger" ? 8000 : 3500);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast--${t.tone}`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function StatTile({ href, label, value, note, tone = "neutral" }: { href: string; label: string; value: ReactNode; note?: string; tone?: Tone }) {
  return (
    <Link href={href} className={`stat-tile stat-tile--${tone}`}>
      <span className="stat-tile__label">{label}</span>
      <strong className="stat-tile__value">{value}</strong>
      {note ? <span className="stat-tile__note">{note}</span> : null}
    </Link>
  );
}

// Review 2026-09-30 R7: when a list was loaded, and a refresh. Lists don't
// poll (rows would move under the j/k cursor), so after five minutes the
// note turns into a warning instead.
const STALE_LIST_MS = 5 * 60 * 1000;

export function Freshness({ loadedAt, loading, onRefresh }: { loadedAt: Date | null; loading: boolean; onRefresh: () => void }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  const stale = loadedAt !== null && now - loadedAt.getTime() > STALE_LIST_MS;
  const time = loadedAt?.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return (
    <span className="freshness">
      {loadedAt ? (
        <span className={stale ? "freshness__stale" : "state-note"} role={stale ? "status" : undefined}>
          {stale ? `Loaded at ${time} — may be out of date` : `Loaded ${time}`}
        </span>
      ) : null}
      <button type="button" className="button-secondary" onClick={onRefresh} disabled={loading}>
        {loading ? "Loading…" : "Refresh"}
      </button>
    </span>
  );
}
