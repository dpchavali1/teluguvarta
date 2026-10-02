// Synthetic stories for local UI checks only; no production services or storage.
const http = require('node:http');
const port = Number(process.env.INTERFACE_API_PORT ?? 8072);
const stories = Array.from({ length: 6 }, (_, i) => ({
  id: `00000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`,
  canonical_slug: `interface-fixture-${i}`,
  status: 'PUBLISHED', format: 'FULL', sensitivity: 'NONE', importance: 0.5,
  topics: ['education'], countries: ['US'],
  published_at: '2026-10-01T12:00:00Z', updated_at: '2026-10-01T12:00:00Z',
  variants: {
    en: {
      language: 'en', qa_status: 'PASSED',
      headline: i ? 'University publishes updated application checklist' : 'University announces application dates for the next academic year',
      summary: 'The university published its application schedule and checklist. Students can check the original announcement for the required documents and dates.',
      why_matters: 'Applicants can use the checklist to prepare their documents.',
    },
    te: {
      language: 'te', qa_status: 'PASSED',
      headline: 'విద్యార్థుల కోసం విశ్వవిద్యాలయం కొత్త విద్యా సంవత్సరపు దరఖాస్తు తేదీలు మరియు అవసరమైన పత్రాల వివరాలను ప్రకటించింది',
      summary: 'విశ్వవిద్యాలయం దరఖాస్తు తేదీలను ప్రకటించింది. అవసరమైన పత్రాల వివరాలను అసలు ప్రకటనలో చూడవచ్చు.',
      why_matters: null,
    },
  },
  sources: [{ url: 'https://example.org/announcement', title: 'Application schedule', source_name: 'Example University', role: 'PRIMARY' }],
}));
const topics = Array.from({ length: 14 }, (_, i) => ({
  id: `20000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`,
  slug: i === 0 ? 'education' : `topic-${i}`,
  name: i === 0 ? 'Education' : `Topic ${i} — Telugu community`,
  active: true, story_count: 6,
}));
const searchItems = Array.from({ length: 20 }, (_, i) => ({
  ...stories[i % stories.length],
  id: `10000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`,
  canonical_slug: `interface-search-${i}`,
}));
const pagedItems = Array.from({ length: 22 }, (_, i) => ({
  ...searchItems[i % searchItems.length],
  id: `40000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`,
  canonical_slug: `paged-search-${i}`,
  variants: {
    en: { ...stories[0].variants.en, headline: `Search result ${i + 1}: University application checklist` },
    te: { ...stories[0].variants.te, headline: `శోధన ఫలితం ${i + 1}: విద్యార్థుల దరఖాస్తు తేదీలు మరియు పత్రాల వివరాలు` },
  },
}));
const failedSearchPages = new Set();
const fallback = {
  ...stories[0], id: '30000000-0000-4000-8000-000000000001', canonical_slug: 'interface-fallback', status: 'UPDATED',
  updated_at: '2026-10-01T14:00:00Z', variants: { en: stories[0].variants.en },
};
// Deliberately retains an unexpected why_matters value to check ADR-019's UI guard.
const brief = { ...stories[0], id: '30000000-0000-4000-8000-000000000002', canonical_slug: 'interface-brief', format: 'BRIEF' };
const all = [...stories, ...searchItems, fallback, brief];
http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Content-Type', 'application/json');
  if (req.method === 'OPTIONS') { res.end(); return; }
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  const path = url.pathname;
  const q = url.searchParams.get('q');
  let data = {};
  if (path === '/v1/config') data = { topics, countries: [] };
  else if (path === '/v1/home') {
    const state = url.searchParams.get('home_state');
    data = { top_stories: state === 'fixture-empty' ? [] : state === 'fixture-one' ? stories.slice(0, 1) : stories, topics };
  } else if (path === '/v1/stories') {
    const ids = url.searchParams.get('ids');
    data = { items: ids ? all.filter((s) => ids.split(',').includes(s.id)).slice(0, ids.split(',').length) : stories, next_cursor: null };
  } else if (path === '/v1/search') {
    if (q === 'failed') { res.statusCode = 503; res.end('{}'); return; }
    const cursor = url.searchParams.get('cursor');
    if (q === 'page-failure' && cursor && !failedSearchPages.has(cursor)) {
      failedSearchPages.add(cursor);
      res.statusCode = 503; res.end('{}'); return;
    }
    if (cursor === 'invalid') { res.statusCode = 422; res.end('{}'); return; }
    data = ['paged', 'తెలుగు', 'page-failure'].includes(q)
      ? { query: q, items: cursor ? pagedItems.slice(20) : pagedItems.slice(0, 20), next_cursor: cursor ? null : 'fixture-page-2' }
      : { query: q, items: q === 'empty' ? [] : searchItems };
  } else if (path.startsWith('/v1/topics/')) {
    data = { topic: topics.find((t) => t.slug === path.split('/').pop()) ?? topics[0], stories, next_cursor: null };
  } else if (path.endsWith('/share-meta')) {
    const story = all.find((s) => s.canonical_slug === path.split('/').at(-2));
    data = story ? { title: story.variants.en.headline, description: story.variants.en.summary, canonical_url: `http://127.0.0.1:3072/story/${story.canonical_slug}` } : {};
  } else if (path.startsWith('/v1/stories/')) {
    data = all.find((s) => s.canonical_slug === path.split('/').pop());
    if (!data) { res.statusCode = 404; data = {}; }
  }
  res.end(JSON.stringify(data));
}).listen(port, '127.0.0.1', () => console.log(`Synthetic interface API: http://127.0.0.1:${port}`));
