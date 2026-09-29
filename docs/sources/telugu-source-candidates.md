# Telugu source candidates — draft rights evidence

- **Date gathered**: 2026-09-28
- **Status**: DRAFT evidence only, pending owner review under
  [ADR-002](../adr/ADR-002-source-rights-approval-policy.md). Nothing here is
  an approval. Every source stays `DISABLED` until a named `ADMIN` reviewer
  checks the evidence and enables it as `LINK_ONLY` (Phase 0b of
  `docs/plans/gemini-hetzner-telugu-plan.md`; target is at least 3 approved
  Telugu sources before T26).
- **Gathered by**: Claude Code research agent. This is not a legal opinion.
  Quotes are short excerpts; open the linked page before you decide.

**How it was checked**: every feed URL marked *verified* was fetched with
`curl` on 2026-09-28 and returned HTTP 200 with an XML `<rss>` body holding at
least one `<item>`. Terms pages were fetched and searched for clauses about
RSS, linking, reproduction and automated access. Robots.txt was checked for
rules on the feed path and for `User-agent: *`.

**Display rule (ADR-002)**: a LINK_ONLY story shows *our own* headline and
summary plus a link to the original. It never reproduces the source's headline
text or article body. The verdicts below assume that rule. (The research brief
wrongly said "headline"; ADR-002 governs.)

**Category note**: only `entertainment`, `sports` and `community_events` are
on the free-tier allowlist. Every other category suggested below will count
as UNKNOWN on the free tier.

## Summary

| # | Outlet | Feed URL | Verified? | Terms / policy URL | Verdict | Suggested category |
|---|---|---|---|---|---|---|
| 1 | Telangana State Portal (govt) | https://www.telangana.gov.in/feed/ | Yes (10 items) | https://www.telangana.gov.in/website-policies/copyright-policy/ | LIKELY OK | telangana (UNKNOWN on free tier) |
| 2 | Namasthe Telangana (ntnews.com) | https://www.ntnews.com/feed | Yes (200 items) | https://www.ntnews.com/terms-conditions | LIKELY OK (caveat) | telangana (UNKNOWN) |
| 3 | Telugu360 | https://www.telugu360.com/feed/ | Yes (10 items) | https://www.telugu360.com/terms-of-use/ | LIKELY OK | entertainment (much of it is politics) |
| 4 | Telugu Times (US diaspora) | https://www.telugutimes.net/feed | Yes (18 items) | https://www.telugutimes.net/terms-and-conditions | LIKELY OK (caveat) | community_events |
| 5 | NTV Telugu | https://ntvtelugu.com/feed | Yes (60 items) | https://ntvtelugu.com/terms-conditions | LIKELY OK (terms say nothing on RSS or linking) | ap / telangana (UNKNOWN) |
| 6 | 123telugu | https://www.123telugu.com/feed | Yes (30 items) | https://www.123telugu.com/disclaimer | LIKELY OK (terms say nothing on RSS or linking) | entertainment |
| 7 | BBC News Telugu | https://feeds.bbci.co.uk/telugu/rss.xml | Yes (14 items) | https://www.bbc.co.uk/usingthebbc/terms-of-use/ (§15) | UNCLEAR: business use needs BBC permission | politics / world (UNKNOWN) |
| 8 | ABP Desam | https://telugu.abplive.com/home/feed | Yes (21 items) | https://telugu.abplive.com/disclaimer | UNCLEAR | ap / telangana (UNKNOWN) |
| 9 | Sakshi | https://www.sakshi.com/rss.xml | Yes (10 items) | https://www.sakshi.com/termsofusage | UNCLEAR | ap (UNKNOWN) |
| 10 | Asianet News Telugu | https://telugu.asianetnews.com/rss | Yes (99 items) | https://telugu.asianetnews.com/terms-of-use | UNCLEAR | ap / telangana (UNKNOWN) |
| 11 | OneIndia Telugu | https://telugu.oneindia.com/rss/feeds/telugu-news-fb.xml | Yes (30 items) | https://www.oneindia.com/terms-service.html | UNCLEAR | ap / telangana (UNKNOWN) |
| 12 | TANA / NATS / ATA (US associations) | none found | No | none found | UNCLEAR: no feed, ask the orgs | community_events |
| 13 | AP govt (ap.gov.in, apcmo, IPR AP, APNRTS) | none found | No (sites unreachable) | not fetched | UNCLEAR: retry from another network | ap (UNKNOWN) |
| 14 | Samayam Telugu | https://telugu.samayam.com/sitemap/rssfeed.xml | Yes (33 items) | https://telugu.samayam.com/rss (+ /termsandcondition.cms) | AVOID | — |
| 15 | TV9 Telugu | https://tv9telugu.com/feed | Yes (59 items) | https://tv9telugu.com/terms-and-conditions | AVOID | — |
| 16 | Eenadu | none (`/rss` returns 410) | No | https://www.eenadu.net/terms-conditions | AVOID | — |
| 17 | Andhra Jyothy | none found (`/rss`, `/rss.xml` return 404) | No | no terms link found on homepage | AVOID for now | — |

## Per-outlet notes

**1. Telangana State Portal (govt).** WordPress feed of CM and government
activity (English). The copyright policy page is an unedited NIC template that
shows all three variants at once. "Moderate" and "Liberal" say material "may
be reproduced free of charge", with the source acknowledged. "Conservative"
says it "may NOT be reproduced under any circumstances". LINK_ONLY reproduces
nothing, so even the strictest reading does not forbid linking and
summarizing. Robots allows `*`. The best candidate for evidence, but record
the template ambiguity in the review note.

