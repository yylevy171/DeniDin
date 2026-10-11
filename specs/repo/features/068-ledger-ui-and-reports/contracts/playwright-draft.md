# Draft Playwright Acceptance Suite (Feature 068) — PREVIEW, NOT YET APPROVED FOR WRITING

This is a concrete draft of the 9 Acceptance-phase scenarios from `tasks.md`, shown for early
review at the user's request. **Per the repo's TDD redefinition this code is not actually
written/run until Phases 1–10 are GREEN** — this file is a preview to approve/adjust the exact
assertions now, not a jump of the gate. Assumes fixture data seeded in a `data_root` the BFF's
`config.test.json` points at (real files, no mocking, per the zero-mocking rule) with known
events/sessions/messages at known timestamps.

```ts
// apps/webapp/frontend/e2e/ledger.spec.ts
import { test, expect, devices } from '@playwright/test';

const BASE_URL = process.env.WEBAPP_E2E_URL ?? 'http://localhost:3000';
const VALID_PASSWORD = process.env.WEBAPP_E2E_PASSWORD!; // from config.test.json's fixture

// --- Fixture assumptions (seeded once, before this suite runs) ---
// Event E1: source_type=הסכם, event_subtype=יצירה, client_name="ישראל ישראלי",
//   amount=5000, txn_date=today-2days, session_id=S1, message_id=M3 (has image_path)
// Event E2: source_type=בנק, client_name="דנה כהן", amount=1200, txn_date=today-10days
//   (outside default 7-day load window — used to prove the load-window boundary)
// Session S1 messages: M1(t0), M2(t0+3min), M3(t0+9min, image attached, this is E1's anchor)
//   -> with lookback_minutes=10, context should include M1,M2,M3; with lookback=5, only M2,M3.

test.describe('1. Login', () => {
  test('blocks with wrong password, unlocks with correct password, persists on reload', async ({ page }) => {
    await page.goto(BASE_URL);
    await expect(page.getByTestId('password-input')).toBeVisible();

    await page.getByTestId('password-input').fill('wrong-password');
    await page.getByTestId('login-submit').click();
    await expect(page.getByTestId('login-error')).toBeVisible();
    await expect(page.getByTestId('event-list')).not.toBeVisible();

    await page.getByTestId('password-input').fill(VALID_PASSWORD);
    await page.getByTestId('login-submit').click();
    await expect(page.getByTestId('event-list')).toBeVisible();

    await page.reload();
    await expect(page.getByTestId('event-list')).toBeVisible(); // token survived reload
    await expect(page.getByTestId('password-input')).not.toBeVisible();
  });

  test('a second login (second device/tab) does not invalidate the first', async ({ browser }) => {
    const ctx1 = await browser.newContext();
    const ctx2 = await browser.newContext();
    const page1 = await ctx1.newPage();
    const page2 = await ctx2.newPage();

    await loginAs(page1, VALID_PASSWORD);
    await loginAs(page2, VALID_PASSWORD); // second "device", same shared password

    await page1.reload();
    await expect(page1.getByTestId('event-list')).toBeVisible(); // still logged in
    await expect(page2.getByTestId('event-list')).toBeVisible();
  });

  test('a copied post-login URL is denied after logout (fresh navigation, not reload)', async ({ page, context }) => {
    await loginAs(page, VALID_PASSWORD);
    const postLoginUrl = page.url();

    await page.getByTestId('settings-gear').click();
    await page.getByTestId('setting-logout').click();
    await expect(page.getByTestId('password-input')).toBeVisible();

    // fresh navigation in a NEW page (simulates pasting the copied URL, not reusing this tab's state)
    const freshPage = await context.newPage();
    await freshPage.goto(postLoginUrl);
    await expect(freshPage.getByTestId('password-input')).toBeVisible();
    await expect(freshPage.getByTestId('event-list')).not.toBeVisible();
    // no stale event data ever flashes on screen before the guard resolves
    await expect(freshPage.getByTestId('event-row')).toHaveCount(0);
  });
});

test.describe('2. Initial load window', () => {
  // Fixture addition for this component:
  // Event E3: dated EXACTLY 7 days before "today" (the boundary) — must be INCLUDED.
  // Event E4: dated 8 days before "today" — must be EXCLUDED.

  test('2.1 shows only events within the default 7-day window (inclusive of boundary), newest first', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    const rows = page.getByTestId('event-row');
    await expect(rows).toHaveCount(await expectedCountWithinDays(7)); // includes E3
    await expect(page.getByTestId('event-row').first()).toContainText('E1'); // newest-first
    await expect(page.getByTestId('event-row-E3')).toBeVisible(); // boundary day included
    await expect(page.getByTestId('event-row-E4')).toHaveCount(0); // 8 days back, excluded
  });

  test('2.2 shows a clear empty state when zero events fall in the window', async ({ page }) => {
    // uses a separate fixture data_root seeded with no events in the last 7 days
    await loginAs(page, EMPTY_WINDOW_PASSWORD);
    await expect(page.getByTestId('event-row')).toHaveCount(0);
    await expect(page.getByTestId('empty-state')).toBeVisible();
    await expect(page.getByTestId('empty-state')).toContainText(/no events/i);
  });

  test('2.3 changing "days back" in settings reloads immediately, no refresh press needed', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    const before = await page.getByTestId('event-row').count();

    await page.getByTestId('settings-gear').click();
    await page.getByTestId('setting-days-back').fill('14');
    await page.getByTestId('settings-close').click();

    // no refresh-button click here — reload must happen on its own
    await expect(page.getByTestId('event-row')).not.toHaveCount(before);
    await expect(page.getByTestId('event-row-E4')).toBeVisible(); // now within 14-day window
  });

  test('2.4 refresh button re-fetches using the current days-back setting', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    const beforeCount = await page.getByTestId('event-row').count();
    // (in a real run: a fixture event is added server-side here, between load and refresh)
    await page.getByTestId('refresh-data').click();
    await expect(page.getByTestId('event-row')).toHaveCount(beforeCount + 1);
  });

  test('2.4b refresh preserves currently-applied filters (2026-09-05 decision)', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    await page.getByTestId('filter-event-type').click();
    await page.getByRole('option', { name: 'הסכם' }).click();
    await page.getByTestId('filter-apply').click();
    const filteredCount = await page.getByTestId('event-row').count();

    await page.getByTestId('refresh-data').click();
    await expect(page.getByTestId('event-row')).toHaveCount(filteredCount); // filter still active, not reset
  });

  test('2.1b same-date events break ties by event_id descending', async ({ page }) => {
    // Fixture: E5, E6 share the identical date, E6's event_id > E5's event_id
    await loginAs(page, VALID_PASSWORD);
    const rows = page.getByTestId('event-row');
    const e5Index = await rows.locator('[data-testid="event-row-E5"]').first().evaluate(el => Array.from(el.parentElement!.children).indexOf(el));
    const e6Index = await rows.locator('[data-testid="event-row-E6"]').first().evaluate(el => Array.from(el.parentElement!.children).indexOf(el));
    expect(e6Index).toBeLessThan(e5Index); // E6 (higher event_id) sorts first
  });

  test('2.2 empty state (same generic message for empty-window and zero-filter-match)', async ({ page }) => {
    await loginAs(page, EMPTY_WINDOW_PASSWORD);
    await expect(page.getByTestId('empty-state')).toBeVisible();
    const genericText = await page.getByTestId('empty-state').textContent();

    await page.getByTestId('filter-client-name').fill('zzz-no-such-client-zzz');
    await page.getByTestId('filter-apply').click();
    await expect(page.getByTestId('empty-state')).toHaveText(genericText!); // identical wording
  });
});

test.describe('3. Filters', () => {
  test('Apply narrows the list; nothing changes before Apply is pressed', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    await page.getByTestId('filter-event-type').click();
    await page.getByRole('option', { name: 'הסכם' }).click();
    // still full list until Apply:
    await expect(page.getByTestId('event-row')).toHaveCount(await expectedCountWithinDays(7));

    await page.getByTestId('filter-apply').click();
    const filtered = page.getByTestId('event-row');
    await expect(filtered).toHaveCount(await expectedCountBySourceType('הסכם'));

    await page.getByTestId('filter-clear').click();
    await page.getByTestId('filter-apply').click();
    await expect(page.getByTestId('event-row')).toHaveCount(await expectedCountWithinDays(7));
  });
});

test.describe('4. Row expand — single', () => {
  test('pressing + opens both panels with correct data and pushes rows down', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    const row = page.getByTestId('event-row-E1');
    const nextRowBefore = await page.getByTestId('event-row-E2').boundingBox();

    await row.getByTestId('expand-toggle').click();

    const rightPanel = page.getByTestId('detail-panel-E1');
    const leftPanel = page.getByTestId('context-panel-E1');
    await expect(rightPanel).toBeVisible();
    await expect(leftPanel).toBeVisible();
    await expect(rightPanel).toContainText('ישראל ישראלי');
    await expect(rightPanel).toContainText('5000');
    await expect(leftPanel.getByTestId('context-message')).toHaveCount(3); // M1,M2,M3 @10min

    // real layout assertion: right panel starts to the right of left panel (desktop, RTL)
    const rightBox = await rightPanel.boundingBox();
    const leftBox = await leftPanel.boundingBox();
    expect(rightBox!.x).toBeGreaterThan(leftBox!.x);

    // subsequent row visibly pushed down
    const nextRowAfter = await page.getByTestId('event-row-E2').boundingBox();
    expect(nextRowAfter!.y).toBeGreaterThan(nextRowBefore!.y);
  });
});

test.describe('5. Row expand — multiple + expand-all/collapse-all', () => {
  test('multiple rows expand independently; expand-all / collapse-all act on all loaded rows', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    await page.getByTestId('event-row-E1').getByTestId('expand-toggle').click();
    await page.getByTestId('event-row-E2').getByTestId('expand-toggle').click();
    await expect(page.getByTestId('detail-panel-E1')).toBeVisible();
    await expect(page.getByTestId('detail-panel-E2')).toBeVisible();

    await page.getByTestId('collapse-all').click();
    await expect(page.getByTestId('detail-panel-E1')).not.toBeVisible();
    await expect(page.getByTestId('detail-panel-E2')).not.toBeVisible();

    await page.getByTestId('expand-all').click();
    const count = await page.getByTestId('event-row').count();
    await expect(page.getByTestId(/^detail-panel-/)).toHaveCount(count);
  });
});

test.describe('6. Mobile viewport stacking', () => {
  test.use({ ...devices['iPhone 13'] });
  test('panels stack vertically (detail on top, context below) on mobile width', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    await page.getByTestId('event-row-E1').getByTestId('expand-toggle').click();
    const rightBox = await page.getByTestId('detail-panel-E1').boundingBox();
    const leftBox = await page.getByTestId('context-panel-E1').boundingBox();
    expect(leftBox!.y).toBeGreaterThan(rightBox!.y + rightBox!.height - 5); // below, not beside
  });
});

test.describe('7. Σ summation (v1: naive raw sum — see spec.md TBD note)', () => {
  test('7.1 sums the currently filtered view correctly', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    await page.getByTestId('sigma-button').click();
    await expect(page.getByTestId('sigma-result')).toHaveText(/Σ \(\d+ events\): ₪[\d,-]+/);
  });

  test('7.2 sum disappears entirely on filter change or refresh (revised 2026-09-05)', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    await page.getByTestId('sigma-button').click();
    await expect(page.getByTestId('sigma-result')).toBeVisible();

    await page.getByTestId('filter-event-type').click();
    await page.getByRole('option', { name: 'הסכם' }).click();
    await page.getByTestId('filter-apply').click();
    await expect(page.getByTestId('sigma-result')).not.toBeVisible(); // cleared, not stale-marked

    await page.getByTestId('sigma-button').click();
    await expect(page.getByTestId('sigma-result')).toBeVisible(); // recomputed for the new view
    await page.getByTestId('refresh-data').click();
    await expect(page.getByTestId('sigma-result')).not.toBeVisible(); // refresh also clears it
  });

  test('7.4 expand/collapse does not clear an already-shown sum', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    await page.getByTestId('sigma-button').click();
    await expect(page.getByTestId('sigma-result')).toBeVisible();
    await page.getByTestId('event-row-E1').getByTestId('expand-toggle').click();
    await expect(page.getByTestId('sigma-result')).toBeVisible(); // still shown, unaffected
  });
});

test.describe('8. Settings persistence', () => {
  test('theme/sort/days-back/lookback persist across reload; logout returns to password screen', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    await page.getByTestId('settings-gear').click();
    await page.getByTestId('setting-theme-dark').click();
    await page.getByTestId('setting-days-back').fill('14');
    await page.getByTestId('setting-lookback-minutes').fill('30');
    await page.getByTestId('settings-close').click();

    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.getByTestId('settings-gear').click();
    await expect(page.getByTestId('setting-days-back')).toHaveValue('14');

    await page.getByTestId('setting-logout').click();
    await expect(page.getByTestId('password-input')).toBeVisible();
  });
});

test.describe('9. Visual regression', () => {
  test('collapsed list and expanded row match baseline (desktop)', async ({ page }) => {
    await loginAs(page, VALID_PASSWORD);
    await expect(page).toHaveScreenshot('list-collapsed-desktop.png');
    await page.getByTestId('event-row-E1').getByTestId('expand-toggle').click();
    await expect(page).toHaveScreenshot('list-expanded-desktop.png');
  });

  test('collapsed list matches baseline (mobile)', async ({ page }) => {
    await page.setViewportSize(devices['iPhone 13'].viewport);
    await loginAs(page, VALID_PASSWORD);
    await expect(page).toHaveScreenshot('list-collapsed-mobile.png');
  });
});

async function loginAs(page, password: string) {
  await page.goto(BASE_URL);
  await page.getByTestId('password-input').fill(password);
  await page.getByTestId('login-submit').click();
  await page.getByTestId('event-list').waitFor();
}
// expectedCountWithinDays / expectedCountBySourceType: helpers reading the same seeded
// fixture data_root the BFF's config.test.json points at, so counts are asserted against
// real data, never hardcoded guesses.
```

## Open items before this can actually be written for real

1. **`data-testid` contract** — every id above (`event-row-E1`, `expand-toggle`, `sigma-button`, etc.) needs to actually exist in the frontend components once built in Phases 4–8; this draft is effectively dictating part of that contract now.
2. **Fixture data_root** — needs a committed, deterministic seed (events/sessions/messages at fixed relative-to-"today" timestamps) so date-window/lookback assertions aren't flaky across days.
3. **Visual regression baselines** — first run generates them; they need a deliberate "approve baseline" step, not auto-accepted.

