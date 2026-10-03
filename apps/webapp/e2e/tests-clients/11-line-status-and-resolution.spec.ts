/**
 * Feature 092 — Clients tab: explicit line status (absorbs bugfix-068) + resolution corrections.
 * One test per APPROVED acceptance scenario (spec.md "User Acceptance Scenarios", UAT 1–9).
 * Real stack, no mocking: see playwright.clients.config.ts (seeded fixture + Morning SANDBOX,
 * read-only).
 *
 * Run: npx playwright test -c playwright.clients.config.ts
 *
 * Serial on purpose: every test writes the fixture's webapp_data/clients files. UAT 5
 * (migration) runs first because it asserts the state the backend's FIRST report produced.
 */
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect, Page, Locator } from "@playwright/test";
import { CLIENTS_API, CLIENTS_BASE } from "../playwright.clients.config";

test.describe.configure({ mode: "serial" });

const __dir = path.dirname(fileURLToPath(import.meta.url));
const M = JSON.parse(
  readFileSync(path.join(__dir, "..", ".fixture", "clients", "manifest.json"), "utf-8")
) as Record<string, any>;

const readJson = (file: string): any => {
  try {
    return JSON.parse(readFileSync(file, "utf-8"));
  } catch {
    return {};
  }
};

type Section = "check" | "active" | "debt" | "missing_agreement" | "settled" | "past";

async function login(page: Page) {
  await page.goto(`${CLIENTS_BASE}/?api=${encodeURIComponent(CLIENTS_API)}`);
  await page.getByTestId("password-input").fill(M.password);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-ready")).toBeVisible();
}

async function openClientsTab(page: Page) {
  await page.getByTestId("tab-clients").click();
  await expect(page.getByTestId("clients-view")).toBeVisible();
  await expect(page.getByTestId("clients-loading")).toHaveCount(0);
  await expect(page.getByTestId("clients-error")).toHaveCount(0);
}

/** Filter the list to one client so only its row (and its section) render. */
async function focusClient(page: Page, name: string) {
  await page.getByTestId("clients-search").fill(name);
}

const rowOf = (page: Page, name: string) => page.getByTestId(`client-row-${name}`);

/** The row, inside the given section (opening that accordion if it's collapsed). */
async function expectInSection(page: Page, name: string, section: Section): Promise<Locator> {
  const sec = page.getByTestId(`section-${section}`);
  await expect(sec).toBeVisible();
  const inSec = sec.getByTestId(`client-row-${name}`);
  if (!(await inSec.count())) await page.getByTestId(`section-header-${section}`).click();
  await expect(inSec).toBeVisible();
  return inSec;
}

const lineBtn = (page: Page, action: string, name: string) => page.getByTestId(`line-btn-${action}-${name}`);

async function revealUnmatched(page: Page) {
  const header = page.getByText("שמות לקוחות לתייג", { exact: true }).first();
  if (!(await page.locator('[data-testid^="unmatched-row-"]').count())) await header.click();
  await expect(page.locator('[data-testid^="unmatched-row-"]').first()).toBeVisible();
}

const unmatchedRow = (page: Page, raw: string) => page.getByTestId(`unmatched-row-${raw}`);

async function mapUnmatched(page: Page, raw: string, official: string) {
  await unmatchedRow(page, raw).getByTestId("unmatched-picker-input").fill(official);
  await page.getByTestId("unmatched-picker-list").getByText(official, { exact: true }).first().click();
  await expect(unmatchedRow(page, raw)).toHaveCount(0);
}

