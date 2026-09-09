import type { Metadata } from "next";

export const metadata: Metadata = { title: "About" };

export default function AboutPage() {
  return (
    <div className="legal">
      <h1>About Telugu Global</h1>
      <p>
        Telugu Global is a bilingual (English/Telugu) news product for the global
        Telugu diaspora, covering immigration, money, jobs, community, and news
        from Andhra Pradesh and Telangana.
      </p>
      <p>
        Every published story is an original, AI-drafted summary and
        &ldquo;why this matters&rdquo; explanation with a clear, clickable link to
        the original source article — never a copy of a source&rsquo;s own
        headline, article text, or images. See our{" "}
        <a href="/ai-disclosure">AI disclosure</a> for details on how stories are
        produced and reviewed.
      </p>
      <p>Browsing Telugu Global never requires an account.</p>
    </div>
  );
}
