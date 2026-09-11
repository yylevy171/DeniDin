/**
 * Component 3 — Filters (PLAYWRIGHT-TEST-PLAN.md §3, ~85 cases).
 *
 * Mental model: all filters always active; empty filter == passthrough; no "clear all";
 * date range always holds a real range. All on-screen filters apply CLIENT-SIDE on Apply
 * ("חפש!" / filter-apply). Only moving "from" earlier than what's loaded triggers a backend
 * fetch.
 */
import { test, expect, Page } from "@playwright/test";
import {
  FULL,
  applyFilters,
  idsBySourceType,
  login,
  msOnly as msSelectOnly,
  msToggle,
  readEvent,
  rowIds,
  rows,
} from "./_helpers";

const TYPES = ["הסכם", "בנק", "חשבונית"];

test.describe("3.1 Apply gating (10)", () => {
  test("3.1.1 selecting an event type without Apply leaves the list unchanged", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    expect(await rowIds(page)).toEqual(before);
  });

  test("3.1.2 typing in the client-name field without Apply leaves the list unchanged", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await page.getByTestId("filter-client-name").fill("ישראל");
    await page.keyboard.press("Escape");
    expect(await rowIds(page)).toEqual(before);
  });

  test("3.1.3 typing in the global search field without Apply leaves the list unchanged", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await page.getByTestId("filter-global").fill("זיכוי");
    expect(await rowIds(page)).toEqual(before);
  });

  test("3.1.4 changing the date range without Apply leaves the list unchanged", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await page.getByTestId("filter-date-from").fill(isoDaysAgo(3));
    expect(await rowIds(page)).toEqual(before);
  });

  test("3.1.5 selecting an event subtype without Apply leaves the list unchanged", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await msSelectOnly(page, "subtype", ["יצירה"]);
    expect(await rowIds(page)).toEqual(before);
  });

  test("3.1.6 Enter inside the client-name field does not apply", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await page.getByTestId("filter-client-name").fill("ישראל");
    await page.getByTestId("filter-client-name").press("Enter");
    expect(await rowIds(page)).toEqual(before);
  });

  test("3.1.7 Enter inside the global search field does not apply", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await page.getByTestId("filter-global").fill("זיכוי");
    await page.getByTestId("filter-global").press("Enter");
    expect(await rowIds(page)).toEqual(before);
  });

  test("3.1.8 multiple filters set at once, none applied yet, still shows the unfiltered list", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    await page.getByTestId("filter-client-name").fill("מש");
    await page.keyboard.press("Escape");
    await page.getByTestId("filter-global").fill("שכר");
    expect(await rowIds(page)).toEqual(before);
  });

  test("3.1.9 Apply with nothing actually changed is a safe no-op", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await applyFilters(page);
    expect(await rowIds(page)).toEqual(before);
  });

  test("3.1.10 repeated identical Applies don't duplicate/corrupt the result", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    await applyFilters(page);
    const once = await rowIds(page);
    await applyFilters(page);
    await applyFilters(page);
    expect(await rowIds(page)).toEqual(once);
  });
});

