/**
 * Component 8 — Settings. PLAYWRIGHT-TEST-PLAN.md §8.
 * theme / sort order / days-back / lookback-minutes, persisted in localStorage (except sort,
 * which is deliberately session-only — same transient-view-state rule as Component 5.6).
 */
import { test, expect, Page } from "@playwright/test";
import { login, openSettings, rowIds, row, gotoApp } from "./_helpers";

async function closeSettings(page: Page) {
  await page.getByTestId("settings-close").click();
  await expect(page.getByTestId("settings-panel")).toHaveCount(0);
}
async function setNum(page: Page, testid: string, value: string) {
  await openSettings(page);
  await page.getByTestId(testid).fill(value);
  await page.getByTestId(testid).blur();
  await closeSettings(page);
}
const theme = (page: Page) => page.locator("html").getAttribute("data-theme");

test.describe("8.1 Theme switching (5)", () => {
  test("8.1.1 dark theme changes colors app-wide", async ({ page }) => {
    await login(page);
    expect(await theme(page)).toBe("light");
    const before = await page.getByTestId("app-ready").evaluate((el) => getComputedStyle(el).backgroundColor);
    await openSettings(page);
    await page.getByTestId("setting-theme").click();
    await closeSettings(page);
    expect(await theme(page)).toBe("dark");
    const after = await page.getByTestId("app-ready").evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(after).not.toBe(before);
  });

  test("8.1.2 switching back restores light app-wide", async ({ page }) => {
    await login(page);
    await openSettings(page);
    await page.getByTestId("setting-theme").click(); // dark
    await page.getByTestId("setting-theme").click(); // back to light
    await closeSettings(page);
    expect(await theme(page)).toBe("light");
  });

  test("8.1.3 applies immediately, no reload", async ({ page }) => {
    await login(page);
    let navigated = false;
    page.on("framenavigated", () => (navigated = true));
    await openSettings(page);
    await page.getByTestId("setting-theme").click();
    expect(await theme(page)).toBe("dark");
    expect(navigated).toBe(false);
  });

  test("8.1.4 an open expanded row's panels also restyle correctly", async ({ page }) => {
    await login(page);
    await page.getByTestId("expand-toggle-E1").click();
    await expect(page.getByTestId("detail-panel-E1")).toBeVisible();
    const bg = (loc: string) => page.getByTestId(loc).first().evaluate((el) => getComputedStyle(el).backgroundColor);
    const before = await bg("event-row-E1");
    await openSettings(page);
    await page.getByTestId("setting-theme").click();
    await closeSettings(page);
    await expect(page.getByTestId("detail-panel-E1")).toBeVisible(); // still expanded after restyle
    expect(await bg("event-row-E1")).not.toBe(before);
  });

  test("8.1.5 first-visit with OS set to dark still loads in light", async ({ browser }) => {
    const ctx = await browser.newContext({ colorScheme: "dark" });
    const page = await ctx.newPage();
    await login(page);
    expect(await theme(page)).toBe("light");
    await ctx.close();
  });
});

test.describe("8.2 Sort order toggle (4)", () => {
  test("8.2.1 oldest-first re-sorts immediately", async ({ page }) => {
    await login(page);
    const desc = await rowIds(page);
    await page.getByTestId("sort-toggle").click();
    const asc = await rowIds(page);
    expect(asc).toEqual([...desc].reverse());
  });

  test("8.2.2 newest-first restores the original order", async ({ page }) => {
    await login(page);
    const original = await rowIds(page);
    await page.getByTestId("sort-toggle").click();
    await page.getByTestId("sort-toggle").click();
    expect(await rowIds(page)).toEqual(original);
  });

  test("8.2.3 the same-date tiebreaker flips direction to match", async ({ page }) => {
    await login(page);
    // E5 & E6 share a date; default desc => E6 before E5
    let ids = await rowIds(page);
    expect(ids.indexOf("E6")).toBeLessThan(ids.indexOf("E5"));
    await page.getByTestId("sort-toggle").click(); // asc => E5 before E6
    ids = await rowIds(page);
    expect(ids.indexOf("E5")).toBeLessThan(ids.indexOf("E6"));
  });

  test("8.2.4 the change is a client-side re-sort, no new backend load", async ({ page }) => {
    await login(page);
    const calls: string[] = [];
    page.on("request", (r) => r.url().includes("/api/events") && calls.push(r.url()));
    await page.getByTestId("sort-toggle").click();
    await page.waitForTimeout(300);
    expect(calls).toHaveLength(0);
  });

  test("8.2.5 sort is session-only — a reload returns to the default newest-first", async ({ page }) => {
    await login(page);
    await page.getByTestId("sort-toggle").click(); // asc
    await page.reload();
    await expect(page.getByTestId("app-ready")).toBeVisible();
    const ids = await rowIds(page);
    expect(ids.indexOf("E6")).toBeLessThan(ids.indexOf("E5")); // back to desc default
  });
});

