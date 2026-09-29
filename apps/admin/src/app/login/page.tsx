"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { components } from "@teluguvarta/contracts";

import { apiUrl, setSession } from "@/lib/auth";

type LoginResponse = components["schemas"]["AdminLoginResponse"];
type MfaSetupResponse = components["schemas"]["MfaSetupResponse"];

class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string | undefined
  ) {
    super(message);
  }
}

async function postJson<T>(path: string, body: unknown, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${apiUrl()}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string };
    } | null;
    throw new ApiError(payload?.error?.message ?? "Request failed", response.status, payload?.error?.code);
  }
  return (await response.json()) as T;
}

// ADR-012: an account without MFA gets a restricted enrollment-scope token
// from /login. It is held only in component state — never via setSession —
// so it can't be mistaken for a real session; after enrolling, the admin
// signs in again with a code to get a full token.
type Enrollment = { token: string; setup: MfaSetupResponse };

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [enrollCode, setEnrollCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const mfaInputRef = useRef<HTMLInputElement>(null);
  const [focusMfa, setFocusMfa] = useState(false);

  useEffect(() => {
    if (focusMfa && !enrollment) {
      mfaInputRef.current?.focus();
      setFocusMfa(false);
    }
  }, [focusMfa, enrollment]);

  async function onLogin(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const code = mfaCode.trim();
      const body = await postJson<LoginResponse>("/v1/admin/auth/login", {
        email,
        password,
        ...(code ? { mfa_code: code } : {})
      });
      if (body.mfa_enrollment_required) {
        const setup = await postJson<MfaSetupResponse>("/v1/admin/auth/mfa/setup", {}, body.access_token);
        setEnrollCode("");
        setEnrollment({ token: body.access_token, setup });
        return;
      }
      setSession(body.access_token, body.role);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError && (err.code === "MFA_REQUIRED" || err.code === "INVALID_MFA_CODE")) {
        setMfaCode("");
        setFocusMfa(true);
      }
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function onEnroll(event: React.FormEvent) {
    event.preventDefault();
    if (!enrollment) return;
    setSubmitting(true);
    setError(null);
    try {
      await postJson(
        "/v1/admin/auth/mfa/enroll",
        { secret: enrollment.setup.secret, code: enrollCode.trim() },
        enrollment.token
      );
      setEnrollment(null);
      setMfaCode("");
      setNotice("Two-factor authentication is on. Enter a new code from your app to finish signing in.");
      setFocusMfa(true);
    } catch (err) {
      if (err instanceof ApiError && err.code !== "INVALID_MFA_CODE" && (err.status === 401 || err.status === 403)) {
        // Enrollment token expired or was rejected — start over.
        setEnrollment(null);
        setError("Your setup session expired. Sign in again to continue.");
      } else {
        setEnrollCode("");
        setError(err instanceof Error ? err.message : "Setup failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  function startOver() {
    setEnrollment(null);
    setError(null);
    setNotice(null);
  }

  if (enrollment) {
    return (
      <main className="auth-page">
        <div className="auth-card">
          <div className="auth-brand">
            TTE<span>Admin</span>
          </div>
          <h1>Set up two-factor authentication</h1>
          <p className="auth-step">Step 2 of 2 · one-time setup</p>
          <p>
            Admin accounts need an authenticator app (such as Google Authenticator, 1Password or Authy). Add this
            account to your app, then enter the 6-digit code it shows.
          </p>
          <p>
            <a href={enrollment.setup.otpauth_url}>Open in authenticator app</a>, or enter this key manually:
          </p>
          <p>
            <code className="mfa-secret" aria-label="Setup key">
              {enrollment.setup.secret.match(/.{1,4}/g)?.join(" ")}
            </code>
          </p>
          <form onSubmit={onEnroll}>
            <div>
              <label htmlFor="enroll-code">Authenticator code</label>
              <input
                id="enroll-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength={6}
                required
                autoFocus
                value={enrollCode}
                onChange={(event) => setEnrollCode(event.target.value)}
              />
            </div>
            {error ? <p role="alert">{error}</p> : null}
            <button type="submit" disabled={submitting}>
              {submitting ? "Verifying…" : "Turn on two-factor authentication"}
            </button>
          </form>
          <p>
            <button type="button" className="link-button" onClick={startOver}>
              Cancel and start over
            </button>
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          TTE<span>Admin</span>
        </div>
        <h1>Sign in</h1>
        {notice ? <p role="status" className="auth-notice">{notice}</p> : null}
        <form onSubmit={onLogin}>
          <div>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <div>
            <label htmlFor="mfa-code">Authenticator code</label>
            <input
              id="mfa-code"
              ref={mfaInputRef}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              aria-describedby="mfa-code-hint"
              value={mfaCode}
              onChange={(event) => setMfaCode(event.target.value)}
            />
            <p id="mfa-code-hint" className="field-hint">
              Leave blank on your first sign-in — you&rsquo;ll set up two-factor authentication next.
            </p>
          </div>
          {error ? <p role="alert">{error}</p> : null}
          <button type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  );
}