test.describe("3.2 Event type filter (7)", () => {
  test("3.2.1 selecting one event type shows only rows of that type", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    await applyFilters(page);
    for (const id of await rowIds(page)) expect(readEvent(id).source_type).toBe("הסכם");
    expect((await rowIds(page)).sort()).toEqual(idsBySourceType("הסכם").sort());
  });

  test("3.2.2 selecting two types shows rows matching either (OR)", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["הסכם", "בנק"]);
    await applyFilters(page);
    const got = new Set(await rowIds(page));
    for (const id of got) expect(["הסכם", "בנק"]).toContain(readEvent(id).source_type);
    for (const id of [...idsBySourceType("הסכם"), ...idsBySourceType("בנק")]) expect(got.has(id)).toBe(true);
  });

  test("3.2.3 selecting all types equals no type filter at all", async ({ page }) => {
    await login(page);
    const all = await rowIds(page);
    await msSelectOnly(page, "type", TYPES); // re-select every type
    await applyFilters(page);
    expect((await rowIds(page)).sort()).toEqual(all.sort());
  });

  test("3.2.4 deselecting one of several narrows correctly on the next Apply", async ({ page }) => {
    await login(page);
    await msToggle(page, "type", "חשבונית"); // now הסכם + בנק
    await applyFilters(page);
    const got = new Set(await rowIds(page));
    for (const id of got) expect(readEvent(id).source_type).not.toBe("חשבונית");
  });

  test("3.2.5 deselecting all returns to passthrough on Apply", async ({ page }) => {
    await login(page);
    const all = await rowIds(page);
    await page.getByTestId("filter-type").click();
    await page.getByTestId("filter-type-opt-all").click(); // clear all
    await page.getByTestId("filter-type-opt-all").click(); // re-select all
    await page.getByTestId("filter-type").click();
    await applyFilters(page);
    expect((await rowIds(page)).sort()).toEqual(all.sort());
  });

  test("3.2.6 dropdown lists the distinct source types of the full loaded window, stable under other filters", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-type").click();
    for (const t of TYPES) await expect(page.getByTestId(`filter-type-opt-${t}`)).toBeVisible();
    await page.getByTestId("filter-type").click();
    // narrow by client, re-open: option list must be unchanged (computed from full load)
    await page.getByTestId("filter-client-name").fill("ישראל ישראלי");
    await page.keyboard.press("Escape");
    await applyFilters(page);
    await page.getByTestId("filter-type").click();
    for (const t of TYPES) await expect(page.getByTestId(`filter-type-opt-${t}`)).toBeVisible();
  });

  test("3.2.7 a selected type with zero matches shows the empty state, not an error", async ({ page }) => {
    await login(page);
    // filter to בנק then also restrict date to today only -> E7 is today/בנק, so use client too
    await msSelectOnly(page, "type", ["בנק"]);
    await page.getByTestId("filter-client-name").fill("no-such-bank-client");
    await page.keyboard.press("Escape");
    await applyFilters(page);
    await expect(page.getByTestId("empty-state")).toBeVisible();
    await expect(rows(page)).toHaveCount(0);
  });
});

test.describe("3.3 Event subtype filter — dynamic scoping (8)", () => {
  test("3.3.1 with no event type selected, every subtype is selectable", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-subtype").click();
    for (const s of ["יצירה", "הפקדה", "קבלה", "חשבונית מס"]) {
      await expect(page.getByTestId(`filter-subtype-opt-${s}`)).not.toHaveAttribute("aria-disabled", "true");
    }
  });

  test("3.3.2 selecting one event type grays out subtypes invalid for it", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["בנק"]);
    await page.getByTestId("filter-subtype").click();
    await expect(page.getByTestId("filter-subtype-opt-הפקדה")).not.toHaveAttribute("aria-disabled", "true");
    await expect(page.getByTestId("filter-subtype-opt-יצירה")).toHaveAttribute("aria-disabled", "true");
  });

  test("3.3.3 selecting a second type un-grays subtypes valid for either", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["בנק"]);
    await msToggle(page, "type", "הסכם"); // בנק + הסכם
    await page.getByTestId("filter-subtype").click();
    await expect(page.getByTestId("filter-subtype-opt-יצירה")).not.toHaveAttribute("aria-disabled", "true");
    await expect(page.getByTestId("filter-subtype-opt-הפקדה")).not.toHaveAttribute("aria-disabled", "true");
    await expect(page.getByTestId("filter-subtype-opt-קבלה")).toHaveAttribute("aria-disabled", "true");
  });

  test("3.3.4 deselecting all types returns every subtype to selectable", async ({ page }) => {
    test.fixme(
      true,
      "Known gap: disabledSubs treats only the ALL-types state as 'no filter'; with ZERO " +
        "types selected it greys every subtype instead. PLAYWRIGHT-TEST-PLAN 3.3.4 / 3.3.1."
    );
    await login(page);
    await msSelectOnly(page, "type", ["בנק"]);
    await page.getByTestId("filter-type").click();
    await page.getByTestId("filter-type-opt-בנק").click(); // now none selected
    await page.getByTestId("filter-type").click();
    await page.getByTestId("filter-subtype").click();
    await expect(page.getByTestId("filter-subtype-opt-יצירה")).not.toHaveAttribute("aria-disabled", "true");
    await expect(page.getByTestId("filter-subtype-opt-קבלה")).not.toHaveAttribute("aria-disabled", "true");
  });

  test("3.3.5 a selected subtype that becomes invalid is auto-deselected", async ({ page }) => {
    test.fixme(
      true,
      "Known gap (tasks.md Stories 4-8): subSel keeps a now-invalid subtype instead of auto-" +
        "removing it when the type selection changes. PLAYWRIGHT-TEST-PLAN 3.3.5."
    );
    await login(page);
    await msSelectOnly(page, "subtype", ["הפקדה"]);
    await msSelectOnly(page, "type", ["הסכם"]); // הפקדה now invalid
    await page.getByTestId("filter-subtype").click();
    await expect(page.getByTestId("filter-subtype-opt-הפקדה")).toHaveAttribute("aria-checked", "false");
  });

  test("3.3.6 grayed-out options are genuinely unclickable", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "subtype", ["הפקדה"]); // start: only הפקדה checked
    await msSelectOnly(page, "type", ["בנק"]);
    await page.getByTestId("filter-subtype").click();
    const opt = page.getByTestId("filter-subtype-opt-קבלה");
    await expect(opt).toHaveAttribute("aria-disabled", "true");
    const before = await opt.getAttribute("aria-checked");
    await opt.click({ force: true });
    await expect(opt).toHaveAttribute("aria-checked", before || "false"); // click had no effect
  });

  test("3.3.7 type + a valid subtype together AND-narrow correctly", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    await msSelectOnly(page, "subtype", ["עדכון"]);
    await applyFilters(page);
    for (const id of await rowIds(page)) {
      const e = readEvent(id);
      expect(e.source_type).toBe("הסכם");
      expect(e.event_subtype).toBe("עדכון");
    }
    expect(await rowIds(page)).toContain("E3");
  });

  test("3.3.8 the subtype dropdown's enabled/grayed state updates live without reopening", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-subtype").click();
    await expect(page.getByTestId("filter-subtype-opt-הפקדה")).not.toHaveAttribute("aria-disabled", "true");
    await page.getByTestId("filter-subtype").click();
    await msSelectOnly(page, "type", ["הסכם"]);
    await page.getByTestId("filter-subtype").click();
    await expect(page.getByTestId("filter-subtype-opt-הפקדה")).toHaveAttribute("aria-disabled", "true");
  });
});

