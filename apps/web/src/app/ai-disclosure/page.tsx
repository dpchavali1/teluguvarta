import type { Metadata } from "next";

export const metadata: Metadata = { title: "AI disclosure" };

export default function AiDisclosurePage() {
  return (
    <div className="legal">
      <h1>AI disclosure</h1>
      <p>
        Story headlines, summaries, and &ldquo;why this matters&rdquo; sections on
        TTE summaries are drafted by AI language models from linked source
        articles, then validated against automated checks before publication.
      </p>
      <ul>
        <li>Every factual claim in a summary must be traceable to a linked source.</li>
        <li>
          Stories about immigration, legal matters, financial matters, or
          breaking news always require a human editor&rsquo;s approval before
          publishing — no exceptions.
        </li>
        <li>
          Telugu translations go through an automated quality check (numbers,
          dates, currency, names, and URLs must match the English original) and
          a sample of sensitive-category translations is human-reviewed.
        </li>
        <li>
          If an approved correction changes the English story, the Telugu
          version is regenerated rather than left stale.
        </li>
      </ul>
      <p>
        We never reproduce a source&rsquo;s own headline, article text, or
        images — every story links directly to its original source.
      </p>
    </div>
  );
}
