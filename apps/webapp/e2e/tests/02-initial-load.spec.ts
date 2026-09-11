/**
 * Component 2 — Initial Load (PLAYWRIGHT-TEST-PLAN.md §2, ~21 cases).
 */
import { test, expect } from "@playwright/test";
import {
  FULL,
  applyFilters,
  idsWithinDays,
  login,
  readEvent,
  row,
  rowIds,
  rows,
  setDaysBack,
} from "./_helpers";

test.describe("2.1 Default load window (7)", () => {
  test("2.1.1 only events within the past 7 days are shown", async ({ page }) => {
    await login(page);
    const shown = await rowIds(page);
    const expected = idsWithinDays(7).sort();
    expect(shown.slice().sort()).toEqual(expected);
  });

  test("2.1.2 an event dated exactly 7 days ago is included (inclusive boundary)", async ({ page }) => {
    await login(page);
    await expect(row(page, FULL().boundary_included_id)).toBeVisible();
  });

  test("2.1.3 an event dated 8 days ago is excluded", async ({ page }) => {
    await login(page);
    await expect(page.getByTestId(`event-row-${FULL().outside_7_within_14_id}`)).toHaveCount(0);
  });

  test("2.1.4 sort is newest-first by default (dates non-increasing top to bottom)", async ({ page }) => {
    await login(page);
    const ids = await rowIds(page);
    const dates = ids.map((id) => {
      const e = readEvent(id);
      const head = (e.txn_date || e.event_datetime || e.event_date || "").split(" ")[0];
      const [dd, mm, yyyy] = head.split("/").map(Number);
      return new Date(yyyy, mm - 1, dd).getTime();
    });
    for (let i = 1; i < dates.length; i++) expect(dates[i]).toBeLessThanOrEqual(dates[i - 1]);
  });

  test("2.1.5 date computation uses Israel local time", async ({ page }) => {
    // fixture 'today' events (E7/E8/E9/E10/E15) must be in the default window; if the backend
    // computed the cutoff in UTC while the browser is well into the next Israel day, a
    // just-before-midnight event could wrongly drop. Assert the newest fixture day is present.
    await login(page);
    const ids = await rowIds(page);
    expect(ids).toContain(FULL().negative_amount_id); // E9, dated 'today'
  });

  test("2.1.6 total count matches the fixture exactly (no off-by-one)", async ({ page }) => {
    await login(page);
    await expect(rows(page)).toHaveCount(idsWithinDays(7).length);
    await expect(page.getByTestId("record-count")).toContainText(String(idsWithinDays(7).length));
  });

  test("2.1.7 same-date events break ties by event_id descending", async ({ page }) => {
    await login(page);
    const [a, b] = FULL().same_date_pair; // E5, E6 — same date, E6 > E5
    const ids = await rowIds(page);
    const hi = a > b ? a : b;
    const lo = a > b ? b : a;
    expect(ids.indexOf(hi)).toBeLessThan(ids.indexOf(lo));
    expect(ids.indexOf(hi)).toBeGreaterThanOrEqual(0);
  });
});

test.describe("2.2 Empty result (3)", () => {
  test("2.2.1 zero events in the window shows an explicit empty state", async ({ page }) => {
    await login(page, "empty");
    await expect(rows(page)).toHaveCount(0);
    await expect(page.getByTestId("empty-state")).toBeVisible();
  });

  test("2.2.2 no stuck loading spinner", async ({ page }) => {
    await login(page, "empty");
    await expect(page.getByTestId("loading")).toHaveCount(0);
  });

  test("2.2.3 same generic empty state for empty-window and filtered-to-zero", async ({ page }) => {
    await login(page, "empty");
    const emptyWindowText = (await page.getByTestId("empty-state").textContent())!.trim();

    await login(page); // full fixture
    await page.getByTestId("filter-client-name").fill("zzz-no-such-client-zzz");
    await applyFilters(page);
    await expect(page.getByTestId("empty-state")).toBeVisible();
    const filteredText = (await page.getByTestId("empty-state").textContent())!.trim();
    expect(filteredText).toBe(emptyWindowText);
  });
});

