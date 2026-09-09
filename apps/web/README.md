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
