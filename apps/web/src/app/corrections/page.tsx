import type { Metadata } from "next";

export const metadata: Metadata = { title: "Corrections" };

export default function CorrectionsPage() {
  return (
    <div className="legal">
      <h1>Corrections policy</h1>
      <p>
        When a published story needs a factual correction, an editor updates the
        story and it is marked &ldquo;Updated / corrected&rdquo; on the story
        card and story page — the correction is never made silently.
      </p>
      <p>
        If a story is retracted entirely, it stays reachable at its original
        link but is clearly marked &ldquo;Retracted&rdquo;.
      </p>
      <p>
        To report an error in a published story, contact us with the story link
        and a description of the issue.
      </p>
    </div>
  );
}