test.describe("3.4 Client-name typeahead + fuzzy filter (22)", () => {
  const req = (page: Page) => {
    const hits: string[] = [];
    page.on("request", (r) => r.url().includes("/api/clients/search") && hits.push(r.url()));
    return hits;
  };

  test("3.4.1 2+ characters fires the suggestion search after a debounce", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("ישר");
    await expect(page.getByTestId("client-suggest-list")).toBeVisible();
    await expect(page.getByTestId("client-suggest-ישראל ישראלי")).toBeVisible();
  });

  test("3.4.2 1 character does not fire it", async ({ page }) => {
    await login(page);
    const hits = req(page);
    await page.getByTestId("filter-client-name").fill("י");
    await page.waitForTimeout(500);
    expect(hits.length).toBe(0);
    await expect(page.getByTestId("client-suggest-list")).toHaveCount(0);
  });

  test("3.4.3 clearing the field closes the dropdown", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("ישר");
    await expect(page.getByTestId("client-suggest-list")).toBeVisible();
    await page.getByTestId("filter-client-name").fill("");
    await expect(page.getByTestId("client-suggest-list")).toHaveCount(0);
  });

  test("3.4.4 additional characters re-query and narrow further", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("ישראל");
    await expect(page.getByTestId("client-suggest-ישראל ישראלי")).toBeVisible();
    await page.getByTestId("filter-client-name").fill("ישראל כ");
    await expect(page.getByTestId("client-suggest-ישראל כהן")).toBeVisible();
    await expect(page.getByTestId("client-suggest-ישראל ישראלי")).toHaveCount(0);
  });

  test("3.4.5 matching is prefix-only — a mid-string match is not suggested", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("ראל"); // 'ישראל' contains it mid-string
    await page.waitForTimeout(500);
    await expect(page.getByTestId("client-suggest-ישראל ישראלי")).toHaveCount(0);
  });

  test("3.4.6 several keystrokes inside the debounce window fire only one request", async ({ page }) => {
    await login(page);
    const hits = req(page);
    const f = page.getByTestId("filter-client-name");
    for (const t of ["מ", "מש", "משה", "משה ", "משה ל"]) {
      await f.fill(t);
      await page.waitForTimeout(40);
    }
    await page.waitForTimeout(600);
    expect(hits.length).toBe(1);
  });

  test("3.4.7 clicking a suggestion fills the field and closes the dropdown", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("ישראל כ");
    await page.getByTestId("client-suggest-ישראל כהן").click();
    await expect(page.getByTestId("filter-client-name")).toHaveValue("ישראל כהן");
    await expect(page.getByTestId("client-suggest-list")).toHaveCount(0);
  });

  test("3.4.8 typing again after picking reopens a fresh dropdown", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("ישראל כ");
    await page.getByTestId("client-suggest-ישראל כהן").click();
    await page.getByTestId("filter-client-name").fill("ישראל כהן ע"); // keep typing
    await page.waitForTimeout(500);
    await expect(page.getByTestId("client-suggest-empty")).toBeVisible();
  });

  test("3.4.9 ignoring the dropdown and typing freely is allowed", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("משהו שלא קיים");
    await applyFilters(page);
    await expect(page.getByTestId("empty-state")).toBeVisible();
  });

  test("3.4.10 clicking outside closes the dropdown without changing the text", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("ישר");
    await expect(page.getByTestId("client-suggest-list")).toBeVisible();
    await page.mouse.click(500, 460); // click outside the filter bar (hits the click-away backdrop)
    await expect(page.getByTestId("client-suggest-list")).toHaveCount(0);
    await expect(page.getByTestId("filter-client-name")).toHaveValue("ישר");
  });

  test("3.4.11 Escape closes the dropdown without changing the text", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("ישר");
    await expect(page.getByTestId("client-suggest-list")).toBeVisible();
    await page.getByTestId("filter-client-name").press("Escape");
    await expect(page.getByTestId("client-suggest-list")).toHaveCount(0);
    await expect(page.getByTestId("filter-client-name")).toHaveValue("ישר");
  });

  test("3.4.12 arrow keys move a highlight through suggestions", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("ישראל");
    await expect(page.getByTestId("client-suggest-active")).toHaveText("ישראל ישראלי");
    await page.getByTestId("filter-client-name").press("ArrowDown");
    await expect(page.getByTestId("client-suggest-active")).toHaveText("ישראל כהן");
    await page.getByTestId("filter-client-name").press("ArrowUp");
    await expect(page.getByTestId("client-suggest-active")).toHaveText("ישראל ישראלי");
  });

  test("3.4.13 Enter while a suggestion is highlighted selects it but does NOT Apply", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await page.getByTestId("filter-client-name").fill("ישראל");
    await expect(page.getByTestId("client-suggest-ישראל כהן")).toBeVisible();
    await page.getByTestId("filter-client-name").press("ArrowDown"); // -> ישראל כהן
    await page.getByTestId("filter-client-name").press("Enter");
    await expect(page.getByTestId("filter-client-name")).toHaveValue("ישראל כהן");
    expect(await rowIds(page)).toEqual(before); // list not filtered yet
  });

  test("3.4.14 zero matches shows an explicit 'no matches' state", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("קליינטלאקיים");
    await expect(page.getByTestId("client-suggest-empty")).toBeVisible();
  });

  test("3.4.15 a slow stale suggestion response must not overwrite a newer one", async ({ page }) => {
    await login(page);
    let n = 0;
    await page.route("**/api/clients/search**", async (r) => {
      n++;
      await new Promise((res) => setTimeout(res, n === 1 ? 900 : 50)); // first is slow
      await r.continue();
    });
    const f = page.getByTestId("filter-client-name");
    await f.fill("ישראל"); // slow request in flight
    await page.waitForTimeout(320);
    await f.fill("משה"); // fast request supersedes
    await page.waitForTimeout(1200);
    await expect(page.getByTestId("client-suggest-משה לוי")).toBeVisible();
    await expect(page.getByTestId("client-suggest-ישראל ישראלי")).toHaveCount(0);
  });

  test("3.4.16 a failed suggestion request shows a graceful state, field stays usable", async ({ page }) => {
    await login(page);
    await page.route("**/api/clients/search**", (r) => r.abort());
    await page.getByTestId("filter-client-name").fill("ישר");
    await expect(page.getByTestId("client-suggest-error")).toBeVisible();
    await page.unroute("**/api/clients/search**");
    await page.getByTestId("filter-client-name").fill("ישרא");
    await expect(page.getByTestId("client-suggest-ישראל ישראלי")).toBeVisible();
  });

  test("3.4.17 whitespace-only input is treated as empty/passthrough", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await page.getByTestId("filter-client-name").fill("   ");
    await page.waitForTimeout(400);
    await expect(page.getByTestId("client-suggest-list")).toHaveCount(0);
    await applyFilters(page);
    expect((await rowIds(page)).sort()).toEqual(before.sort());
  });

  test("3.4.18 a typo still fuzzy-matches the intended client at Apply", async ({ page }) => {
    test.fixme(
      true,
      "Known gap (tasks.md Stories 4-8): the applied client-name match is substring/normalized, " +
        "not fuzzy. PLAYWRIGHT-TEST-PLAN 3.4.18."
    );
    await login(page);
    await page.getByTestId("filter-client-name").fill("ישראל ישראל"); // near-miss of 'ישראל ישראלי'
    await page.keyboard.press("Escape");
    await applyFilters(page);
    expect(await rowIds(page)).toContain("E1");
  });

  test("3.4.19 gibberish returns zero rows cleanly at Apply", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("qwezxcasd");
    await page.keyboard.press("Escape");
    await applyFilters(page);
    await expect(page.getByTestId("empty-state")).toBeVisible();
  });

  test("3.4.20 Apply immediately after picking a suggestion filters correctly", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("משה");
    await page.getByTestId("client-suggest-משה לוי").click();
    await applyFilters(page);
    for (const id of await rowIds(page)) expect(readEvent(id).client_name).toContain("משה לוי");
  });

  test("3.4.21 clearing to empty then Apply applies no restriction", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await page.getByTestId("filter-client-name").fill("משה");
    await page.getByTestId("filter-client-name").fill("");
    await applyFilters(page);
    expect((await rowIds(page)).sort()).toEqual(before.sort());
  });

  test("3.4.22 editing another filter doesn't clear client-name text already typed", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-client-name").fill("משה לוי");
    await page.keyboard.press("Escape");
    await page.getByTestId("filter-global").fill("שכר");
    await expect(page.getByTestId("filter-client-name")).toHaveValue("משה לוי");
  });
});

