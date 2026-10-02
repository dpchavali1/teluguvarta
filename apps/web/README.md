# apps/web — Next.js public site. See docs/tickets/T01.md and T14.md.

Public pages (home/feed, story detail, topic, country, search, saved, about,
legal pages, 404/500) rendered via SSR/ISR against the FastAPI public API
(`NEXT_PUBLIC_API_URL`). Types come from `@teluguvarta/contracts` only — no
hand-rolled duplicate API types.

Saved stories are stored in `localStorage` on the viewer's device (no public
account system exists yet — see `src/lib/saved.ts`).

## Local development

```
pnpm run dev            # http://localhost:3000, needs apps/api running + `pnpm run seed` for real data
pnpm run build && pnpm run start
pnpm run lint
pnpm run typecheck
pnpm run test:a11y      # axe-core check against a running server (home + one story page)
```

`test:a11y` fetches rendered HTML from a running server (`A11Y_BASE_URL`,
default `http://localhost:3000`) and checks it with `axe-core` inside jsdom —
no browser download required. It looks up a real published story via the API
(`NEXT_PUBLIC_API_URL`, default `http://localhost:8000`) unless
`A11Y_STORY_SLUG` is set.

## Interface acceptance

`test:interface` uses Chromium to check seven page categories at five viewport
sizes in English/Telugu and light/dark, plus axe WCAG 2.2 checks at 390px.
Install the Playwright Chromium runtime if it is not already available.
Run these from `apps/web`, with the API and website in separate terminals:

```sh
node scripts/interface-fixture-api.cjs
NEXT_PUBLIC_API_URL=http://127.0.0.1:8072 pnpm build
NEXT_PUBLIC_API_URL=http://127.0.0.1:8072 pnpm exec next start -p 3072
INTERFACE_BASE_URL=http://127.0.0.1:3072 NEXT_PUBLIC_API_URL=http://127.0.0.1:8072 INTERFACE_FIXTURE=1 pnpm test:interface
```

The fixture binds to loopback and serves synthetic stories only. Fixture mode
also checks topic scrolling/focus, empty/one-story Home, returning preferences,
English fallback, corrected/brief detail, search errors/caps and unavailable or
corrupt bookmarks. It never calls a production deletion endpoint. Stop the dev
server before building: dev and build share `.next` output.

`INTERFACE_OUT_DIR` controls screenshots and JSON reports (default: system temp).
`INTERFACE_JOURNEYS_ONLY=1` reruns just state journeys after a passing layout matrix.
For a same-fixture performance comparison, serve an isolated baseline production
build too, set `INTERFACE_BASELINE_URL`, and run `pnpm test:interface-performance`.
It compares 36 cold/warm cases across Home, Saved and detail at 320/390/1440px
in both languages, recording CLS and compressed HTML/JS/CSS/font bytes. Warm
cases first visit Home and load the preferred-language fonts. JS resource sums
include speculative prefetch/cache timing; use production build output for
bundle-size comparisons. For the ports above, the comparison command is:

```sh
INTERFACE_BASE_URL=http://127.0.0.1:3072 INTERFACE_BASELINE_URL=http://127.0.0.1:3073 NEXT_PUBLIC_API_URL=http://127.0.0.1:8072 pnpm test:interface-performance
```

Add `INTERFACE_SLOW_CHECK=1` for a separate 320px Telugu-detail cold comparison
that delays each JS/font request by 1500ms. This is a controlled delay, not a
mobile-network emulation.

Verify language first paint, accessible copy, switching, cross-tab updates and
quota-failure navigation/onboarding against the running fixture build:

```sh
INTERFACE_BASE_URL=http://127.0.0.1:3072 NEXT_PUBLIC_API_URL=http://127.0.0.1:8072 INTERFACE_FIXTURE=1 pnpm test:language-layout
```

This checks Telugu detail with React bundles blocked and English static Home
with every script disabled. Dynamic detail uses an existing streamed boundary
that requires its inline completion script; fully script-disabled detail
delivery remains a separate limitation.

These are local synthetic measurements, not production Core Web Vitals or
native-device accessibility evidence.

The final acceptance record and remaining native/production gates are in
[`docs/reviews/2026-10-01-improvement-plan.md`](../../docs/reviews/2026-10-01-improvement-plan.md).
