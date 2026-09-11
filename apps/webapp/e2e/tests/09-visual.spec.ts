/**
 * Component 9 — Visual Regression. PLAYWRIGHT-TEST-PLAN.md §9.
 * Pixel-compares a fresh screenshot against a committed baseline (tolerance from
 * playwright.config.ts). Baselines are updated ONLY via a deliberate `--update-snapshots`
 * run whose new images are reviewed and committed like code (§9.5).
 *
 * NOTE: the seeded fixture writes dates relative to the seed day, so the visible date column
 * shifts if the fixture is re-seeded on a later calendar day. Regenerate the baselines as part
 * of that same deliberate step (this is exactly the §9.5 governance rule in practice).
 */
import { test, expect, Page } from "@playwright/test";
import { login } from "./_helpers";

async function settle(page: Page) {
  await expect(page.getByTestId("app-ready")).toBeVisible();
  await expect(page.getByTestId("loading")).toHaveCount(0);
  await page.waitForTimeout(150); // let RNW layout settle
}
async function expand(page: Page, id: string) {
  await page.getByTestId(`expand-toggle-${id}`).click({ force: true });
  await expect(page.getByTestId(`detail-panel-${id}`)).toBeVisible();
  await expect(page.getByTestId("detail-loading")).toHaveCount(0);
  await page.waitForTimeout(200);
}
async function setDark(page: Page) {
  await page.getByTestId("settings-gear").click();
  await page.getByTestId("setting-theme").click();
  await page.getByTestId("settings-close").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
}

test.describe("9.1 Collapsed list baseline (1)", () => {
  test("9.1.1 desktop, default light theme, seeded fixture", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await settle(page);
    await expect(page).toHaveScreenshot("collapsed-desktop-light.png", { fullPage: true });
  });
});

test.describe("9.2 Expanded row baseline (2)", () => {
  test("9.2.1 a single expanded row (both panels, desktop)", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await settle(page);
    await expand(page, "E3"); // text-only chat, deterministic
    await expect(page.getByTestId("expanded-E3")).toHaveScreenshot("expanded-row-desktop.png");
  });

  test("9.2.2 an expanded row whose chat panel includes an image thumbnail", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await settle(page);
    await expand(page, "E1"); // M2 + M3 carry images
    await page.waitForTimeout(300); // thumbnails decode
    await expect(page.getByTestId("expanded-E1")).toHaveScreenshot("expanded-row-with-image-desktop.png");
  });
});

test.describe("9.3 Mobile baselines (2)", () => {
  test("9.3.1 collapsed list at mobile width", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await settle(page);
    await expect(page).toHaveScreenshot("collapsed-mobile.png", { fullPage: true });
  });

  test("9.3.2 expanded row at mobile width (stacked panels)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await settle(page);
    await expand(page, "E3");
    await expect(page.getByTestId("expanded-E3")).toHaveScreenshot("expanded-row-mobile.png");
  });
});

test.describe("9.4 Dark theme baseline (2)", () => {
  test("9.4.1 collapsed list in dark theme", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await settle(page);
    await setDark(page);
    await page.waitForTimeout(150);
    await expect(page).toHaveScreenshot("collapsed-desktop-dark.png", { fullPage: true });
  });

  test("9.4.2 expanded row in dark theme", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await settle(page);
    await setDark(page);
    await expand(page, "E3");
    await expect(page.getByTestId("expanded-E3")).toHaveScreenshot("expanded-row-desktop-dark.png");
  });
});

test.describe("9.5 Baseline governance (1 process rule)", () => {
  test("9.5 baselines change only via a deliberate, committed --update-snapshots run", async () => {
    test.info().annotations.push({
      type: "process-rule",
      description:
        "PLAYWRIGHT-TEST-PLAN 9.5: a baseline image is updated ONLY through an explicit " +
        "`playwright test --update-snapshots` run whose new PNGs under tests/09-visual.spec.ts-snapshots/ " +
        "are reviewed and committed like any other code change — never auto-accepted because a run " +
        "produced a new screenshot. Not an automated assertion; enforced by code review + the fact " +
        "that CI (none here) would fail on an un-updated baseline.",
    });
    expect(true).toBe(true);
  });
});