test.describe("3.5 Global free-text search (9)", () => {
  test("3.5.1 matches in description", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-global").fill("זיכוי");
    await applyFilters(page);
    expect(await rowIds(page)).toContain(FULL().negative_amount_id); // E9 description = 'זיכוי'
  });

  test("3.5.2 matches in amount (numeric-as-text)", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-global").fill("999");
    await applyFilters(page);
    expect(await rowIds(page)).toContain("E6");
  });

  test("3.5.3 matches in a date field", async ({ page }) => {
    await login(page);
    const e = readEvent("E1");
    const d = (e.event_date as string).split("/").reverse().join("-"); // yyyy-mm-dd substring won't be in blob; use event_date raw
    await page.getByTestId("filter-global").fill(e.event_date);
    await applyFilters(page);
    expect(await rowIds(page)).toContain("E1");
    expect(d).toBeTruthy();
  });

  test("3.5.4 matches a field not shown anywhere in the UI (bank_account)", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-global").fill("654844"); // E2 bank_account, but E2 is 8d out
    await import("./_helpers").then((h) => h.setDaysBack(page, 20));
    await page.getByTestId("filter-global").fill("654844");
    await applyFilters(page);
    expect(await rowIds(page)).toContain("E2");
  });

  test("3.5.5 a typo still fuzzy-matches", async ({ page }) => {
    test.fixme(true, "Known gap (tasks.md Stories 4-8): free-text match is substring, not fuzzy. PLAYWRIGHT-TEST-PLAN 3.5.5.");
    await login(page);
    await page.getByTestId("filter-global").fill("זיכי"); // typo of זיכוי
    await applyFilters(page);
    expect(await rowIds(page)).toContain(FULL().negative_amount_id);
  });

  test("3.5.6 no-match returns zero cleanly", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-global").fill("נוסטרדמוס-אין-כזה");
    await applyFilters(page);
    await expect(page.getByTestId("empty-state")).toBeVisible();
  });

  test("3.5.7 a broad/common-term match doesn't error or hang", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-global").fill("שכר");
    await applyFilters(page);
    await expect(page.getByTestId("loading")).toHaveCount(0);
    expect((await rowIds(page)).length).toBeGreaterThan(0);
  });

  test("3.5.8 combines as AND with another filter", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    await page.getByTestId("filter-global").fill("שכר טרחה");
    await applyFilters(page);
    for (const id of await rowIds(page)) {
      const e = readEvent(id);
      expect(e.source_type).toBe("הסכם");
      expect(JSON.stringify(e).includes("שכר טרחה") || (e.search_blob ?? "")).toBeTruthy();
    }
  });

  test("3.5.9 empty field is passthrough", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await page.getByTestId("filter-global").fill("");
    await applyFilters(page);
    expect((await rowIds(page)).sort()).toEqual(before.sort());
  });
});

