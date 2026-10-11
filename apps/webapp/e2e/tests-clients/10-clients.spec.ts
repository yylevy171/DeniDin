/**
 * Feature 087 — Clients tab acceptance (spec.md UAT-1/2/3) plus the "served from memory,
 * reload only on refresh" behavior. Real stack, no mocking: see playwright.clients.config.ts.
 *
 * Run: npx playwright test -c playwright.clients.config.ts
 *
 * Serial on purpose: UAT-2 and UAT-3 write to the fixture's webapp_data/clients files, and
 * UAT-3 (a mapping) changes the report the other tests read, so it runs last.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect, Page } from "@playwright/test";
import { CLIENTS_API, CLIENTS_BASE } from "../playwright.clients.config";

test.describe.configure({ mode: "serial" });

const __dir = path.dirname(fileURLToPath(import.meta.url));
const M = JSON.parse(
  readFileSync(path.join(__dir, "..", ".fixture", "clients", "manifest.json"), "utf-8")
) as {
  password: string;
  official_client: string;
  unmatched_raw_name: string;
  agreement_marker: string;
  invoice_marker: string;
  unmatched_marker: string;
  comments_file: string;
  mapping_file: string;
};

const readJson = (file: string): Record<string, string> => JSON.parse(readFileSync(file, "utf-8"));

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

const clientRow = (page: Page) => page.getByTestId(`client-row-${M.official_client}`);
const unmatchedRow = (page: Page) => page.getByTestId(`unmatched-row-${M.unmatched_raw_name}`);

// Sections and the unmatched block are collapsed accordions. Open only the ones that can hold
// the seeded client - never "לקוח עבר" (past), which renders thousands of Morning clients.
const CLIENT_SECTIONS = ["חוב פתוח", "לקוח פעיל", "לבדוק", "חסר הסכם", "סגור - שולם"];
const UNMATCHED_SECTION = "שמות לקוחות לתייג";

async function revealClient(page: Page) {
  for (const label of CLIENT_SECTIONS) {
    if (await clientRow(page).count()) return;
    const header = page.getByText(label, { exact: true });
    if (await header.count()) await header.first().click();
  }
  await expect(clientRow(page)).toBeVisible();
}

async function revealUnmatched(page: Page) {
  if (!(await unmatchedRow(page).count())) {
    await page.getByText(UNMATCHED_SECTION, { exact: true }).first().click();
  }
  await expect(unmatchedRow(page)).toBeVisible();
}

async function expandClient(page: Page) {
  await revealClient(page);
  await clientRow(page).getByText(M.official_client, { exact: true }).first().click();
}

test.describe("UAT-1: viewing the client status dashboard", () => {
  test("Clients tab lists the Morning clients with their ledger totals", async ({ page }) => {
    await login(page);
    await openClientsTab(page);

    // a real, non-empty client list from the Morning sandbox
    await expect(page.getByTestId("clients-count")).not.toHaveText(/^0 /);
    await revealClient(page);

    // the seeded agreement (1,000) shows in the row's agreed column
    await expect(clientRow(page)).toContainText("₪1,000.00");

    // expanding lists the ledger events behind the totals, each with its own amount
    await expandClient(page);
    await expect(clientRow(page)).toContainText(M.agreement_marker);
    await expect(clientRow(page)).toContainText(M.invoice_marker);
    await expect(clientRow(page)).toContainText("₪400.00");
  });

  test("a ledger name that matches no Morning client is listed as unmatched", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await revealUnmatched(page);
    await expect(unmatchedRow(page)).toContainText(M.unmatched_marker);
  });
});

test.describe("served from memory - reload only on refresh", () => {
  test("switching tabs never refetches the clients (or events) data", async ({ page }) => {
    await login(page);
    const clientsCalls: string[] = [];
    const eventsCalls: string[] = [];
    page.on("request", (r) => {
      const u = r.url();
      if (u.includes("/api/clients") && r.method() === "GET") clientsCalls.push(u);
      if (u.includes("/api/events?")) eventsCalls.push(u);
    });

    await openClientsTab(page);
    expect(clientsCalls, clientsCalls.join("\n")).toHaveLength(1);

    for (let i = 0; i < 3; i++) {
      await page.getByTestId("tab-events").click();
      await expect(page.getByTestId("event-list")).toBeVisible();
      await page.getByTestId("tab-clients").click();
      await expect(page.getByTestId("clients-view")).toBeVisible();
    }
    expect(clientsCalls, clientsCalls.join("\n")).toHaveLength(1); // still just the first load
    expect(eventsCalls.length).toBe(0); // events view was mounted at login, never refetched
  });

  test("the refresh button is a hard reload (refresh=1) and keeps the list", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    const reqPromise = page.waitForRequest((r) => r.url().includes("/api/clients?refresh=1"));
    await page.getByTestId("clients-refresh").click();
    await reqPromise;
    await expect(page.getByTestId("clients-loading")).toHaveCount(0);
    await expect(page.getByText("חוב פתוח", { exact: true })).toBeVisible(); // list still there
  });
});

test.describe("UAT-2: updating client comments", () => {
  const COMMENT = "סוכם תשלום ב-24 לחודש";

  test("a comment saves, shows in the row without a page reload, and persists", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await expandClient(page);

    const field = clientRow(page).getByPlaceholder("הנחיות תפעול / הערות ללקוח...");
    await field.fill(COMMENT);
    await clientRow(page).getByText("💾", { exact: true }).click();

    // persisted by the backend...
    await expect.poll(() => readJson(M.comments_file)[M.official_client]).toBe(COMMENT);
    // ...and reflected in the row right away, no navigation
    await expect(field).toHaveValue(COMMENT);

    // survives a full page reload
    await page.reload();
    await openClientsTab(page);
    await expandClient(page);
    await expect(clientRow(page).getByPlaceholder("הנחיות תפעול / הערות ללקוח...")).toHaveValue(COMMENT);
  });
});

test.describe("UAT-3: aliasing an unresolved name to a Morning client", () => {
  test("the mapping is persisted and the raw name becomes an alias of the Morning client", async ({ page }) => {
    await login(page);
    await openClientsTab(page);
    await revealUnmatched(page);

    await unmatchedRow(page).getByTestId("unmatched-picker-input").fill(M.official_client);
    await page.getByTestId("unmatched-picker-list").getByText(M.official_client, { exact: true }).first().click();

    // persisted
    await expect.poll(() => readJson(M.mapping_file)[M.unmatched_raw_name]).toBe(M.official_client);
    // no longer unmatched, and now listed as an alias on the Morning client's row
    await expect(unmatchedRow(page)).toHaveCount(0);
    await revealClient(page);
    await expect(clientRow(page)).toContainText(M.unmatched_raw_name);

    // and the mapping holds after a full reload
    await page.reload();
    await openClientsTab(page);
    await expect(unmatchedRow(page)).toHaveCount(0);
    await revealClient(page);
    await expect(clientRow(page)).toContainText(M.unmatched_raw_name);
  });
});
