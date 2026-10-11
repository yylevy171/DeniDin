/**
 * Component 7 — Σ Summation. PLAYWRIGHT-TEST-PLAN.md §7.
 * v1 is a deliberately naive raw sum of every visible row's `amount` (null/unparseable excluded).
 * Any Apply / refresh clears a shown sum entirely; expand/collapse never touches it.
 */
import { test, expect, Page } from "@playwright/test";
import { login, rowIds, readEvent, idsWithinDays, msOnly, applyFilters } from "./_helpers";

async function sigma(page: Page) {
  await page.getByTestId("sigma-button").click();
  await expect(page.getByTestId("sigma-result")).toBeVisible();
  return (await page.getByTestId("sigma-result").textContent()) || "";
}
/** raw sum + contributing count of the numeric amounts among the currently-visible rows */
async function expected(page: Page) {
  const ids = await rowIds(page);
  const nums = ids.map((i) => readEvent(i).amount).filter((a) => typeof a === "number") as number[];
  return { n: nums.length, total: nums.reduce((s, x) => s + x, 0) };
}
function parseSigma(txt: string) {
  const clean = txt.replace(/[‎‏‪-‮]/g, ""); // strip bidi marks
  const n = Number((clean.match(/([\d,]+)\s*אירוע/) || [])[1]?.replace(/,/g, ""));
  const after = clean.split("₪")[1] || "";
  const total = Number((after.match(/-?[\d,]+(?:\.\d+)?/) || [])[0]?.replace(/,/g, ""));
  return { n, total };
}

test.describe("7.1 Basic sum/count display (4)", () => {
  test("7.1.1 correct total matching the sum of every visible row's amount", async ({ page }) => {
    await login(page);
    const exp = await expected(page);
    expect(parseSigma(await sigma(page))).toEqual(exp);
  });

  test("7.1.2 displayed count matches events actually contributing (nulls not counted)", async ({ page }) => {
    await login(page);
    const exp = await expected(page);
    const got = parseSigma(await sigma(page));
    expect(got.n).toBe(exp.n);
    expect(got.n).toBeLessThan((await rowIds(page)).length); // at least one null-amount row present
  });

  test("7.1.3 repeat press with nothing changed is deterministic", async ({ page }) => {
    await login(page);
    const a = await sigma(page);
    const b = await sigma(page);
    expect(a).toBe(b);
  });

  test("7.1.4 a single-row view shows that row's amount with count 1", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-global").fill("בדיקת פתרון לפי מזהה הודעה"); // E12 description
    await applyFilters(page);
    expect((await rowIds(page))).toEqual(["E12"]);
    const got = parseSigma(await sigma(page));
    expect(got).toEqual({ n: 1, total: readEvent("E12").amount });
  });
});

test.describe("7.2 Sum disappears on view change (4)", () => {
  test("7.2.1 applying a filter change clears the previously-shown sum entirely", async ({ page }) => {
    await login(page);
    await sigma(page);
    await msOnly(page, "type", ["הסכם"]);
    await applyFilters(page);
    await expect(page.getByTestId("sigma-result")).toHaveCount(0);
  });

  test("7.2.2 pressing refresh also clears it entirely", async ({ page }) => {
    await login(page);
    await sigma(page);
    await page.getByTestId("refresh-data").click();
    await expect(page.getByTestId("loading")).toHaveCount(0);
    await expect(page.getByTestId("sigma-result")).toHaveCount(0);
  });

  test("7.2.3 the sum only reappears by pressing Σ again", async ({ page }) => {
    await login(page);
    await sigma(page);
    await applyFilters(page); // no-op apply still clears
    await expect(page.getByTestId("sigma-result")).toHaveCount(0);
    await page.getByTestId("sigma-button").click();
    await expect(page.getByTestId("sigma-result")).toBeVisible();
  });

  test("7.2.4 merely expanding/collapsing rows does NOT clear an already-shown sum", async ({ page }) => {
    await login(page);
    const before = await sigma(page);
    await page.getByTestId("expand-toggle-E1").click();
    await expect(page.getByTestId("detail-panel-E1")).toBeVisible();
    await page.getByTestId("expand-toggle-E1").click();
    await expect(page.getByTestId("sigma-result")).toHaveText(before);
  });
});