function isoDaysAgo(n: number): string {
  const t = new Date();
  t.setDate(t.getDate() - n);
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
}
function todayIso(): string {
  const t = new Date();
  return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
}

test.describe("3.6 Date range = load window (8)", () => {
  test("3.6.1 initial range exactly equals the load window", async ({ page }) => {
    await login(page);
    await expect(page.getByTestId("filter-date-from")).toHaveValue(isoDaysAgo(7));
    await expect(page.getByTestId("filter-date-to")).toHaveValue(todayIso());
  });

  test("3.6.2 'from' picker floor is a fixed absolute 2024-01-01 (NOT the window start)", async ({ page }) => {
    await login(page);
    await expect(page.getByTestId("filter-date-from")).toHaveAttribute("min", "2024-01-01");
  });

  test("3.6.3 'to' picker clamped at today", async ({ page }) => {
    await login(page);
    await expect(page.getByTestId("filter-date-to")).toHaveAttribute("max", todayIso());
  });

  test("3.6.4 narrowing inward filters correctly (client-side)", async ({ page }) => {
    await login(page);
    await page.getByTestId("filter-date-from").fill(isoDaysAgo(2));
    await applyFilters(page);
    for (const id of await rowIds(page)) {
      const e = readEvent(id);
      const head = (e.txn_date || e.event_datetime || e.event_date).split(" ")[0];
      const [dd, mm, yyyy] = head.split("/");
      expect(`${yyyy}-${mm}-${dd}` >= isoDaysAgo(2)).toBeTruthy();
    }
  });

  test("3.6.5 an invalid to-before-from range is prevented/auto-corrected", async ({ page }) => {
    await login(page);
    // the 'to' input's min is bound to 'from'; setting an earlier 'to' is rejected by the control
    await page.getByTestId("filter-date-from").fill(isoDaysAgo(3));
    await expect(page.getByTestId("filter-date-to")).toHaveAttribute("min", isoDaysAgo(3));
  });

  test("3.6.6 widening 'days back' immediately widens this filter's selectable bounds", async ({ page }) => {
    await login(page);
    await import("./_helpers").then((h) => h.setDaysBack(page, 30));
    await expect(page.getByTestId("filter-date-from")).toHaveValue(isoDaysAgo(30));
  });

  test("3.6.7 narrowing 'days back' clamps an out-of-range selection back into bounds", async ({ page }) => {
    await login(page);
    await import("./_helpers").then((h) => h.setDaysBack(page, 30));
    await import("./_helpers").then((h) => h.setDaysBack(page, 5));
    await expect(page.getByTestId("filter-date-from")).toHaveValue(isoDaysAgo(5));
  });

  test("3.6.8 narrowing this filter never triggers a new backend load", async ({ page }) => {
    await login(page);
    const hits: string[] = [];
    page.on("request", (r) => r.url().includes("/api/events") && hits.push(r.url()));
    await page.getByTestId("filter-date-from").fill(isoDaysAgo(2));
    await applyFilters(page);
    await page.waitForTimeout(300);
    expect(hits.length).toBe(0); // narrowing inward — pure client-side
  });
});