test.describe("Feature 092 acceptance", () => {
  test("UAT 5 — after deploy, comment-driven lines stay in their section, comments untouched", async ({ page }) => {
    await login(page);
    await openClientsTab(page);

    for (const [name, section, comment] of [
      [M.mig_check, "check", "לבדוק"],
      [M.mig_active, "active", "לקוח פעיל"],
      [M.mig_closed, "settled", "לסגור"],
    ] as [string, Section, string][]) {
      await focusClient(page, name);
      const row = await expectInSection(page, name, section);
      await row.getByText(name, { exact: true }).first().click(); // expand
      await expect(row.getByPlaceholder("הנחיות תפעול / הערות ללקוח...")).toHaveValue(comment);
    }
    // the closed line shows its REAL numbers (bugfix-068), not agreed == paid
    const closed = rowOf(page, M.mig_closed);
    await expect(closed).toContainText("₪5,000.00");
    await expect(closed).toContainText("₪1,000.00");

    expect(readJson(M.comments_file)[M.mig_closed]).toBe("לסגור");
    expect(readJson(M.migrations_file)).toHaveProperty("092_comment_line_status");
  });

  test("UAT 1 — לסגור moves a debt line to green without faking its numbers; לפתוח sends it back", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await focusClient(page, M.debt_client);
    await expectInSection(page, M.debt_client, "debt");

    await lineBtn(page, "close", M.debt_client).click();
    const green = await expectInSection(page, M.debt_client, "settled");
    await expect(green).toContainText("₪10,000.00");
    await expect(green).toContainText("₪2,000.00");

    await lineBtn(page, "reopen", M.debt_client).click();
    const red = await expectInSection(page, M.debt_client, "debt");
    await expect(red).toContainText("₪10,000.00");
    await expect(red).toContainText("₪2,000.00");
  });

  test("UAT 2 — reopening a fully paid green line moves it to לקוחות פעילים", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await focusClient(page, M.paid_client);
    await expectInSection(page, M.paid_client, "settled");

    await lineBtn(page, "reopen", M.paid_client).click();
    await expectInSection(page, M.paid_client, "active");
  });

  test("UAT 3 — לבדוק / לקוח פעיל buttons move the line; comment keywords no longer do", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await focusClient(page, M.target_a);
    await expectInSection(page, M.target_a, "debt");

    await lineBtn(page, "check", M.target_a).click();
    await expectInSection(page, M.target_a, "check");

    await lineBtn(page, "active", M.target_a).click();
    await expectInSection(page, M.target_a, "active");

    // typing a routing keyword into the comment changes nothing
    for (const word of ["לבדוק", "לסגור"]) {
      const row = await expectInSection(page, M.target_a, "active");
      await row.getByText(M.target_a, { exact: true }).first().click(); // expand (collapsed after reload)
      await row.getByPlaceholder("הנחיות תפעול / הערות ללקוח...").fill(word);
      await row.getByText("💾", { exact: true }).click();
      await expect.poll(() => readJson(M.comments_file)[M.target_a]).toBe(word);
      await page.reload();
      await openClientsTab(page);
      await focusClient(page, M.target_a);
      await expectInSection(page, M.target_a, "active");
    }
  });

  test("UAT 4 — a gray (past) line shows none of the four buttons", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await focusClient(page, M.past_client);
    await expectInSection(page, M.past_client, "past");
    for (const action of ["close", "reopen", "check", "active"]) {
      await expect(lineBtn(page, action, M.past_client)).toHaveCount(0);
    }
  });

  test("UAT 6 — each no-name event is its own Unknown-<event_id> line; mapping moves exactly that event", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await revealUnmatched(page);
    const [u1, u2, u3] = M.unknown_events as { event_id: string; amount: number }[];
    for (const u of [u1, u2, u3]) {
      await expect(unmatchedRow(page, `Unknown-${u.event_id}`)).toBeVisible();
    }

    await mapUnmatched(page, `Unknown-${u1.event_id}`, M.target_a);
    await mapUnmatched(page, `Unknown-${u2.event_id}`, M.target_b);

    await focusClient(page, M.target_a);
    await expect(await expectInSection(page, M.target_a, "active")).toContainText("₪500.00");
    await focusClient(page, M.target_b);
    await expect(await expectInSection(page, M.target_b, "debt")).toContainText("₪1,200.00");
    await focusClient(page, "");

    // a fourth no-name event arrives with an OLDER date; reload the ledger like the Events tab does
    const late = M.late_unknown_event as { event_id: string; amount: number; event_datetime: string };
    writeFileSync(
      path.join(M.events_dir, `${late.event_id}.json`),
      JSON.stringify({
        event_id: late.event_id, source_type: "חשבונית", event_subtype: "חשבונית מס קבלה",
        client_name: null, amount: late.amount, description: "e2e-092-late-unknown",
        event_datetime: late.event_datetime,
      }),
      "utf-8"
    );
    const token = await page.evaluate(() => localStorage.getItem("denidin_ledger_token"));
    const reload = await page.request.get(`${CLIENTS_API}/api/events?refresh=1`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(reload.ok()).toBeTruthy();
    await page.reload();
    await openClientsTab(page);
    await revealUnmatched(page);

    await expect(unmatchedRow(page, `Unknown-${late.event_id}`)).toBeVisible();
    await expect(unmatchedRow(page, `Unknown-${u3.event_id}`)).toBeVisible();
    await expect(unmatchedRow(page, `Unknown-${u1.event_id}`)).toHaveCount(0);
    expect(readJson(M.mapping_file)[`Unknown-${u1.event_id}`]).toBe(M.target_a);
    expect(readJson(M.mapping_file)[`Unknown-${u2.event_id}`]).toBe(M.target_b);

    // unlinking the first one returns it to the list
    await focusClient(page, M.target_a);
    const row = await expectInSection(page, M.target_a, "active");
    await row.getByText(M.target_a, { exact: true }).first().click();
    await page.getByTestId(`unlink-Unknown-${u1.event_id}`).click();
    await expect(page.getByTestId(`unlink-Unknown-${u1.event_id}`)).toHaveCount(0);
    await focusClient(page, "");
    await revealUnmatched(page);
    await expect(unmatchedRow(page, `Unknown-${u1.event_id}`)).toBeVisible();
  });

  test("UAT 7 — unlinking a name mapping reverts totals and returns it to the list with its note", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await revealUnmatched(page);
    await mapUnmatched(page, M.yisrael_raw_name, M.target_b);

    await focusClient(page, M.target_b);
    let row = await expectInSection(page, M.target_b, "debt");
    await expect(row).toContainText("₪1,900.00"); // 1,200 (UAT 6) + 700
    await row.getByText(M.target_b, { exact: true }).first().click();
    await expect(page.getByTestId(`alias-${M.yisrael_raw_name}`)).toBeVisible();

    await page.getByTestId(`unlink-${M.yisrael_raw_name}`).click();
    await expect(page.getByTestId(`alias-${M.yisrael_raw_name}`)).toHaveCount(0);
    row = await expectInSection(page, M.target_b, "debt");
    await expect(row).toContainText("₪1,200.00");
    await expect(row).not.toContainText(M.yisrael_raw_name);
    expect(readJson(M.mapping_file)[M.yisrael_raw_name]).toBeUndefined();

    await focusClient(page, "");
    await revealUnmatched(page);
    const back = unmatchedRow(page, M.yisrael_raw_name);
    await expect(back).toBeVisible();
    await expect(back.getByPlaceholder("הערה...")).toHaveValue(M.yisrael_note);
  });

  test("UAT 8 — הסר מהרשימה removes a name and it stays gone after a refresh", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await revealUnmatched(page);
    await expect(unmatchedRow(page, M.hide_raw_name)).toBeVisible();

    await page.getByTestId(`hide-unmatched-${M.hide_raw_name}`).click();
    await expect(unmatchedRow(page, M.hide_raw_name)).toHaveCount(0);
    expect(readJson(M.hidden_file)).toContain(M.hide_raw_name);

    await page.getByTestId("clients-refresh").click();
    await expect(page.getByTestId("clients-loading")).toHaveCount(0);
    await page.reload();
    await openClientsTab(page);
    await revealUnmatched(page);
    await expect(unmatchedRow(page, M.hide_raw_name)).toHaveCount(0);
  });

  test("UAT 9 — Escape closes the client dropdown and nothing is mapped", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await revealUnmatched(page);
    const before = JSON.stringify(readJson(M.mapping_file));
    const raw = `Unknown-${(M.unknown_events as { event_id: string }[])[2].event_id}`;

    await unmatchedRow(page, raw).getByTestId("unmatched-picker-input").fill(M.target_a);
    await expect(page.getByTestId("unmatched-picker-list")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("unmatched-picker-list")).toHaveCount(0);
    await expect(unmatchedRow(page, raw)).toBeVisible();
    expect(JSON.stringify(readJson(M.mapping_file))).toBe(before);
  });
});
