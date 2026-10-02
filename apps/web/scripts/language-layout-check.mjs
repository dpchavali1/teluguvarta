#!/usr/bin/env node
// UI13: preference-driven SSR copy and accessible controls, with no new storage.
import assert from 'node:assert/strict';
import { chromium } from '@playwright/test';
const base = process.env.INTERFACE_BASE_URL ?? 'http://localhost:3000';
const api = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const fixtures = process.env.INTERFACE_FIXTURE === '1';
const first = (await (await fetch(new URL('/v1/stories?limit=1', api))).json()).items?.[0];
if (!first?.variants?.en || !first?.variants?.te) throw new Error('A published bilingual story is required');
const detail = `/story/${encodeURIComponent(first.canonical_slug)}`;
const browser = await chromium.launch();
const profile = (language) => JSON.stringify({ lifeStages: [], topics: [], language });
try {
  // The head script can run while React bundles are unavailable.
  const initial = await browser.newContext({ viewport: { width: 320, height: 844 } });
  await initial.addInitScript((value) => localStorage.setItem('tg_onboarding_profile_v1', value), profile('te'));
  const prepaint = await initial.newPage();
  await prepaint.route('**/_next/static/**/*.js', (route) => route.abort());
  await prepaint.goto(new URL(detail, base).href, { waitUntil: 'domcontentloaded' });
  const headline = prepaint.locator('.story-detail .story-card__headline').first();
  assert.equal(await headline.innerText(), first.variants.te.headline);
  assert.equal(await prepaint.getByRole('heading', { name: first.variants.en.headline, exact: true, level: 1 }).count(), 0);
  assert.equal(await prepaint.getByRole('heading', { name: first.variants.te.headline, exact: true, level: 1 }).count(), 1);
  assert.equal(await headline.locator('[lang="te"]').getAttribute('lang'), 'te');
  await initial.close();

  // Static Home keeps canonical English and source links with every script disabled.
  // Dynamic story routes have an existing streamed loading boundary that needs
  // the inline stream-completion script (the React bundles can still be blocked).
  const noScript = await browser.newContext({ javaScriptEnabled: false });
  const plain = await noScript.newPage();
  await plain.goto(base, { waitUntil: 'domcontentloaded' });
  await plain.getByRole('heading', { name: first.variants.en.headline, exact: true, level: 2 }).waitFor();
  assert.equal(await plain.getByRole('heading', { name: first.variants.en.headline, exact: true, level: 2 }).count(), 1);
  assert.equal(await plain.getByRole('heading', { name: first.variants.te.headline, exact: true, level: 2 }).count(), 0);
  assert.equal(await plain.locator('.front-grid__lead .story-card__source-link--lead').count(), 1);
  await noScript.close();

  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error' && /hydrat|Minified React error/i.test(message.text())) errors.push(message.text()); });
  await page.goto(new URL(detail, base).href, { waitUntil: 'networkidle' });
  const header = page.locator('.site-header .language-toggle');
  await header.getByRole('button', { name: 'Telugu', exact: true }).click();
  await page.getByRole('button', { name: `Share: ${first.variants.te.headline}`, exact: true }).waitFor();
  assert.equal(await page.getByRole('heading', { name: first.variants.te.headline, exact: true, level: 1 }).count(), 1);
  assert.equal(await header.getByRole('button', { name: 'Telugu', exact: true }).getAttribute('aria-pressed'), 'true');
  await page.locator('.story-card__detail-meta').getByRole('button', { name: 'English', exact: true }).click();
  await page.getByRole('button', { name: `Share: ${first.variants.en.headline}`, exact: true }).waitFor();
  assert.equal(await header.getByRole('button', { name: 'English', exact: true }).getAttribute('aria-pressed'), 'true');

  const other = await context.newPage();
  await other.goto(base, { waitUntil: 'domcontentloaded' });
  await other.evaluate((value) => localStorage.setItem('tg_onboarding_profile_v1', value), profile('te'));
  await page.getByRole('button', { name: `Share: ${first.variants.te.headline}`, exact: true }).waitFor();
  assert.equal(await page.getByRole('heading', { name: first.variants.te.headline, exact: true, level: 1 }).count(), 1);
  await other.close();

  if (fixtures) {
    await page.goto(new URL('/story/interface-fallback', base).href, { waitUntil: 'domcontentloaded' });
    await page.locator('.story-copy--fallback').waitFor();
    assert.equal(await page.getByRole('heading', { name: first.variants.en.headline, exact: true, level: 1 }).count(), 1);
    assert.equal(await header.getByRole('button', { name: 'Telugu', exact: true }).getAttribute('aria-pressed'), 'true');
  }
  assert.deepEqual(errors, [], 'no hydration/runtime errors');
  await context.close();

  // A quota failure may leave the old stored choice readable. The new choice
  // must still work across client navigation in this session.
  const blocked = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await blocked.addInitScript((value) => {
    localStorage.setItem('tg_onboarding_profile_v1', value);
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function(key, value) {
      if (key === 'tg_onboarding_profile_v1') throw new Error('quota');
      return original.call(this, key, value);
    };
  }, profile('en'));
  const failedStorage = await blocked.newPage();
  await failedStorage.goto(new URL(detail, base).href, { waitUntil: 'networkidle' });
  await failedStorage.locator('.site-header .language-toggle').getByRole('button', { name: 'Telugu', exact: true }).click();
  await failedStorage.getByRole('button', { name: `Share: ${first.variants.te.headline}`, exact: true }).waitFor();
  await failedStorage.locator('.bottom-nav').getByRole('link', { name: 'Latest', exact: true }).click();
  await failedStorage.waitForURL('**/latest');
  await failedStorage.locator('.story-card__headline .story-copy--te').first().waitFor();
  assert.equal(await failedStorage.locator('.site-header .language-toggle').getByRole('button', { name: 'Telugu', exact: true }).getAttribute('aria-pressed'), 'true');
  assert.equal(await failedStorage.evaluate(() => JSON.parse(localStorage.getItem('tg_onboarding_profile_v1')).language), 'en');
  await failedStorage.locator('.bottom-nav').getByRole('link', { name: 'Home', exact: true }).click();
  await failedStorage.waitForURL(base + '/');
  await failedStorage.getByRole('link', { name: 'Personalize your feed', exact: true }).click();
  await failedStorage.getByRole('button', { name: 'Skip for now', exact: true }).click();
  await failedStorage.waitForURL(base + '/');
  await failedStorage.locator('.story-card__headline .story-copy--te').first().waitFor();
  assert.equal(await failedStorage.locator('.site-header .language-toggle').getByRole('button', { name: 'Telugu', exact: true }).getAttribute('aria-pressed'), 'true');
  assert.equal(await failedStorage.evaluate(() => JSON.parse(localStorage.getItem('tg_onboarding_profile_v1')).language), 'en');
  await blocked.close();
  console.log('Passed: pre-hydration Telugu, no-script English, switching/action labels, cross-tab updates, fallback and quota-failure navigation/onboarding');
} finally { await browser.close(); }
