/**
 * Feature 089 — Agreements section of the Clients tab. One test per APPROVED acceptance
 * scenario tagged [UI] in specs/repo/features/089-ui-agreement-edits/user-stories.md
 * (UAT 1.1-1.4, 2.1-2.6, 3.1-3.6, 4.1, 6.1, plus the UI halves of 4.2 / 4.3).
 *
 * Real stack, no stand-in server: see playwright.agreements.config.ts. Every test that changes
 * data also asserts the three things the UAT preamble requires: the Agreements DB (read back
 * through the real API), a new revision, and the ledger effect on the real ledger files - and
 * that nothing ELSE was written to the ledger.
 *
 * Run: npx playwright test -c playwright.agreements.config.ts
 *
 * Serial on purpose: tests share the seeded DB, in the order below. Ledger files created by a
 * test are removed afterwards (a minute only has ten event-id slots per source letter; the
 * product refuses a write beyond that), seeded files are never touched.
 */
import { readdirSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect, Page, APIRequestContext } from "@playwright/test";
import { AGREEMENTS_API, AGREEMENTS_BASE } from "../playwright.agreements.config";

test.describe.configure({ mode: "serial" });

const __dir = path.dirname(fileURLToPath(import.meta.url));
const M = JSON.parse(readFileSync(path.join(__dir, "..", ".fixture", "agreements", "manifest.json"), "utf-8")) as Record<string, any>;
const C = M.clients as Record<string, string>;
const EVENTS: string = M.events_dir;

// ---------------------------------------------------------------- ledger -----------------
const eventFiles = () => readdirSync(EVENTS).filter((f) => f.endsWith(".json")).sort();
let before = new Set<string>();
test.beforeEach(() => {
  before = new Set(eventFiles());
});
test.afterEach(() => {
  for (const f of eventFiles()) if (!before.has(f)) rmSync(path.join(EVENTS, f));
});
/** Ledger events written during the current test, in write order. */
const newEvents = (): any[] =>
  eventFiles().filter((f) => !before.has(f)).map((f) => JSON.parse(readFileSync(path.join(EVENTS, f), "utf-8")));