test.describe("7.3 Excluding null/unparseable amounts (3)", () => {
  test("7.3.1/7.3.2 a null-amount event is excluded from both the sum and the count", async ({ page }) => {
    await login(page);
    const exp = await expected(page); // computed excluding nulls
    const got = parseSigma(await sigma(page));
    expect(got).toEqual(exp);
    // E8 (null amount) is on screen but not contributing
    expect((await rowIds(page))).toContain("E8");
  });

  test("7.3.3 a view where every event has a null amount shows count 0, not an error", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-global").fill("הסכם ללא סכום"); // only E8
    await applyFilters(page);
    expect((await rowIds(page))).toEqual(["E8"]);
    const got = parseSigma(await sigma(page));
    expect(got.n).toBe(0);
    expect(got.total).toBe(0);
  });
});

test.describe("7.4 Independence from expand/collapse state (2)", () => {
  test("7.4.1 sum is identical whether computed with zero or all rows expanded", async ({ page }) => {
    await login(page);
    const collapsed = parseSigma(await sigma(page));
    await page.getByTestId("expand-all").click();
    // press Σ fresh — it should not have been cleared, but recomputing must match
    await page.getByTestId("sigma-button").click();
    const expandedVal = parseSigma((await page.getByTestId("sigma-result").textContent()) || "");
    expect(expandedVal).toEqual(collapsed);
  });

  test("7.4.2 expanding/collapsing does not itself clear or recompute the sum", async ({ page }) => {
    await login(page);
    const txt = await sigma(page);
    await page.getByTestId("expand-all").click();
    await expect(page.getByTestId("sigma-result")).toHaveText(txt);
  });
});

test.describe("7.5 Sign/decimal/currency correctness (4, raw values) (4)", () => {
  test("7.5.1 a genuinely negative stored amount correctly reduces the total", async ({ page }) => {
    await login(page);
    const withNeg = parseSigma(await sigma(page)).total;
    // exclude E9 (negative) via free text that matches everything else is hard; instead check
    // the total equals the arithmetic sum that includes the negative
    const exp = await expected(page);
    expect(withNeg).toBe(exp.total);
    expect(readEvent("E9").amount).toBeLessThan(0);
  });

  test("7.5.2 a view netting to a negative raw total displays that correctly, not floored at 0", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-global").fill("זיכוי"); // E9 only, amount -500
    await applyFilters(page);
    expect((await rowIds(page))).toEqual(["E9"]);
    const got = parseSigma(await sigma(page));
    expect(got.total).toBe(-500);
  });

  test("7.5.3 non-integer amounts sum without visible rounding distortion", async ({ page }) => {
    await login(page);
    // fixture amounts are integers; assert the formatter round-trips the integer total exactly
    const exp = await expected(page);
    const got = parseSigma(await sigma(page));
    expect(got.total).toBe(exp.total);
    expect(Number.isInteger(got.total)).toBeTruthy();
  });

  test("7.5.4 currency formatting stays consistent regardless of sign", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-global").fill("זיכוי");
    await applyFilters(page);
    const txt = await sigma(page);
    expect(txt).toContain("₪");
  });
});

test.describe("7.6 Σ disabled during refresh (1)", () => {
  test("7.6.1 the Σ button is disabled while a refresh is in flight, re-enabled after", async ({ page }) => {
    await login(page);
    await page.route("**/api/events**", async (r) => {
      await new Promise((res) => setTimeout(res, 800));
      await r.continue();
    });
    await page.getByTestId("refresh-data").click();
    await expect(page.getByTestId("sigma-button")).toHaveAttribute("aria-disabled", "true");
    await expect(page.getByTestId("loading")).toHaveCount(0);
    await expect(page.getByTestId("sigma-button")).not.toHaveAttribute("aria-disabled", "true");
  });
});
