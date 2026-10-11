import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { Page, expect } from "@playwright/test";
import { BASE, EMPTY_API, FULL_API } from "../playwright.config";

const __dir = path.dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = path.join(__dir, "..", ".fixture");

export interface FixtureManifest {
  password: string;
  root: string;
  all_event_ids: string[];
  within_7_days: string[];
  within_14_days: string[];
  boundary_included_id: string;
  outside_7_within_14_id: string;
  same_date_pair: [string, string];
  null_amount_id: string;
  negative_amount_id: string;
  unknown_type_id: string;
  no_conversation_id: string;
  unresolvable_context_id: string;
  stale_session_id: string;
  full_history_id: string;
  client_prefix: { query: string; expected: string[] };
  anchor_event: { id: string; lookback_10: string[]; lookback_5: string[] };
}

let _cache: { full: FixtureManifest; empty: { password: string; root: string } } | null = null;
export function manifest() {
  if (!_cache) {
    _cache = JSON.parse(readFileSync(path.join(FIXTURE_DIR, "manifest.json"), "utf-8"));
  }
  return _cache!;
}
export const FULL = () => manifest().full;
export const PASSWORD = () => manifest().full.password;

/** Read raw event JSON straight from the seeded fixture — so expected values in assertions
 *  come from the same files the backend serves, never a hand-copied guess. */
export function readEvent(id: string): Record<string, any> {
  return JSON.parse(readFileSync(path.join(FULL().root, "events", `${id}.json`), "utf-8"));
}
export function allEvents(): Record<string, any>[] {
  return FULL().all_event_ids.map(readEvent);
}

function daysBetween(dateStr: string): number {
  // event dates in fixtures are DD/MM/YYYY (event_date) or "DD/MM/YYYY HH:MM" (event_datetime)
  const head = dateStr.split(" ")[0];
  const [dd, mm, yyyy] = head.split("/").map(Number);
  const d = new Date(yyyy, mm - 1, dd);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((today.getTime() - d.getTime()) / 86_400_000);
}
export function eventDateField(rec: Record<string, any>): string {
  return rec.txn_date || rec.event_datetime || rec.event_date || "";
}
export function idsWithinDays(days: number): string[] {
  return allEvents()
    .filter((e) => {
      const f = eventDateField(e);
      return f && daysBetween(f) <= days && daysBetween(f) >= 0;
    })
    .map((e) => e.event_id);
}
export function idsBySourceType(t: string, withinDays = 7): string[] {
  const win = new Set(idsWithinDays(withinDays));
  return allEvents().filter((e) => win.has(e.event_id) && e.source_type === t).map((e) => e.event_id);
}

// --- page helpers ---------------------------------------------------------------------

export async function gotoApp(page: Page, which: "full" | "empty" = "full") {
  const api = which === "full" ? FULL_API : EMPTY_API;
  await page.goto(`${BASE}/?api=${encodeURIComponent(api)}`);
}

export async function login(page: Page, which: "full" | "empty" = "full", password?: string) {
  await gotoApp(page, which);
  await expect(page.getByTestId("password-input")).toBeVisible();
  await page.getByTestId("password-input").fill(password ?? manifest().full.password);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-ready")).toBeVisible();
  await expect(page.getByTestId("loading")).toHaveCount(0);
}

export function rows(page: Page) {
  return page.getByTestId(/^event-row-/);
}
export function row(page: Page, id: string) {
  return page.getByTestId(`event-row-${id}`);
}
export async function rowIds(page: Page): Promise<string[]> {
  return rows(page).evaluateAll((els) =>
    els
      .map((e) => (e.getAttribute("data-testid") || "").replace(/^event-row-/, ""))
      .filter(Boolean)
  );
}
export async function expandRow(page: Page, id: string) {
  await page.getByTestId(`expand-toggle-${id}`).click();
  await expect(page.getByTestId(`detail-panel-${id}`)).toBeVisible();
}
export async function openSettings(page: Page) {
  await page.getByTestId("settings-gear").click();
  await expect(page.getByTestId("settings-panel")).toBeVisible();
}
export async function setDaysBack(page: Page, n: number) {
  await openSettings(page);
  const input = page.getByTestId("setting-days-back");
  await input.fill(String(n));
  await page.getByTestId("settings-close").click();
  await expect(page.getByTestId("settings-panel")).toHaveCount(0);
}

/** Set a MultiSelect so that EXACTLY `labels` are checked. Deterministic: reads each option's
 *  live aria-checked and only clicks the ones that need to flip. */
export async function msOnly(page: Page, which: "type" | "subtype", labels: string[]) {
  const base = `filter-${which}`;
  const want = new Set(labels);
  await page.getByTestId(base).click();
  await expect(page.getByTestId(`${base}-menu`)).toBeVisible();
  const opts = page.locator(`[data-testid^="${base}-opt-"]:not([data-testid="${base}-opt-all"])`);
  const n = await opts.count();
  for (let i = 0; i < n; i++) {
    const o = opts.nth(i);
    const label = (await o.getAttribute("data-testid"))!.replace(`${base}-opt-`, "");
    const checked = (await o.getAttribute("aria-checked")) === "true";
    const disabled = (await o.getAttribute("aria-disabled")) === "true";
    if (disabled) continue;
    if (want.has(label) !== checked) await o.click();
  }
  await page.getByTestId(base).click(); // close
}
export async function msToggle(page: Page, which: "type" | "subtype", label: string) {
  const base = `filter-${which}`;
  await page.getByTestId(base).click();
  await page.getByTestId(`${base}-opt-${label}`).click();
  await page.getByTestId(base).click();
}

export async function applyFilters(page: Page) {
  await page.getByTestId("filter-apply").click();
}