test.describe("8.3 Days-back validation (4, no max) (4)", () => {
  test("8.3.1 a valid value reloads immediately and persists", async ({ page }) => {
    await login(page);
    await setNum(page, "setting-days-back", "14");
    await expect(row(page, "E2")).toBeVisible(); // E2 is 8 days back — only visible at >=8
    await page.reload();
    await expect(page.getByTestId("app-ready")).toBeVisible();
    await expect(row(page, "E2")).toBeVisible();
  });

  test("8.3.2 zero / negative input is rejected / clamped", async ({ page }) => {
    await login(page);
    await setNum(page, "setting-days-back", "0");
    await openSettings(page);
    expect(Number(await page.getByTestId("setting-days-back").inputValue())).toBeGreaterThanOrEqual(1);
    await closeSettings(page);
  });

  test("8.3.3 non-numeric input is rejected (never applied, never reloads)", async ({ page }) => {
    await login(page);
    const idsBefore = await rowIds(page);
    const calls: string[] = [];
    page.on("request", (r) => r.url().includes("/api/events") && calls.push(r.url()));
    await openSettings(page);
    await page.getByTestId("setting-days-back").fill("abc");
    await closeSettings(page);
    // garbage never took effect: same window, no reload
    expect(await rowIds(page)).toEqual(idsBefore);
    expect(calls).toHaveLength(0);
    // and the authoritative value is what shows on reopen
    await openSettings(page);
    await expect(page.getByTestId("setting-days-back")).toHaveValue("7");
  });

  test("8.3.4 clearing the field falls back to a defined default", async ({ page }) => {
    await login(page);
    const idsBefore = await rowIds(page);
    await openSettings(page);
    await page.getByTestId("setting-days-back").fill("");
    await closeSettings(page);
    expect(await rowIds(page)).toEqual(idsBefore); // still the default 7-day window
    await openSettings(page);
    await expect(page.getByTestId("setting-days-back")).toHaveValue("7");
  });
});