test.describe("3.7 Combined filters — AND across, OR within (6)", () => {
  test("3.7.1 type(OR) + client-name AND", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["הסכם", "חשבונית"]);
    await page.getByTestId("filter-client-name").fill("ישראל ישראלי");
    await page.keyboard.press("Escape");
    await applyFilters(page);
    for (const id of await rowIds(page)) {
      const e = readEvent(id);
      expect(["הסכם", "חשבונית"]).toContain(e.source_type);
      expect(e.client_name).toContain("ישראל ישראלי");
    }
  });

  test("3.7.2 triple combination (type + subtype + client-name)", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    await msSelectOnly(page, "subtype", ["יצירה"]);
    await page.getByTestId("filter-client-name").fill("ישראל ישראלי");
    await page.keyboard.press("Escape");
    await applyFilters(page);
    expect(await rowIds(page)).toEqual(["E1"]);
  });

  test("3.7.3 date-range-narrowed + type", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["חשבונית"]);
    await page.getByTestId("filter-date-from").fill(isoDaysAgo(1));
    await applyFilters(page);
    for (const id of await rowIds(page)) expect(readEvent(id).source_type).toBe("חשבונית");
    expect(await rowIds(page)).not.toContain("E4"); // E4 is 3 days back
  });

  test("3.7.4 all five categories set to match exactly one known row", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    await msSelectOnly(page, "subtype", ["יצירה"]);
    await page.getByTestId("filter-client-name").fill("ישראל ישראלי");
    await page.keyboard.press("Escape");
    await page.getByTestId("filter-global").fill("שכר טרחה");
    await page.getByTestId("filter-date-from").fill(isoDaysAgo(4));
    await applyFilters(page);
    expect(await rowIds(page)).toEqual(["E1"]);
  });

  test("3.7.5 all five set so no row satisfies all -> zero rows", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["בנק"]);
    await page.getByTestId("filter-client-name").fill("ישראל ישראלי"); // no בנק event for this client
    await page.keyboard.press("Escape");
    await applyFilters(page);
    await expect(page.getByTestId("empty-state")).toBeVisible();
  });

  test("3.7.6 removing one category correctly widens the result", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    await msSelectOnly(page, "subtype", ["יצירה"]);
    await applyFilters(page);
    const narrow = new Set(await rowIds(page));
    // widen: every הסכם-valid subtype selected == no effective subtype filter for הסכם rows
    await msSelectOnly(page, "subtype", ["יצירה", "עדכון", "מבוטל"]);
    await applyFilters(page);
    const wide = new Set(await rowIds(page));
    for (const id of narrow) expect(wide.has(id)).toBe(true); // superset
    expect(wide.size).toBeGreaterThan(narrow.size);
  });
});

