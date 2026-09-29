# Admin redesign — plan (2026-09-29, not started)

**Goal (owner's words):** make the whole admin modern and easy to use; tasks
must be smooth with very little manual involvement. The first version of
`/sources` (bare inputs, table + hidden `<details>`) was called "very very
primitive" after real use on the VPS.

**Hard limits (do not automate away):** ADR-002 source-rights gate — a human
still supplies evidence URL + reviewer before a source leaves DISABLED;
immigration/legal/financial/breaking stories always human-reviewed
(NON_NEGOTIABLES). "Less manual" = fewer clicks and better defaults, not
removing these gates.

## Where we are
- Admin app: `apps/admin` (Next.js, bare-tag CSS in `src/app/globals.css`,
  tokens in `tokens.css` shared with web, nav in `src/components/AdminNav.tsx`).
- Pages: `/` (near-empty), `/login`, `/review`, `/review/[id]`,
  `/observability`, `/sources` (new, forms just added).
- Deployed on the VPS: https://admin.5-78-188-206.sslip.io ; deploy =
  push to main, then `./infra/deploy/deploy.sh` on the VPS (it git-pulls).
- Not verified in a browser by Claude yet — start by looking at each page.

## Work items (in order)
1. **Look at every page first** (screenshots, phone + desktop width) and list
   concrete problems. Run the `web-design-guidelines` skill for a11y/UX.
2. **Shared shell + components**: consistent layout, status badges, cards,
   toasts, inline validation, empty/loading/error states. Reuse design tokens
   (ADR-010 "Folio"); no new visual language.
3. **Sources**: card per source (status badge, last fetch, fail count,
   "needs rights review" prompt); add-source flow with **presets**
   (e.g. "US government feed": prefills type/country/permitted fields/
   restrictions/terms text) and a **Test feed** button (fetch URL, show first
   headlines, catch bad URLs before saving); category suggestions with the
   ADR-015 free-tier eligibility shown plainly.
4. **Dashboard (`/`)**: pipeline at a glance — active sources, jobs pending,
   review-queue count, AI spend vs budget, anything failing — each a link to
   the page that fixes it.
5. **Review queue**: keyboard-friendly triage, bulk actions where safe,
   clear "why is this held" reason (e.g. `NO_PAID_PROVIDER`).
6. **Automation to cut manual work** (needs API changes + tests): a
   `POST /v1/admin/sources/test-feed` endpoint; optional "add + set rights +
   activate" in one call for presets (still requires evidence fields).
7. Verify in a real browser, run admin `tsc` **and** `next lint` (build runs
   ESLint — a Docker build failed once on a lint error tsc missed), update
   PROGRESS.md, commit, push, then deploy on the VPS.

## Open questions for the owner
- Any product/tool whose admin they like, or a screenshot to copy?
- Phone use of the admin, or desktop only?
