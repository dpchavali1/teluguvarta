import Link from "next/link";

const LEGAL_LINKS = [
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
  { href: "/ai-disclosure", label: "AI disclosure" },
  { href: "/corrections", label: "Corrections policy" },
  { href: "/copyright-takedown", label: "Copyright / takedown" },
  { href: "/account/delete", label: "Delete account" },
];

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <p>
          TTE publishes original AI-drafted summaries with links to the
          source article — never reproduced headlines, article text, or images.
        </p>
        <nav aria-label="Legal">
          <ul>
            {LEGAL_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href}>{link.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