test.describe("8.4 Lookback-minutes validation (5)", () => {
  test("8.4.1 a valid value (0–60) takes effect on the next expansion", async ({ page }) => {
    await login(page);
    await setNum(page, "setting-lookback", "5");
    await page.getByTestId("expand-toggle-E1").click();
    await expect(page.getByTestId("context-panel-E1")).toBeVisible();
    const ids = await page
      .getByTestId("context-panel-E1")
      .getByTestId(/^chat-msg-/)
      .evaluateAll((els) => els.map((e) => (e.getAttribute("aria-label") || "").match(/id:(\S+)/)?.[1]));
    expect(ids.sort()).toEqual(["M2", "M3", "M4"]); // lookback_5 window
  });

  test("8.4.2 above-60 is clamped / rejected client-side", async ({ page }) => {
    await login(page);
    await setNum(page, "setting-lookback", "999");
    await openSettings(page);
    expect(Number(await page.getByTestId("setting-lookback").inputValue())).toBeLessThanOrEqual(60);
    await closeSettings(page);
  });

  test("8.4.3 negative is rejected", async ({ page }) => {
    await login(page);
    await setNum(page, "setting-lookback", "-5");
    await openSettings(page);
    expect(Number(await page.getByTestId("setting-lookback").inputValue())).toBeGreaterThanOrEqual(0);
    await closeSettings(page);
  });

  test("8.4.4 non-numeric is rejected (never applied)", async ({ page }) => {
    await login(page);
    await openSettings(page);
    await page.getByTestId("setting-lookback").fill("xx");
    await closeSettings(page);
    await openSettings(page);
    await expect(page.getByTestId("setting-lookback")).toHaveValue("10"); // authoritative value on reopen
  });

  test("8.4.5 the backend independently clamps to [0,60] regardless", async ({ page }) => {
    await login(page);
    // force an over-limit lookback straight onto the API and confirm the server bounds it
    await page.evaluate(() => localStorage.setItem("denidin_ledger_settings", JSON.stringify({ theme: "light", daysBack: 7, lookback: 500 })));
    await page.reload();
    await expect(page.getByTestId("app-ready")).toBeVisible();
    const [r] = await Promise.all([
      page.waitForResponse((x) => x.url().includes("/context")),
      page.getByTestId("expand-toggle-E1").click(),
    ]);
    const body = await r.json();
    expect(body.lookback_minutes_used).toBeLessThanOrEqual(60);
  });
});

test.describe("8.5 Persistence (2)", () => {
  test("8.5.1 theme + days-back + lookback preserved exactly after reload", async ({ page }) => {
    await login(page);
    await openSettings(page);
    await page.getByTestId("setting-theme").click(); // dark
    await page.getByTestId("setting-days-back").fill("10");
    await page.getByTestId("setting-lookback").fill("30");
    await closeSettings(page);
    await page.reload();
    await expect(page.getByTestId("app-ready")).toBeVisible();
    expect(await theme(page)).toBe("dark");
    await openSettings(page);
    expect(await page.getByTestId("setting-days-back").inputValue()).toBe("10");
    expect(await page.getByTestId("setting-lookback").inputValue()).toBe("30");
  });

  test("8.5.2 settings persist across a fresh page (tab/browser close proxy)", async ({ page, context }) => {
    await login(page);
    await openSettings(page);
    await page.getByTestId("setting-theme").click();
    await closeSettings(page);
    const p2 = await context.newPage();
    await gotoApp(p2, "full"); // same context => token already present, lands straight in the app
    await expect(p2.getByTestId("app-ready")).toBeVisible();
    expect(await p2.locator("html").getAttribute("data-theme")).toBe("dark");
  });
});

test.describe("8.6 Settings panel open/close (3)", () => {
  test("8.6.1 opening shows current values pre-filled", async ({ page }) => {
    await login(page);
    await openSettings(page);
    expect(await page.getByTestId("setting-days-back").inputValue()).toBe("7");
    expect(await page.getByTestId("setting-lookback").inputValue()).toBe("10");
  });

  test("8.6.2 closing without changes leaves everything unchanged", async ({ page }) => {
    await login(page);
    const ids = await rowIds(page);
    await openSettings(page);
    await closeSettings(page);
    expect(await rowIds(page)).toEqual(ids);
    expect(await theme(page)).toBe("light");
  });

  test("8.6.3 reopening shows consistent values; backdrop click also closes", async ({ page }) => {
    await login(page);
    await openSettings(page);
    await page.getByTestId("settings-backdrop").click({ position: { x: 5, y: 5 } });
    await expect(page.getByTestId("settings-panel")).toHaveCount(0);
    await openSettings(page);
    expect(await page.getByTestId("setting-days-back").inputValue()).toBe("7");
  });
});

test.describe("8.7 Logout reachable from settings (1)", () => {
  test("8.7.1 the logout control triggers the flow (back to the password screen)", async ({ page }) => {
    await login(page);
    await openSettings(page);
    await page.getByTestId("setting-logout").click();
    await expect(page.getByTestId("password-input")).toBeVisible();
    await expect(page.getByTestId("app-ready")).toHaveCount(0);
  });
});