**2. Namasthe Telangana.** The terms say "You must not: Republish material"
and "Redistribute content". They also include a hyperlinking clause:
"News organizations" and "Search engines" "may link to our Website without
prior written approval". That clause is the clearest affirmative linking
permission among the commercial outlets. Caveat: robots.txt blocks GPTBot,
CCBot and ChatGPT-User at `/`. That signals an anti-AI-crawler stance even
though our fetcher is none of those bots. The reviewer should weigh this
before letting AI summaries run on its content.

**3. Telugu360.** English-language Telugu politics and film site. The terms
say republishing, translating for republication or commercial reuse "requires
the relevant rights holder's permission". Linking and original summaries are
not restricted. Robots allows `*`.

**4. Telugu Times.** US diaspora outlet with Telugu and English content
covering associations, events and US politics. The terms say "You may not
reproduce, copy, modify, or redistribute any content" without consent.
Linking is not addressed. Robots allows `*` except wp-admin, and it blocks SEO
bots such as Ahrefs and Semrush. It is small and diaspora-focused, so asking
them directly is cheap.

**5. NTV Telugu.** The terms cover IP only: copying, publishing and
distributing are infringement, and they warn against downloading images.
Nothing on RSS, linking or automated access. Robots allows `*`. Images must
not be used, which LINK_ONLY already guarantees.

**6. 123telugu.** Film and entertainment news. The only policy page is a
warranty disclaimer, with no copyright, RSS or linking clause found. Robots
blocks SEO bots only. Because the terms are this thin, the reviewer may want
the owner to email them.

**7. BBC News Telugu.** Terms of use §15: people may add the BBC News RSS feed
to a site with credit, but "For business use of our RSS feeds you'll need to
get our permission". A fee may also apply. §8 also lists metadata "plucked
from our services to develop or train artificial intelligence" as needing
permission. A formal licence route exists (World Service RSS licence). The
content quality is high, but this outlet needs the owner to ask. Do not
enable without that permission.

**8. ABP Desam.** The disclaimer bars copying and republishing "Except where
specifically authorised". It says nothing on RSS, linking or automation.
Robots allows `*`. Note that `https://telugu.abplive.com/rss` is an HTML
index page. The XML feed is `/home/feed`.

**9. Sakshi.** Terms of usage: "personal, non-commercial purposes" and "Not
to use any automated systems or means, except for those provided by us". The
RSS feed is arguably a means "provided by us", but combined with the
non-commercial clause this is unclear. Ask the outlet.

**10. Asianet News Telugu.** The terms bar copying or creating "derivative
works" without written authorization. Silent on linking and RSS. Robots
allows `*`.

**11. OneIndia Telugu.** The terms say the platform "may not be reproduced
... or otherwise exploited for any commercial purpose". The public RSS index
page is `https://telugu.oneindia.com/rss/`. Two feed paths work:
`/rss/telugu-news-fb.xml` and `/rss/feeds/telugu-news-fb.xml`. Robots allows
the feed path.

**12. TANA / NATS / ATA.** No RSS was found on tana.org
(`/latest-news` is HTML only), natsworld.org (`/nats-global/news` and event
pages are HTML), or americanteluguassociation.org (`ata-news.php` is HTML).
No terms pages were found on their homepages. **Warning**: `nats.org` is the
National Association of Teachers of Singing, not the Telugu NATS. Its RSS
feeds do respond, but they are the wrong organization. The Telugu NATS is
`natsworld.org`. TTA (`ttaworld.org`) did not respond. These orgs would
probably welcome coverage, but without a feed they need HTML ingestion or
manual entry. Ask them for a feed or for permission.

**13. AP government.** ap.gov.in, apcmo.ap.gov.in, ipr.ap.gov.in and
andhrapradesh.gov.in all failed to connect from this network, which may be
geo or IP filtering. apnrts.ap.gov.in loaded but has no `/feed`. Nothing is
verified. Retry from an Indian IP or check with the AP I&PR department.

**14. Samayam Telugu (Times Internet).** The RSS page says the feeds are for
personal, non-commercial use only. Displaying or aggregating them
commercially without written permission and a syndication fee is prohibited.
The main terms also forbid inclusion "in any public or private electronic
retrieval system". Avoid unless licensed.

**15. TV9 Telugu.** The terms bar users from "frame or link to any of the
materials" and from "unauthorized spidering, scraping". These appear in the
Application terms, but that is the only terms page linked from the site.
Robots disallows `*html/feed*`, though the root `/feed` is not covered.

**16. Eenadu.** No working public feed: `/rss` redirects to a 410 page. The
terms call any distribution of its material copyright infringement and say
"Such persons will be prosecuted". Robots blocks GPTBot, CCBot and
Google-Extended. Avoid.

**17. Andhra Jyothy.** No public feed found. Robots references `/rss/gn/`
paths, which look like Google-News-only feeds. No terms link was visible in
the homepage HTML, so no terms were verified. Avoid until the owner can find
a feed and terms.

**Dropped**: PIB Hyderabad. `RssMain.aspx?...Regid=3` redirects to a Hindi
national feed (`Lang=2`), not Telugu. Gulte `/feed` returns 410. Great Andhra
`/rss.xml` returns 404. News18 Telugu feeds return 403. Hindustan Times
Telugu has no Telugu feed found.
