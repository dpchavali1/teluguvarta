import Link from "next/link";

const COLUMNS = [
  {
    heading: "Read",
    links: [
      { href: "/", label: "Today" },
      { href: "/latest", label: "Latest stories" },
      { href: "/topics", label: "All topics" },
      { href: "/search", label: "Search" },
      { href: "/saved", label: "Saved" },
    ],
  },
  {
    heading: "About",
    links: [
      { href: "/about", label: "About TTE" },
      { href: "/ai-disclosure", label: "AI disclosure" },
      { href: "/corrections", label: "Corrections policy" },
      { href: "/onboarding", label: "Personalize" },
    ],
  },
  {
    heading: "Legal",
    links: [
      { href: "/privacy", label: "Privacy" },
      { href: "/terms", label: "Terms" },
      { href: "/copyright-takedown", label: "Copyright / takedown" },
      { href: "/account/delete", label: "Delete account" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <div className="site-footer__about">
          <p className="brand brand--footer">
            <span className="brand__mark" aria-hidden="true" lang="te">తె</span>
            <span className="brand__name">The Telugu Edit</span>
          </p>
          <p>
            TTE publishes original AI-drafted summaries with links to the
            source article — never reproduced headlines, article text, or images.
          </p>
        </div>
        {COLUMNS.map((column) => (
          <nav key={column.heading} aria-label={column.heading} className="site-footer__col">
            <p className="site-footer__heading">{column.heading}</p>
            <ul>
              {column.links.map((link) => (
                <li key={link.href}><Link href={link.href}>{link.label}</Link></li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <p className="site-footer__base">© {new Date().getUTCFullYear()} The Telugu Edit · Browsing never requires an account.</p>
    </footer>
  );
}
