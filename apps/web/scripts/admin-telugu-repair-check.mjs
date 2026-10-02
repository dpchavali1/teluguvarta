#!/usr/bin/env node
// Reuses the web workspace's existing Playwright/axe tools for admin QA.
// Every API request is intercepted; no credentials, providers or live repair.
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const base = process.env.ADMIN_BASE_URL ?? 'http://127.0.0.1:3074';
const output = process.env.INTERFACE_OUT_DIR ?? join(tmpdir(), 'tte-admin-telugu-repair');
mkdirSync(output, { recursive: true });
const browser = await chromium.launch();
const id = '00000000-0000-4000-8000-000000000034';
function fixture({ qa = 'PASSED', left = 2 } = {}) {
  return {
    id, canonical_slug: 'repair-fixture', status: 'PUBLISHED', sensitivity: 'NONE', format: 'FULL',
    importance: 0.5, published_at: '2026-10-01T12:00:00Z', topics: [], countries: [],
    sources: [], review_task: null, corrections: [],
    variants: {
      en: { language: 'en', headline: 'University publishes application details', summary: 'Students can check the original announcement for the dates and required documents.', why_matters: null, qa_status: 'PENDING' },
      te: { language: 'te', headline: 'విద్యార్థుల కోసం వివరాలు ಸುದ್ದಿ', summary: 'అవసరమైన పత్రాల వివరాలను ప్రకటనలో చూడవచ్చు.', why_matters: null, qa_status: qa },
    },
    telugu_repair: { qa_issues: ['MIXED_SCRIPT:headline', 'MISSING_URL:https://example.org/' + 'long-path-'.repeat(30)], english_text_hash: 'a'.repeat(64), telugu_text_hash: 'b'.repeat(64), resets_left: left, can_regenerate: qa === 'FAILED' && left > 0 },
  };
}
async function setup(role = 'ADMIN', state = fixture(), width = 390) {
  const context = await browser.newContext({ viewport: { width, height: 844 } });
  await context.addInitScript((role) => localStorage.setItem('tg_admin_role', role), role);
  const requests = [];
  let failNext = false;
  await context.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/v1/')) {
      return url.origin === new URL(base).origin ? route.continue() : route.abort();
    }
    const headers = { 'Access-Control-Allow-Origin': new URL(base).origin, 'Access-Control-Allow-Credentials': 'true', 'Access-Control-Allow-Headers': 'content-type,x-tte-admin', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS' };
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    if (url.pathname.endsWith('/auth/session')) return route.fulfill({ headers, json: { role, mfa_enrollment_required: false } });
    if (url.pathname.endsWith('/reports')) return route.fulfill({ headers, json: { items: [], open_count: 0 } });
    if (url.pathname.endsWith('/repair-telugu')) {
      const body = request.postDataJSON();
      requests.push(body);
      await new Promise((resolve) => setTimeout(resolve, 150));
      if (failNext) {
        failNext = false;
        return route.fulfill({ status: 409, headers, json: { error: { message: 'Story text changed; reload and review the latest text before repairing' } } });
      }
      if (body.action === 'withhold') {
        state.variants.te.qa_status = 'FAILED';
        state.telugu_repair.can_regenerate = state.telugu_repair.resets_left > 0;
      } else {
        delete state.variants.te;
        state.telugu_repair.telugu_text_hash = null;
        state.telugu_repair.qa_issues = [];
        state.telugu_repair.resets_left--;
        state.telugu_repair.can_regenerate = false;
      }
      return route.fulfill({ headers, json: { story_id: id, status: state.status } });
    }
    return route.fulfill({ headers, json: url.pathname.endsWith(`/stories/${id}`) ? state : url.pathname.endsWith('/config') ? { topics: [], countries: [] } : [] });
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(new URL(`/review/${id}`, base).href);
  const panel = page.getByRole('region', { name: 'Telugu quality and repair' });
  await panel.waitFor();
  return { context, page, panel, requests, state, errors, fail: () => { failNext = true; } };
}
try {
  const test = await setup();
  const { page, panel, requests, state } = test;
  const reason = panel.getByRole('textbox', { name: 'Translation repair reason (required)' });
  assert.equal(await panel.getByRole('button', { name: 'Withhold Telugu', exact: true }).isDisabled(), true);
  assert.equal(await panel.getByRole('button', { name: 'Regenerate Telugu', exact: true }).isDisabled(), true);
  assert.match(await panel.innerText(), /MIXED_SCRIPT:headline/);
  await reason.fill('  Wrong script confirmed  ');
  await panel.getByRole('button', { name: 'Withhold Telugu', exact: true }).click();
  assert.equal(requests.length, 0, 'confirmation required before a request');
  await panel.getByRole('button', { name: 'Cancel repair' }).click();
  assert.equal(requests.length, 0);
  test.fail();
  await panel.getByRole('button', { name: 'Withhold Telugu', exact: true }).click();
  await panel.getByRole('button', { name: 'Confirm withholding' }).click();
  await panel.getByRole('alert').waitFor();
  assert.equal(await reason.inputValue(), '  Wrong script confirmed  ');
  assert.match(await panel.getByRole('alert').innerText(), /reload and review/);
  state.telugu_repair.english_text_hash = 'c'.repeat(64);
  await panel.getByRole('button', { name: 'Reload translation status' }).click();
  await page.waitForFunction(() => document.querySelector('#telugu-repair-reason')?.value === '');
  await reason.fill('Wrong script confirmed');
  await panel.getByRole('button', { name: 'Withhold Telugu', exact: true }).click();
  await panel.getByRole('button', { name: 'Confirm withholding' }).click();
  await page.getByText('Telugu withheld. New responses use English.', { exact: true }).waitFor();
  await page.waitForFunction(() => document.querySelector('#telugu-repair-reason')?.value === '');
  assert.equal(requests[1].english_text_hash, 'c'.repeat(64));
  assert.equal(requests[1].reason, 'Wrong script confirmed');
  await reason.fill('Regenerate the withheld translation');
  assert.equal(await panel.getByRole('button', { name: 'Regenerate Telugu', exact: true }).isEnabled(), true);
  const axe = await new AxeBuilder({ page }).include('section[aria-labelledby="telugu-repair-title"]').withTags(['wcag2a', 'wcag2aa', 'wcag22aa']).analyze();
  assert.deepEqual(axe.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious'), []);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({ path: join(output, 'phone-withheld.png'), fullPage: true });
  await panel.getByRole('button', { name: 'Regenerate Telugu', exact: true }).click();
  assert.equal(requests.length, 2);
  await panel.getByRole('button', { name: 'Confirm regeneration' }).click();
  await page.getByText('Regeneration requested. Readers see English while translation is pending.', { exact: true }).waitFor();
  assert.equal(requests[2].action, 'regenerate');
  assert.deepEqual(test.errors, []);
  await test.context.close();

  const capped = await setup('ADMIN', fixture({ qa: 'FAILED', left: 0 }), 1440);
  await capped.panel.getByRole('textbox').fill('Quality issue');
  assert.equal(await capped.panel.getByRole('button', { name: 'Regenerate Telugu', exact: true }).isDisabled(), true);
  assert.match(await capped.panel.innerText(), /0 of 2 manual translation resets/);
  await capped.page.evaluate(() => scrollTo(0, 0));
  await capped.page.screenshot({ path: join(output, 'desktop-cap.png'), fullPage: true });
  await capped.context.close();

  const editor = await setup('EDITOR');
  assert.equal(await editor.panel.getByRole('button').count(), 0);
  assert.match(await editor.panel.innerText(), /MIXED_SCRIPT:headline/);
  await editor.context.close();
  console.log(`Passed: required reason, confirmation/cancel, stale-error retention/reload, fresh hashes, withholding/regeneration, cap, editor visibility, phone overflow and scoped axe. Screenshots: ${output}`);
} finally { await browser.close(); }
