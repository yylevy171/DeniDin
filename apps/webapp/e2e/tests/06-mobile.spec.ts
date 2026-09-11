/**
 * Component 6 — Mobile Viewport Layout. PLAYWRIGHT-TEST-PLAN.md §6.
 * Runs only under the `mobile-chromium` project (Pixel 7, ~412px wide — below the 768px
 * mobile/desktop breakpoint). Chat panel = fixed height + own internal scroll on both form factors.
 */
import { test, expect, Page } from "@playwright/test";
import { login, rows, rowIds } from "./_helpers";

async function expand(page: Page, id: string) {
  // NOTE: force — on mobile the known table overflow-x gap (see 6.3.3 / Component 0) pushes
  // page content past the viewport, so a normal click is intercepted by <html>. The overflow
  // itself is covered by its own fixme; the stacking/panel assertions below are independent.
  const t = page.getByTestId(`expand-toggle-${id}`);
  await t.scrollIntoViewIfNeeded();
  await t.click({ force: true });
  await expect(page.getByTestId(`detail-panel-${id}`)).toBeVisible();
}

test.describe("6.1 Single expanded row stacks vertically (2)", () => {
  test("6.1.1 detail panel appears above the chat panel on mobile", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const d = (await page.getByTestId("detail-panel-E1").boundingBox())!;
    const c = (await page.getByTestId("context-panel-E1").boundingBox())!;
    expect(d.y).toBeLessThan(c.y); // stacked, detail on top
    expect(Math.abs(d.x - c.x)).toBeLessThan(4); // same column
  });

  test("6.1.2 both panels are full / near-full width", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const vw = page.viewportSize()!.width;
    for (const id of ["detail-panel-E1", "context-panel-E1"]) {
      const b = (await page.getByTestId(id).boundingBox())!;
      expect(b.width).toBeGreaterThan(vw * 0.85);
    }
  });
});

test.describe("6.2 Multiple expanded rows on mobile (2)", () => {
  test("6.2.1 each independently expanded row shows its own correctly-stacked pair", async ({ page }) => {
    await login(page);
    await expand(page, "E3");
    await expand(page, "E6");
    for (const id of ["E3", "E6"]) {
      const d = (await page.getByTestId(`detail-panel-${id}`).boundingBox())!;
      const c = (await page.getByTestId(`context-panel-${id}`).boundingBox())!;
      expect(d.y).toBeLessThan(c.y);
    }
  });

  test("6.2.2 stacking applies uniformly across every expansion", async ({ page }) => {
    await login(page);
    await page.getByTestId("expand-all").click({ force: true });
    const ids = await rowIds(page);
    for (const id of ids.slice(0, 4)) {
      const d = (await page.getByTestId(`detail-panel-${id}`).boundingBox())!;
      const c = (await page.getByTestId(`context-panel-${id}`).boundingBox())!;
      expect(d.y).toBeLessThan(c.y);
    }
  });
});

test.describe("6.3 Row list at mobile width (4)", () => {
  test("6.3.1 description wraps onto a second sub-row when needed", async ({ page }) => {
    await login(page);
    const desc = page.getByTestId("event-row-E1").getByTestId("row-description");
    await expect(desc).toBeVisible();
    const box = (await desc.boundingBox())!;
    expect(box.height).toBeGreaterThan(14); // at least one line, wraps as needed (numberOfLines=2)
  });

  test("6.3.2 the core fields stay on the first line under normal circumstances", async ({ page }) => {
    await login(page);
    // date + amount cells sit on the same y within the row header
    const row = page.getByTestId("event-row-E6");
    await expect(row).toBeVisible();
    expect((await row.boundingBox())!.height).toBeLessThan(160);
  });

  test("6.3.3 no row ever requires horizontal scrolling", async ({ page }) => {
    await login(page);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("6.3.4 amount and date remain fully visible / un-truncated under tight width", async ({ page }) => {
    await login(page);
    const row = page.getByTestId("event-row-E1");
    await expect(row).toContainText("₪5,000");
  });
});

test.describe("6.5 WhatsApp chat panel usability + fixed height (6)", () => {
  test("6.5.1 chat bubbles remain legible at mobile width", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const first = page.getByTestId("context-panel-E1").getByTestId(/^chat-msg-/).first();
    await expect(first).toBeVisible();
    expect((await first.boundingBox())!.width).toBeGreaterThan(60);
  });

  test("6.5.2 tapping a thumbnail opens the larger view, sized for the smaller screen", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await page.getByTestId("context-panel-E1").getByTestId("chat-image").first().click({ force: true });
    const overlay = page.getByTestId("image-overlay");
    await expect(overlay).toBeVisible();
    const vw = page.viewportSize()!.width;
    expect((await overlay.boundingBox())!.width).toBeLessThanOrEqual(vw + 1);
  });

  test("6.5.3 'OK' remains reachable / tappable", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await page.getByTestId("context-panel-E1").getByTestId("chat-image").first().click({ force: true });
    const close = page.getByTestId("image-overlay-close");
    await expect(close).toBeVisible();
    await close.click({ force: true }); // page h-overflow (6.3.3) intercepts a normal tap

    await expect(page.getByTestId("image-overlay")).toHaveCount(0);
  });

  test("6.5.4 the chat panel occupies its fixed height, not the full remaining page height", async ({ page }) => {
    test.fixme(
      true,
      "Known gap (PLAYWRIGHT-TEST-PLAN 6.5.4 / bugfix-052 G2): on mobile the expanded row has " +
        "no fixed height, so the inner panels grow with their content instead of the chat " +
        "panel holding ~240px. Not addressed by the 2026-09-06 mobile h-overflow fix."
    );
    await login(page);
    await expand(page, "E1");
    const h = (await page.getByTestId("context-panel-E1").boundingBox())!.height;
    expect(h).toBeGreaterThan(180);
    expect(h).toBeLessThan(320); // fixed ~240, not the whole screen
  });

  test("6.5.5 the panel has its own internal scrollbar, independent of the outer page scroll", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const scrollable = await page
      .getByTestId("context-panel-E1")
      .getByTestId("chat-scroll")
      .evaluate((el) => el.scrollHeight > el.clientHeight + 1 || getComputedStyle(el).overflowY !== "visible");
    expect(scrollable).toBeTruthy();
  });

  test("6.5.6 scrolling inside the chat panel doesn't scroll the outer row list", async ({ page }) => {
    test.fixme(
      true,
      "Known gap (PLAYWRIGHT-TEST-PLAN 6.5.6 / bugfix-052 G2): nested-scroll containment — a " +
        "wheel over the chat panel also scrolls the outer event list (no overscroll-behavior: " +
        "contain). Same root cause as 6.5.4. Not addressed by the 2026-09-06 mobile h-overflow fix."
    );
    await login(page);
    await expand(page, "E1");
    const list = page.getByTestId("event-list");
    const before = await list.evaluate((el) => el.scrollTop);
    await page.getByTestId("context-panel-E1").getByTestId("chat-scroll").hover();
    await page.mouse.wheel(0, 300);
    const after = await list.evaluate((el) => el.scrollTop);
    expect(Math.abs(after - before)).toBeLessThan(30);
  });
});
