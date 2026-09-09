import type { Metadata } from "next";

export const metadata: Metadata = { title: "Copyright / takedown" };

export default function CopyrightTakedownPage() {
  return (
    <div className="legal">
      <h1>Copyright &amp; takedown requests</h1>
      <p>
        Telugu Global only republishes original, AI-drafted summaries with a
        link to the source — never a source&rsquo;s own headline text, article
        text, or images. Every source is reviewed for republication rights
        before it is used, and any source without confirmed rights is disabled.
      </p>
      <p>
        If you believe a story misrepresents your content, or you are a rights
        holder who wants a source removed, contact us with the story or source
        link. Editors can disable a source or retract a story immediately.
      </p>
    </div>
  );
}
