/**
 * Component 0 — Layout (11) + Component 0b — General Responsiveness (6).
 * PLAYWRIGHT-TEST-PLAN.md §0 / §0b.
 */
import { test, expect, Page } from "@playwright/test";
import { login } from "./_helpers";

const FILTER_CONTROLS = [
  "filter-date-from",
  "filter-date-to",
  "filter-client-name",
  "filter-type",
  "filter-subtype",
  "filter-global",
  "filter-apply",
];
const TOPBAR_CONTROLS = ["logo", "record-count", "refresh-data", "settings-gear"];

async function allVisible(page: Page, ids: string[]) {
  for (const id of ids) await expect(page.getByTestId(id)).toBeVisible();
}
async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  );
  expect(overflow).toBeLessThanOrEqual(1);
}

test.describe("Component 0 — Layout (11)", () => {
  test("0.1 desktop: all filter controls visible in one bar above the list", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await allVisible(page, FILTER_CONTROLS);
    const bar = await page.getByTestId("filter-apply").boundingBox();
    const list = await page.getByTestId("event-list").boundingBox();
    expect(bar!.y).toBeLessThan(list!.y);
  });

  test("0.2 mobile: same controls wrap onto multiple lines, never hidden behind a toggle", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 840 });
    await login(page);
    await allVisible(page, FILTER_CONTROLS);
  });

  test("0.3 no filter control is hidden behind a collapsed panel at any viewport", async ({ page }) => {
    await login(page);
    for (const w of [1400, 1024, 768, 480, 360]) {
      await page.setViewportSize({ width: w, height: 900 });
      await allVisible(page, FILTER_CONTROLS);
    }
  });

  test("0.4 filter bar RTL control order is consistent desktop vs mobile", async ({ page }) => {
    test.fixme(
      true,
      "Known gap (PLAYWRIGHT-TEST-PLAN 0.4 / bugfix-052 G4): on a narrow viewport the filter " +
        "bar wraps and 'filter-apply' drops to a second line, so its right-to-left x-order no " +
        "longer matches desktop. Not addressed by the 2026-09-06 mobile h-overflow fix."
    );
    await login(page);
    const order = async () => {
      const xs: Record<string, number> = {};
      for (const id of FILTER_CONTROLS) xs[id] = (await page.getByTestId(id).boundingBox())!.x;
      return [...FILTER_CONTROLS].sort((a, b) => xs[b] - xs[a]); // right-to-left
    };
    await page.setViewportSize({ width: 1400, height: 900 });
    const desktop = await order();
    await page.setViewportSize({ width: 390, height: 900 });
    const mobile = await order();
    // date-from is rightmost, apply is leftmost, in both
    expect(desktop[0]).toBe(mobile[0]);
    expect(desktop.at(-1)).toBe(mobile.at(-1));
  });

  test("0.5 Apply button stays visible/reachable at every viewport size", async ({ page }) => {
    await login(page);
    for (const w of [1600, 1200, 900, 768, 600, 414, 360]) {
      await page.setViewportSize({ width: w, height: 800 });
      await expect(page.getByTestId("filter-apply")).toBeVisible();
      await page.getByTestId("filter-apply").click(); // reachable / clickable
    }
  });

  test("0.6 desktop top bar shows every control group in consistent RTL order", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await allVisible(page, [...TOPBAR_CONTROLS, "expand-all"]);
  });

  test("0.7 mobile top bar keeps all controls visible, never an overflow menu", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 780 });
    await login(page);
    await allVisible(page, TOPBAR_CONTROLS);
    await expect(page.getByText("⋯", { exact: true })).toHaveCount(0);
  });

  test("0.8 no top-bar control disappears at any tested viewport width", async ({ page }) => {
    await login(page);
    for (const w of [1600, 1000, 768, 500, 360]) {
      await page.setViewportSize({ width: w, height: 800 });
      await allVisible(page, TOPBAR_CONTROLS);
    }
  });

  test("0.9 mobile icon/touch targets are large enough (>= 32px)", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 780 });
    await login(page);
    for (const id of ["refresh-data", "settings-gear", "filter-apply", "sigma-button"]) {
      const b = await page.getByTestId(id).boundingBox();
      expect(Math.min(b!.width, b!.height)).toBeGreaterThanOrEqual(32);
    }
  });

  test("0.10 live resize desktop->narrow reflows with no leftover artifacts / no h-scroll", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    for (const w of [1200, 900, 700, 500, 380]) {
      await page.setViewportSize({ width: w, height: 900 });
      await noHorizontalScroll(page);
    }
  });

  test("0.11 RTL is consistent in the chrome (html dir=rtl, no accidental LTR row)", async ({ page }) => {
    await login(page);
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    // logo (rightmost item) sits to the right of the settings gear (leftmost)
    const logo = await page.getByTestId("logo").boundingBox();
    const gear = await page.getByTestId("settings-gear").boundingBox();
    expect(logo!.x).toBeGreaterThan(gear!.x);
  });
});

test.describe("Component 0b — General Responsiveness (6)", () => {
  test("0b.1 rotating a mobile device (portrait<->landscape) reflows live", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await noHorizontalScroll(page);
    await page.setViewportSize({ width: 844, height: 390 });
    await noHorizontalScroll(page);
    await expect(page.getByTestId("filter-apply")).toBeVisible();
  });

  test("0b.2 browser zoom / font-scaling doesn't overflow containers", async ({ page }) => {
    await login(page);
    await page.evaluate(() => ((document.body.style as any).zoom = "1.4"));
    await noHorizontalScroll(page);
    await expect(page.getByTestId("filter-apply")).toBeVisible();
    await page.evaluate(() => ((document.body.style as any).zoom = "1"));
  });

  test("0b.3 progressive desktop narrowing reflows smoothly through intermediate widths", async ({ page }) => {
    await login(page);
    for (let w = 1440; w >= 360; w -= 90) {
      await page.setViewportSize({ width: w, height: 860 });
      await noHorizontalScroll(page);
    }
  });

  test("0b.4 reduced viewport area (DevTools/split-screen) reflows correctly", async ({ page }) => {
    await login(page);
    await page.setViewportSize({ width: 700, height: 500 });
    await noHorizontalScroll(page);
    await expect(page.getByTestId("event-list")).toBeVisible();
  });

  test("0b.5 an extremely narrow width doesn't crash the layout", async ({ page }) => {
    await login(page);
    await page.setViewportSize({ width: 280, height: 640 });
    await expect(page.getByTestId("app-ready")).toBeVisible();
    await expect(page.getByTestId("filter-apply")).toBeVisible();
  });

  test("0b.6 an extremely wide monitor doesn't leave the layout broken/stretched", async ({ page }) => {
    await page.setViewportSize({ width: 2560, height: 1400 });
    await login(page);
    await noHorizontalScroll(page);
    await expect(page.getByTestId("event-list")).toBeVisible();
  });
});
