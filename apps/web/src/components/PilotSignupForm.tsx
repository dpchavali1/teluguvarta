"use client";

import { useState } from "react";

import { submitPilotSignup } from "@/lib/api";

export function PilotSignupForm({ segment, exampleFeed }: { segment: string; exampleFeed: string }) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "done" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setStatus("submitting");
    setError(null);
    try {
      await submitPilotSignup({ email, segment, example_feed: exampleFeed });
      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
      setStatus("error");
    }
  }

  if (status === "done") {
    return <p role="status">You&rsquo;re on the list — we&rsquo;ll be in touch about the pilot.</p>;
  }

  return (
    <form className="pilot-signup-form" onSubmit={handleSubmit}>
      <label className="visually-hidden" htmlFor={`pilot-email-${exampleFeed}`}>
        Email address
      </label>
      <input
        id={`pilot-email-${exampleFeed}`}
        type="email"
        required
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        placeholder="you@example.com"
      />
      <button type="submit" disabled={status === "submitting"}>
        {status === "submitting" ? "Joining…" : "Get early access"}
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
