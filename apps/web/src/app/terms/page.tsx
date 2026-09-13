import type { Metadata } from "next";

export const metadata: Metadata = { title: "Terms" };

export default function TermsPage() {
  return (
    <div className="legal">
      <h1>Terms of use</h1>
      <p>
        TTE provides original news summaries and links to source
        articles for informational purposes. Story text is AI-drafted and
        human-reviewed for sensitive categories — see our{" "}
        <a href="/ai-disclosure">AI disclosure</a> page for details.
      </p>
      <p>
        Content on the linked source articles belongs to its original
        publishers; TTE does not claim rights over source content
        beyond the original summary and commentary we publish.
      </p>
      <p>By using this site you agree not to misuse it, including attempting to disrupt its availability or scrape it at volume.</p>
    </div>
  );
}