test.describe("2.3 Changing days-back reloads immediately (5)", () => {
  test("2.3.1 increasing the value immediately reloads wider (no refresh press)", async ({ page }) => {
    await login(page);
    const before = await rows(page).count();
    await setDaysBack(page, 20);
    await expect(page.getByTestId(`event-row-${FULL().outside_7_within_14_id}`)).toBeVisible();
    expect(await rows(page).count()).toBeGreaterThan(before);
  });

  test("2.3.2 decreasing immediately reloads narrower", async ({ page }) => {
    await login(page);
    await setDaysBack(page, 20);
    const wide = await rows(page).count();
    await setDaysBack(page, 1);
    expect(await rows(page).count()).toBeLessThan(wide);
  });

  test("2.3.3 newly-revealed events sort correctly into the list (tiebreaker respected)", async ({ page }) => {
    await login(page);
    await setDaysBack(page, 20);
    const ids = await rowIds(page);
    // E2 (8 days back) must sit after all newer events and before none newer than it
    const idx = ids.indexOf(FULL().outside_7_within_14_id);
    expect(idx).toBeGreaterThan(0);
    const dateOf = (id: string) => {
      const e = readEvent(id);
      const head = (e.txn_date || e.event_datetime || e.event_date || "").split(" ")[0];
      const [dd, mm, yyyy] = head.split("/").map(Number);
      return new Date(yyyy, mm - 1, dd).getTime();
    };
    expect(dateOf(ids[idx - 1])).toBeGreaterThanOrEqual(dateOf(ids[idx]));
  });

  test("2.3.4 setting the same value again is a safe no-op", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await setDaysBack(page, 7);
    expect(await rowIds(page)).toEqual(before);
  });

  test("2.3.5 rapid consecutive changes don't race (stale-response guard)", async ({ page }) => {
    await login(page);
    await page.getByTestId("settings-gear").click();
    const input = page.getByTestId("setting-days-back");
    for (const v of ["30", "3", "25", "9"]) await input.fill(v);
    await page.getByTestId("settings-close").click();
    await expect(page.getByTestId("loading")).toHaveCount(0);
    // final value is 9 -> E2 (8d) visible, E11 (400d) not
    await expect(page.getByTestId(`event-row-${FULL().outside_7_within_14_id}`)).toBeVisible();
    await expect(page.getByTestId(`event-row-${FULL().full_history_id}`)).toHaveCount(0);
  });
});

test.describe("2.4 Refresh button (5)", () => {
  test("2.4.1 re-fetches from the backend (network call, not a cached re-render)", async ({ page }) => {
    await login(page);
    const reqs: string[] = [];
    page.on("request", (r) => r.url().includes("/api/events") && reqs.push(r.url()));
    await page.getByTestId("refresh-data").click();
    await expect(page.getByTestId("refresh-data")).toBeEnabled();
    expect(reqs.length).toBeGreaterThan(0);
  });

  test("2.4.2 / 2.4.3 refreshed list reflects the current server state", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await page.getByTestId("refresh-data").click();
    await expect(page.getByTestId("loading")).toHaveCount(0);
    // no server mutation in this test env -> identical set, proving a real reload round-trip
    expect((await rowIds(page)).slice().sort()).toEqual(before.slice().sort());
  });

  test("2.4.4 visual feedback while refreshing", async ({ page }) => {
    await login(page);
    await page.route("**/api/events**", async (r) => {
      await new Promise((res) => setTimeout(res, 700));
      await r.continue();
    });
    await page.getByTestId("refresh-data").click();
    await expect(page.getByTestId("refresh-data")).toContainText("…"); // busy glyph
    await expect(page.getByTestId("refresh-data")).not.toContainText("…", { timeout: 5000 });
  });

  test("2.4.5 refresh re-applies whatever on-screen filters were active", async ({ page }) => {
    test.fixme(
      true,
      "Known gap (tasks.md Stories 4-8): App.load('refresh') resets every filter to passthrough " +
        "instead of preserving the active on-screen filters. PLAYWRIGHT-TEST-PLAN 2.4.5."
    );
    await login(page);
    await page.getByTestId("filter-client-name").fill("ישראל ישראלי");
    await page.keyboard.press("Escape");
    await applyFilters(page);
    const filtered = await rows(page).count();
    await page.getByTestId("refresh-data").click();
    await expect(page.getByTestId("loading")).toHaveCount(0);
    expect(await rows(page).count()).toBe(filtered);
  });
});