// ---------------------------------------------------------------- api (read back) --------
async function token(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${AGREEMENTS_API}/api/auth/login`, { data: { password: M.password } });
  return (await r.json()).token;
}
async function agreementsOf(request: APIRequestContext, client: string): Promise<any[]> {
  const r = await request.get(`${AGREEMENTS_API}/api/clients/${encodeURIComponent(client)}/agreements`, {
    headers: { Authorization: `Bearer ${await token(request)}` },
  });
  return (await r.json()).agreements;
}
async function revisionsOf(request: APIRequestContext, agreementId: string): Promise<any[]> {
  const r = await request.get(`${AGREEMENTS_API}/api/agreements/${encodeURIComponent(agreementId)}/revisions`, {
    headers: { Authorization: `Bearer ${await token(request)}` },
  });
  return (await r.json()).revisions;
}
const comp = (agreement: any, label: string) => agreement.components.find((c: any) => c.label === label);
const byTitle = (list: any[], title: string) => list.find((a) => a.title === title);

// ---------------------------------------------------------------- ui helpers -------------
async function login(page: Page) {
  await page.goto(`${AGREEMENTS_BASE}/?api=${encodeURIComponent(AGREEMENTS_API)}`);
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
const row = (page: Page, name: string) => page.getByTestId(`client-row-${name}`);
/** Show one client's row (opening its section accordion if collapsed). */
async function showRow(page: Page, name: string) {
  await page.getByTestId("clients-search").fill(name);
  if (!(await row(page, name).count())) await page.locator('[data-testid^="section-header-"]').first().click();
  await expect(row(page, name)).toBeVisible();
}
async function openClient(page: Page, name: string) {
  await login(page);
  await openClientsTab(page);
  await showRow(page, name);
  await row(page, name).getByText(name, { exact: true }).first().click();
  await expect(page.getByTestId("agreements-section")).toBeVisible();
}
const btn = (page: Page, id: string) => page.getByTestId(id);
async function expectDisabled(page: Page, id: string) {
  await expect(btn(page, id)).toHaveAttribute("aria-disabled", "true");
}

// ================================================================ User Story 1 =============
test.describe("US1 - view agreements and components", () => {
  test("UAT 1.1 - the Agreements section appears in the client's details", async ({ page }) => {
    await openClient(page, C.view);
    await expect(page.getByTestId("agreements-section")).toContainText("הסכמים");
    expect(newEvents()).toHaveLength(0);
  });

  test("UAT 1.2 - agreement details and nested components are visible without drilling in", async ({ page, request }) => {
    await openClient(page, C.view);
    const a = byTitle(await agreementsOf(request, C.view), M.titles.view);
    const id = a.agreement_id;
    await expect(page.getByTestId(`agreement-title-${id}`)).toHaveText(M.titles.view);
    await expect(page.getByTestId(`agreement-payer-${id}`)).toContainText("ישראל ישראלי");
    await expect(page.getByTestId(`agreement-partner-${id}`)).toContainText("עו״ד כהן");
    await expect(page.getByTestId(`agreement-partner-percent-${id}`)).toContainText("25%");
    await expect(page.getByTestId(`agreement-status-${id}`)).toHaveText("פעיל");
    const retainer = comp(a, "ריטיינר").component_key;
    await expect(page.getByTestId(`component-label-${retainer}`)).toHaveText("ריטיינר");
    await expect(page.getByTestId(`component-amount-${retainer}`)).toContainText("5,000");
    await expect(page.getByTestId(`component-status-${retainer}`)).toHaveText("פעיל");
    const success = comp(a, "שכר הצלחה").component_key;
    await expect(page.getByTestId(`component-status-${success}`)).toHaveText("ממתין");
    expect(newEvents()).toHaveLength(0);
  });

  test("UAT 1.3 - hours-worked lines are not components but still count in the agreed total", async ({ page, request }) => {
    await openClient(page, C.view);
    const a = byTitle(await agreementsOf(request, C.view), M.titles.view);
    await expect(page.locator('[data-testid^="component-label-"]')).toHaveCount(a.components.length);
    await expect(page.getByTestId("agreements-section")).not.toContainText("שעות עבודה");
    await expect(row(page, C.view)).toContainText("₪9,000.00"); // 5,000 + 3,000 + 1,000 hours
  });

  test("UAT 1.4 - a client with no agreements shows an empty state and the new-agreement button", async ({ page }) => {
    await openClient(page, C.empty);
    await expect(page.getByTestId("agreements-empty")).toBeVisible();
    await expect(page.getByTestId("agreement-new")).toBeVisible();
  });
});

// ================================================================ User Story 6 =============
test.describe("US6 - agreed total follows the Agreements DB", () => {
  test("UAT 6.1 - cancelling a component lowers the agreed total (9,000 -> 6,000)", async ({ page, request }) => {
    await openClient(page, C.view);
    await expect(row(page, C.view)).toContainText("₪9,000.00");
    const a = byTitle(await agreementsOf(request, C.view), M.titles.view);
    await btn(page, `component-cancel-${comp(a, "שכר הצלחה").component_key}`).click();
    await showRow(page, C.view);
    await expect(row(page, C.view)).toContainText("₪6,000.00");
    const events = newEvents();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ component_label: "שכר הצלחה", component_status: "Cancelled", event_subtype: "יצירה" });
  });
});

// ================================================================ User Story 4 =============
test.describe("US4 - revision history and cross-channel consistency", () => {
  test("UAT 4.1 / 4.2 (UI half) - history lists the WhatsApp edit then the UI edit, in order", async ({ page, request }) => {
    await openClient(page, C.view);
    const a = byTitle(await agreementsOf(request, C.view), M.titles.view);
    const key = comp(a, "ריטיינר").component_key;
    await btn(page, `component-edit-${key}`).click();
    await page.getByTestId(`component-edit-${key}-amount`).fill("1000");
    await page.getByTestId(`component-edit-${key}-save`).click();
    await expect(page.getByTestId(`component-amount-${key}`)).toContainText("1,000");
    // 4.2: the DB (what the bot reads) now holds 1,000 from the latest revision
    expect(comp(byTitle(await agreementsOf(request, C.view), M.titles.view), "ריטיינר").amount).toBe(1000);
    await btn(page, `agreement-history-${a.agreement_id}`).click();
    const actors = await page.locator('[data-testid^="revision-actor-"]').allTextContents();
    // chronological: the seeded WhatsApp edit appears, and the UI edit just made comes after it
    expect(actors).toContain("בוט הוואטסאפ");
    expect(actors.indexOf("בוט הוואטסאפ")).toBeLessThan(actors.length - 1);
    expect(actors[actors.length - 1]).toBe("ממשק הווב");
    const events = newEvents();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ component_label: "ריטיינר", amount: 1000 });
  });
});

// ================================================================ User Story 2 =============
test.describe("US2 - edit agreements and components", () => {
  test("UAT 2.1 - the agreement edit dialog exposes only payer / partner / partner %", async ({ page, request }) => {
    await openClient(page, C.edit);
    const a = (await agreementsOf(request, C.edit))[0];
    const revisionsBefore = (await revisionsOf(request, a.agreement_id)).length;
    await btn(page, `agreement-edit-${a.agreement_id}`).click();
    await expect(page.getByTestId("agreement-edit-form")).toBeVisible();
    await expect(page.getByTestId("agreement-edit-title")).toHaveCount(0);
    await expect(page.locator('[data-testid^="agreement-edit-component-"]')).toHaveCount(0);
    await page.getByTestId("agreement-edit-payer_name").fill("חברה בע״מ");
    await page.getByTestId("agreement-edit-partner_name").fill("עו״ד לוי");
    await page.getByTestId("agreement-edit-partner_percent").fill("30");
    await page.getByTestId("agreement-edit-save").click();
    await expect(page.getByTestId(`agreement-payer-${a.agreement_id}`)).toContainText("חברה בע״מ");
    const after = (await agreementsOf(request, C.edit))[0];
    expect(after.components).toEqual(a.components); // components untouched
    expect((await revisionsOf(request, a.agreement_id)).length).toBe(revisionsBefore + 1);
    const events = newEvents();
    expect(events).toHaveLength(a.components.length); // one per component
    for (const e of events) expect(e).toMatchObject({ payer_name: "חברה בע״מ", split_partner: "עו״ד לוי", split_percent: 30 });
  });

  test("UAT 2.2 - editing one component changes only that component", async ({ page, request }) => {
    await openClient(page, C.edit);
    const a = (await agreementsOf(request, C.edit))[0];
    const key = comp(a, "ריטיינר").component_key;
    await btn(page, `component-edit-${key}`).click();
    for (const f of ["label", "description", "amount", "percent", "percent_base", "trigger_condition", "txn_date"]) {
      await expect(page.getByTestId(`component-edit-${key}-${f}`)).toBeVisible();
    }
    await page.getByTestId(`component-edit-${key}-amount`).fill("6000");
    await page.getByTestId(`component-edit-${key}-save`).click();
    await expect(page.getByTestId(`component-amount-${key}`)).toContainText("6,000");
    const after = (await agreementsOf(request, C.edit))[0];
    expect(comp(after, "ריטיינר").amount).toBe(6000);
    for (const label of ["שכר הצלחה", "הוצאות"]) expect(comp(after, label)).toEqual(comp(a, label));
    const events = newEvents();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ component_label: "ריטיינר", amount: 6000, event_subtype: "יצירה", component_status: "Active" });
  });

  test("UAT 2.2b - a wording-only edit still writes a ledger event", async ({ page, request }) => {
    await openClient(page, C.edit);
    const a = (await agreementsOf(request, C.edit))[0];
    const key = comp(a, "ריטיינר").component_key;
    await btn(page, `component-edit-${key}`).click();
    await page.getByTestId(`component-edit-${key}-description`).fill("ניסוח חדש לריטיינר");
    await page.getByTestId(`component-edit-${key}-save`).click();
    await expect.poll(async () => comp((await agreementsOf(request, C.edit))[0], "ריטיינר").description).toBe("ניסוח חדש לריטיינר");
    const events = newEvents();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ description: "ניסוח חדש לריטיינר", component_label: "ריטיינר" });
  });

  test("UAT 2.3 - adding a component requires its fields; a valid save defaults to Pending with a trigger", async ({ page, request }) => {
    await openClient(page, C.edit);
    const a = (await agreementsOf(request, C.edit))[0];
    const form = `component-add-${a.agreement_id}`;
    await btn(page, form).click();
    await page.getByTestId(`${form}-save`).click();
    await expect(page.getByTestId(`${form}-error`)).toBeVisible();
    expect(newEvents()).toHaveLength(0);
    await page.getByTestId(`${form}-label`).fill("תוספת דיון");
    await page.getByTestId(`${form}-amount`).fill("1500");
    await page.getByTestId(`${form}-trigger_condition`).fill("על כל דיון נוסף");
    await page.getByTestId(`${form}-save`).click();
    await expect.poll(async () => comp((await agreementsOf(request, C.edit))[0], "תוספת דיון")?.status).toBe("Pending");
    const events = newEvents();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ component_label: "תוספת דיון", amount: 1500, component_status: "Pending" });
  });

  test("UAT 2.4 - creating a new agreement needs at least one component", async ({ page, request }) => {
    await openClient(page, C.new);
    await btn(page, "agreement-new").click();
    await page.getByTestId("agreement-new-title").fill("הסכם חדש לבדיקה");
    await page.getByTestId("agreement-new-save").click(); // zero components -> refused
    await expect(page.getByTestId("agreement-new-error")).toBeVisible();
    expect(await agreementsOf(request, C.new)).toHaveLength(0);
    await page.getByTestId("agreement-new-component-label").fill("ריטיינר");
    await page.getByTestId("agreement-new-component-amount").fill("4000");
    await page.getByTestId("agreement-new-save").click();
    await expect.poll(async () => (await agreementsOf(request, C.new)).length).toBe(1);
    const created = (await agreementsOf(request, C.new))[0];
    expect(created.components).toHaveLength(1);
    expect(created.components[0].status).toBe("Active");
    const events = newEvents();
    expect(events).toHaveLength(1);
    expect(events[0].original_client_name).toBeNull();
  });

  test("UAT 2.5 - deleting a component asks for confirmation and writes a ביטול event", async ({ page, request }) => {
    await openClient(page, C.edit);
    const a = (await agreementsOf(request, C.edit))[0];
    const target = comp(a, "הוצאות");
    await btn(page, `component-delete-${target.component_key}`).click();
    await btn(page, `component-confirm-no-${target.component_key}`).click(); // cancelled: nothing happens
    expect(comp((await agreementsOf(request, C.edit))[0], "הוצאות")).toBeTruthy();
    expect(newEvents()).toHaveLength(0);
    await btn(page, `component-delete-${target.component_key}`).click();
    await btn(page, `component-confirm-yes-${target.component_key}`).click();
    await expect(page.getByTestId(`component-${target.component_key}`)).toHaveCount(0);
    const after = (await agreementsOf(request, C.edit))[0];
    expect(comp(after, "הוצאות")).toBeUndefined();
    expect(comp(after, "ריטיינר")).toBeTruthy(); // siblings untouched
    const events = newEvents();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ event_subtype: "ביטול", reference: target.origin_event_id });
  });

  test("UAT 2.6 - closed components and components of closed agreements cannot be edited", async ({ page, request }) => {
    await openClient(page, C.closed);
    const list = await agreementsOf(request, C.closed);
    const open = byTitle(list, "הסכם עם רכיבים סגורים");
    const dead = byTitle(list, "הסכם מבוטל");
    for (const label of ["שולם", "בוטל"]) {
      const key = comp(open, label).component_key;
      await expectDisabled(page, `component-edit-${key}`);
      await expectDisabled(page, `component-delete-${key}`);
    }
    await expect(btn(page, `component-edit-${comp(open, "פתוח").component_key}`)).not.toHaveAttribute("aria-disabled", "true");
    const deadKey = dead.components[0].component_key;
    await expectDisabled(page, `component-edit-${deadKey}`);
    await expectDisabled(page, `component-delete-${deadKey}`);
    expect(newEvents()).toHaveLength(0);
  });
});

// ================================================================ User Story 3 =============
test.describe("US3 - component and agreement lifecycle", () => {
  test("UAT 3.1 - a component with a trigger starts Pending, one without starts Active", async ({ page, request }) => {
    await openClient(page, C.edit);
    const a = (await agreementsOf(request, C.edit))[0];
    for (const [label, trigger] of [["גמיש", ""], ["מותנה", "אם נגיע לבית משפט"]]) {
      const form = `component-add-${a.agreement_id}`;
      await btn(page, form).click();
      await page.getByTestId(`${form}-label`).fill(label);
      await page.getByTestId(`${form}-amount`).fill("100");
      if (trigger) await page.getByTestId(`${form}-trigger_condition`).fill(trigger);
      await page.getByTestId(`${form}-save`).click();
      await expect.poll(async () => !!comp((await agreementsOf(request, C.edit))[0], label)).toBe(true);
    }
    const after = (await agreementsOf(request, C.edit))[0];
    expect(comp(after, "גמיש").status).toBe("Active");
    expect(comp(after, "מותנה").status).toBe("Pending");
    expect(newEvents().map((e) => e.component_status)).toEqual(["Active", "Pending"]);
  });

  test("UAT 3.2 - Mark Active moves a Pending component to Active", async ({ page, request }) => {
    await openClient(page, C.edit);
    const a = (await agreementsOf(request, C.edit))[0];
    const key = comp(a, "שכר הצלחה").component_key;
    await btn(page, `component-activate-${key}`).click();
    await expect(page.getByTestId(`component-status-${key}`)).toHaveText("פעיל");
    const after = (await agreementsOf(request, C.edit))[0];
    expect(comp(after, "שכר הצלחה").status).toBe("Active");
    expect(comp(after, "ריטיינר").status).toBe("Active");
    const events = newEvents();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ component_label: "שכר הצלחה", component_status: "Active" });
  });

  test("UAT 3.3 - Mark Completed locks an Active component", async ({ page, request }) => {
    await openClient(page, C.edit);
    const a = (await agreementsOf(request, C.edit))[0];
    const key = comp(a, "ריטיינר").component_key;
    await btn(page, `component-complete-${key}`).click();
    await expect(page.getByTestId(`component-status-${key}`)).toHaveText("הושלם");
    await expectDisabled(page, `component-edit-${key}`);
    const events = newEvents();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ component_label: "ריטיינר", component_status: "Completed" });
  });

  test("UAT 3.4 - Cancel locks a Pending component and is a status change, not a ביטול", async ({ page, request }) => {
    await openClient(page, C.edit);
    const a = (await agreementsOf(request, C.edit))[0];
    const key = comp(a, "תוספת דיון").component_key;
    await btn(page, `component-cancel-${key}`).click();
    await expect(page.getByTestId(`component-status-${key}`)).toHaveText("בוטל");
    await expectDisabled(page, `component-edit-${key}`);
    const events = newEvents();
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ component_label: "תוספת דיון", component_status: "Cancelled", event_subtype: "יצירה" });
  });

  test("UAT 3.5 - completing the agreement cascades per the decision and locks everything", async ({ page, request }) => {
    await openClient(page, C.cascade);
    const a = (await agreementsOf(request, C.cascade))[0];
    await btn(page, `agreement-complete-${a.agreement_id}`).click();
    await expect(page.getByTestId(`agreement-status-${a.agreement_id}`)).toHaveText("הושלם");
    const after = (await agreementsOf(request, C.cascade))[0];
    expect(after.status).toBe("Completed");
    expect(comp(after, "פעיל").status).toBe("Completed");  // Active -> Completed
    expect(comp(after, "ממתין").status).toBe("Cancelled"); // Pending -> Cancelled
    expect(comp(after, "שולם").status).toBe("Completed");  // already closed: unchanged
    for (const c of after.components) await expectDisabled(page, `component-edit-${c.component_key}`);
    // reopening a component of a still-closed agreement is not offered
    await expect(page.locator('[data-testid^="component-reopen-"]')).toHaveCount(0);
    const events = newEvents();
    expect(events).toHaveLength(after.components.length);
    for (const e of events) expect(e.agreement_status).toBe("Completed");
    expect(events.map((e) => e.component_status).sort()).toEqual(["Cancelled", "Completed", "Completed"]);
  });

  test("UAT 3.6 - reopening the agreement, then one component, unlocks only what was reopened", async ({ page, request }) => {
    await openClient(page, C.cascade);
    const a = (await agreementsOf(request, C.cascade))[0];
    await btn(page, `agreement-reopen-${a.agreement_id}`).click();
    await expect(page.getByTestId(`agreement-status-${a.agreement_id}`)).toHaveText("פעיל");
    let after = (await agreementsOf(request, C.cascade))[0];
    expect(after.status).toBe("Active");
    expect(comp(after, "ממתין").status).toBe("Cancelled"); // components stay as the close left them
    expect(comp(after, "פעיל").status).toBe("Completed");
    const agreementEvents = newEvents();
    expect(agreementEvents).toHaveLength(after.components.length);
    for (const e of agreementEvents) expect(e.agreement_status).toBe("Active");
    const key = comp(after, "ממתין").component_key;
    await btn(page, `component-reopen-${key}`).click();
    await expect(page.getByTestId(`component-status-${key}`)).toHaveText("פעיל");
    after = (await agreementsOf(request, C.cascade))[0];
    expect(comp(after, "ממתין").status).toBe("Active");
    expect(newEvents().filter((e) => e.component_label === "ממתין").pop()).toMatchObject({ component_status: "Active" });
  });
});

// ================================================================ UAT 4.3 (UI half) ========
test("UAT 4.3 (UI half) - an edit made elsewhere is what the UI shows after a reload (last write wins)", async ({ page, request }) => {
  await openClient(page, C.view);
  const a = byTitle(await agreementsOf(request, C.view), M.titles.view);
  const key = comp(a, "ריטיינר").component_key;
  await btn(page, `component-edit-${key}`).click();
  await page.getByTestId(`component-edit-${key}-amount`).fill("1200");
  await page.getByTestId(`component-edit-${key}-save`).click();
  await expect(page.getByTestId(`component-amount-${key}`)).toContainText("1,200");
  await page.reload(); // the session survives a reload; no second login
  await openClientsTab(page);
  await showRow(page, C.view);
  await row(page, C.view).getByText(C.view, { exact: true }).first().click();
  await expect(page.getByTestId(`component-amount-${key}`)).toContainText("1,200");
  const revisions = await revisionsOf(request, a.agreement_id);
  expect(revisions[revisions.length - 1].snapshot.amount).toBe(1200);
  expect(newEvents()).toHaveLength(1);
});