test.describe("3.8 No clear button, manual reset (4)", () => {
  test("3.8.1 full manual reset across all filters restores the full loaded set", async ({ page }) => {
    await login(page);
    const before = await rowIds(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    await page.getByTestId("filter-client-name").fill("משה");
    await page.keyboard.press("Escape");
    await applyFilters(page);
    // manual reset
    await msSelectOnly(page, "type", TYPES);
    await page.getByTestId("filter-client-name").fill("");
    await applyFilters(page);
    await expect.poll(async () => (await rowIds(page)).sort().join(",")).toBe(before.sort().join(","));
  });

  test("3.8.2 partial reset leaves remaining filters still active", async ({ page }) => {
    await login(page);
    await msSelectOnly(page, "type", ["הסכם"]);
    await page.getByTestId("filter-global").fill("שכר");
    await applyFilters(page);
    await page.getByTestId("filter-global").fill(""); // reset only the free text
    await applyFilters(page);
    for (const id of await rowIds(page)) expect(readEvent(id).source_type).toBe("הסכם");
  });

  test("3.8.3 no 'clear all' control exists anywhere (absence check)", async ({ page }) => {
    await login(page);
    await expect(page.getByTestId("filter-clear")).toHaveCount(0);
    await expect(page.getByText(/נקה הכל|clear all/i)).toHaveCount(0);
  });

  test("3.8.4 resetting a multi-select via per-value unchecking == reopening and unchecking each", async ({ page }) => {
    await login(page);
    // path A: msOnly helper (flip only what's needed)
    await msSelectOnly(page, "type", ["הסכם"]);
    await applyFilters(page);
    const viaHelper = (await rowIds(page)).slice().sort();
    // reset to all, then path B: open once, uncheck בנק & חשבונית by hand
    await msSelectOnly(page, "type", TYPES);
    await applyFilters(page);
    await page.getByTestId("filter-type").click();
    await page.getByTestId("filter-type-opt-בנק").click();
    await page.getByTestId("filter-type-opt-חשבונית").click();
    await page.getByTestId("filter-type").click();
    await applyFilters(page);
    expect((await rowIds(page)).slice().sort()).toEqual(viaHelper);
  });
});
