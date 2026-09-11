/**
 * Component 4 — Row Expand (single). PLAYWRIGHT-TEST-PLAN.md §4.
 * Right panel = per-type field manifest (contracts/field-manifests.md).
 * Left panel = WhatsApp-style chat (human right / bot left), inclusive lookback window.
 */
import { test, expect, Page } from "@playwright/test";
import { login, row, rowIds, manifest, readEvent, setDaysBack } from "./_helpers";

async function expand(page: Page, id: string) {
  await page.getByTestId(`expand-toggle-${id}`).click();
  await expect(page.getByTestId(`detail-panel-${id}`)).toBeVisible();
}
async function collapse(page: Page, id: string) {
  await page.getByTestId(`expand-toggle-${id}`).click();
  await expect(page.getByTestId(`detail-panel-${id}`)).toHaveCount(0);
}
/** wait until the right panel has finished loading (fields OR unsupported OR unavailable) */
async function detailReady(page: Page, id: string) {
  await expect(page.getByTestId(`detail-panel-${id}`)).toBeVisible();
  await expect(page.getByTestId("detail-loading")).toHaveCount(0);
}
function msgs(page: Page, id: string) {
  return page.getByTestId(`context-panel-${id}`).getByTestId(/^chat-msg-/);
}
async function msgMeta(page: Page, id: string) {
  return msgs(page, id).evaluateAll((els) =>
    els.map((e) => {
      const lbl = e.getAttribute("aria-label") || "";
      return {
        id: (lbl.match(/id:(\S+)/) || [])[1] || "",
        side: (lbl.match(/side:(\S+)/) || [])[1] || "",
      };
    })
  );
}
function fieldKeys(page: Page, id: string) {
  return page
    .getByTestId(`detail-panel-${id}`)
    .getByTestId(/^detail-field-/)
    .evaluateAll((els) =>
      els.map((e) => (e.getAttribute("data-testid") || "").replace(/^detail-field-/, ""))
    );
}
async function fieldText(page: Page, id: string, key: string) {
  return (await page.getByTestId(`detail-panel-${id}`).getByTestId(`detail-field-${key}`).textContent()) || "";
}

test.describe("4.1 Pressing '+' opens both panels correctly (8)", () => {
  test("4.1.1 right panel shows the correct event's data", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await detailReady(page, "E1");
    expect(await fieldText(page, "E1", "client_name")).toContain("ישראל ישראלי");
  });

  test("4.1.2 left panel shows the correct session/messages for that event", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await expect(msgs(page, "E1").first()).toBeVisible();
    const ids = (await msgMeta(page, "E1")).map((m) => m.id);
    expect(ids).toContain(manifest().full.anchor_event.lookback_10[0]);
  });

  test("4.1.3 row expands in place (no navigation / no modal)", async ({ page }) => {
    await login(page);
    const url = page.url();
    await expand(page, "E1");
    expect(page.url()).toBe(url);
    await expect(page.getByTestId("event-list")).toBeVisible();
    await expect(page.getByTestId(`expanded-E1`)).toBeVisible();
  });

  test("4.1.4 rows below visibly shift down", async ({ page }) => {
    await login(page);
    const order = await rowIds(page);
    const below = order[order.indexOf("E1") + 1] || order[1];
    const before = (await row(page, below).boundingBox())!.y;
    await expand(page, "E1");
    await detailReady(page, "E1");
    const after = (await row(page, below).boundingBox())!.y;
    expect(after).toBeGreaterThan(before + 40);
  });

  test("4.1.5 toggle icon changes state", async ({ page }) => {
    await login(page);
    const toggle = page.getByTestId("expand-toggle-E1");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expand(page, "E1");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  test("4.1.6 right panel sits right of left panel on desktop", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await detailReady(page, "E1");
    const detail = await page.getByTestId("detail-panel-E1").boundingBox();
    const ctx = await page.getByTestId("context-panel-E1").boundingBox();
    expect(detail!.x).toBeGreaterThan(ctx!.x); // RTL: detail is the right-hand column
  });

  test("4.1.7 identical behavior regardless of which row", async ({ page }) => {
    await login(page);
    for (const id of ["E3", "E13", "E14"]) {
      await expand(page, id);
      await detailReady(page, id);
      await expect(page.getByTestId(`context-panel-${id}`)).toBeVisible();
      await collapse(page, id);
    }
  });

  test("4.1.8 no flash of wrong/blank content before real data appears", async ({ page }) => {
    await login(page);
    // slow the detail response so the loading state is observable, then assert it resolves
    await page.route("**/api/events/E1", async (r) => {
      await new Promise((res) => setTimeout(res, 400));
      await r.continue();
    });
    await page.getByTestId("expand-toggle-E1").click();
    await expect(page.getByTestId("detail-loading")).toBeVisible();
    await expect(page.getByTestId("detail-fields")).toBeVisible();
    await expect(page.getByTestId("detail-loading")).toHaveCount(0);
  });
});

test.describe("4.2 Collapsing back (5)", () => {
  test("4.2.1 toggle again closes both panels", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await collapse(page, "E1");
    await expect(page.getByTestId("context-panel-E1")).toHaveCount(0);
  });

  test("4.2.2 row / icon revert to collapsed", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await collapse(page, "E1");
    await expect(page.getByTestId("expand-toggle-E1")).toHaveAttribute("aria-expanded", "false");
  });

  test("4.2.3 rows below shift back up", async ({ page }) => {
    await login(page);
    const order = await rowIds(page);
    const below = order[order.indexOf("E1") + 1] || order[1];
    const before = (await row(page, below).boundingBox())!.y;
    await expand(page, "E1");
    await detailReady(page, "E1");
    await collapse(page, "E1");
    const after = (await row(page, below).boundingBox())!.y;
    expect(Math.abs(after - before)).toBeLessThan(8);
  });

  test("4.2.4 collapsing one row doesn't affect another independently-expanded row", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await expand(page, "E3");
    await collapse(page, "E1");
    await expect(page.getByTestId("detail-panel-E3")).toBeVisible();
  });

  test("4.2.5 re-expanding shows fresh correct data", async ({ page }) => {
    await login(page);
    await expand(page, "E3");
    await detailReady(page, "E3");
    await collapse(page, "E3");
    await expand(page, "E3");
    await detailReady(page, "E3");
    expect(await fieldText(page, "E3", "client_name")).toContain("משה לוי");
  });
});

test.describe("4.3 Right panel field manifest correctness (23)", () => {
  test("4.3.1/4.3.2 הסכם: common fields always + manifest fields when populated", async ({ page }) => {
    await login(page);
    await expand(page, "E14"); // הסכם/יצירה, reference + component_label populated
    await detailReady(page, "E14");
    const keys = await fieldKeys(page, "E14");
    for (const k of ["event_datetime", "source_type", "event_subtype", "client_name", "description", "amount", "txn_date"])
      expect(keys).toContain(k);
    expect(keys).toContain("component_label");
    expect(keys).toContain("reference"); // IF-populated even for יצירה
  });

  test("4.3.3 הסכם: manifest fields absent when empty", async ({ page }) => {
    await login(page);
    await expand(page, "E8"); // הסכם/יצירה, nothing optional populated
    await detailReady(page, "E8");
    const keys = await fieldKeys(page, "E8");
    expect(keys).not.toContain("hours");
    expect(keys).not.toContain("split_partner");
    expect(keys).not.toContain("reference");
  });

  test("4.3.4 הסכם: reference/reference_hint ALWAYS shown when subtype != יצירה", async ({ page }) => {
    await login(page);
    await expand(page, "E3"); // הסכם/עדכון, reference="REF-9", reference_hint=null
    await detailReady(page, "E3");
    const keys = await fieldKeys(page, "E3");
    expect(keys).toContain("reference");
    expect(keys).toContain("reference_hint"); // ALWAYS => shown even though null
    expect(await fieldText(page, "E3", "reference_hint")).toContain("—");
  });

  test("4.3.5 הסכם: reference IF-EXISTS-only when subtype = יצירה", async ({ page }) => {
    await login(page);
    await expand(page, "E1"); // הסכם/יצירה, reference=null
    await detailReady(page, "E1");
    expect(await fieldKeys(page, "E1")).not.toContain("reference");
  });

  test("4.3.6 הסכם: internal ids never appear", async ({ page }) => {
    await login(page);
    await expand(page, "E14");
    await detailReady(page, "E14");
    const keys = await fieldKeys(page, "E14");
    for (const k of ["event_id", "agreement_id", "component_id", "session_id", "message_id"])
      expect(keys).not.toContain(k);
  });

  test("4.3.7 בנק/הפקדה: bank fields + vat_status shown even null", async ({ page }) => {
    await login(page);
    await setDaysBack(page, 14); // E2 is 8 days back
    await expect(row(page, "E2")).toBeVisible();
    await expand(page, "E2");
    await detailReady(page, "E2");
    const keys = await fieldKeys(page, "E2");
    for (const k of ["bank_number", "bank_branch", "bank_account", "vat_status"]) expect(keys).toContain(k);
    expect(await fieldText(page, "E2", "vat_status")).toContain("—"); // vat_status null but ALWAYS-shown for הפקדה
  });

  test("4.3.8/4.3.9 בנק non-הפקדה: bank fields IF-EXISTS only; payer_name IF-EXISTS", async ({ page }) => {
    await login(page);
    await expand(page, "E7"); // בנק/מבוטל, bank fields null, payer_name null
    await detailReady(page, "E7");
    const keys = await fieldKeys(page, "E7");
    expect(keys).not.toContain("bank_number");
    expect(keys).not.toContain("payer_name");
  });

  test("4.3.10 בנק: split fields never shown", async ({ page }) => {
    await login(page);
    await expand(page, "E7");
    await detailReady(page, "E7");
    const keys = await fieldKeys(page, "E7");
    expect(keys).not.toContain("split_partner");
    expect(keys).not.toContain("split_percent");
  });

  test("4.3.11/12/13 חשבונית: display_number + status_label + vat_status always shown", async ({ page }) => {
    await login(page);
    await expand(page, "E6"); // חשבונית/חשבונית מס
    await detailReady(page, "E6");
    const keys = await fieldKeys(page, "E6");
    expect(keys).toContain("accounting_document_display_number");
    expect(keys).toContain("accounting_document_status_label");
    expect(keys).toContain("vat_status");
  });

  test("4.3.14 חשבונית: raw status/status_code never shown", async ({ page }) => {
    await login(page);
    await expand(page, "E4");
    await detailReady(page, "E4");
    const keys = await fieldKeys(page, "E4");
    expect(keys).not.toContain("accounting_document_status");
    expect(keys).not.toContain("accounting_document_status_code");
  });

  test("4.3.15 חשבונית: payment_method IF-EXISTS", async ({ page }) => {
    await login(page);
    await expand(page, "E4"); // has payment_method
    await detailReady(page, "E4");
    expect(await fieldKeys(page, "E4")).toContain("accounting_document_payment_method");
    await collapse(page, "E4");
    await expand(page, "E5"); // no payment_method
    await detailReady(page, "E5");
    expect(await fieldKeys(page, "E5")).not.toContain("accounting_document_payment_method");
  });

  test("4.3.16 חשבונית מס/קבלה + bank transfer: bank fields shown even empty", async ({ page }) => {
    await login(page);
    await expand(page, "E4"); // "חשבונית מס / קבלה" + "העברה בנקאית", bank fields null
    await detailReady(page, "E4");
    const keys = await fieldKeys(page, "E4");
    expect(keys).toContain("bank_number");
    expect(await fieldText(page, "E4", "bank_number")).toContain("—");
  });

  test("4.3.17 חשבונית מס + other payment method: bank fields completely absent", async ({ page }) => {
    await login(page);
    await expand(page, "E6"); // "חשבונית מס" + "מזומן"
    await detailReady(page, "E6");
    const keys = await fieldKeys(page, "E6");
    expect(keys).not.toContain("bank_number");
    expect(keys).not.toContain("bank_branch");
  });

  test("4.3.18 חשבון עסקה: bank fields completely absent regardless", async ({ page }) => {
    await login(page);
    await expand(page, "E5"); // "חשבון עסקה"
    await detailReady(page, "E5");
    expect(await fieldKeys(page, "E5")).not.toContain("bank_number");
  });

  test("4.3.19 חשבונית זיכוי: reference/reference_hint shown even empty", async ({ page }) => {
    await login(page);
    await expand(page, "E9"); // "חשבונית זיכוי", reference="" reference_hint=""
    await detailReady(page, "E9");
    const keys = await fieldKeys(page, "E9");
    expect(keys).toContain("reference");
    expect(keys).toContain("reference_hint");
  });

  test("4.3.20 חשבונית other subtype: reference IF-EXISTS only", async ({ page }) => {
    await login(page);
    await expand(page, "E6"); // "חשבונית מס", no reference
    await detailReady(page, "E6");
    expect(await fieldKeys(page, "E6")).not.toContain("reference");
  });

  test("4.3.21 Hebrew labels render correctly (spot-check)", async ({ page }) => {
    await login(page);
    await expand(page, "E6");
    await detailReady(page, "E6");
    expect(await fieldText(page, "E6", "client_name")).toContain("שם לקוח");
    expect(await fieldText(page, "E6", "accounting_document_display_number")).toContain("מספר מסמך");
  });

  test("4.3.22 internal/bookkeeping fields never appear for any type", async ({ page }) => {
    await login(page);
    for (const id of ["E1", "E6", "E7"]) {
      await expand(page, id);
      await detailReady(page, id);
      const keys = await fieldKeys(page, id);
      for (const k of ["captured_at", "session_id", "message_id", "event_id"])
        expect(keys).not.toContain(k);
      await collapse(page, id);
    }
  });

  test("4.3.23 unrecognized source_type shows an explicit unsupported message", async ({ page }) => {
    await login(page);
    await expand(page, "E10"); // source_type "מוזר"
    await expect(page.getByTestId("detail-unsupported")).toBeVisible();
    await expect(page.getByTestId("detail-fields")).toHaveCount(0);
  });
});

test.describe("4.4/4.5 Left panel — WhatsApp-style chat (17)", () => {
  test("4.4.1/4.4.2 user messages right, assistant messages left", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const meta = await msgMeta(page, "E1");
    const anchor = meta.find((m) => m.id === "M3")!;
    const bot = meta.find((m) => m.id === "M4")!;
    expect(anchor.side).toBe("right");
    expect(bot.side).toBe("left");
  });

  test("4.4.3 chronological order", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const ids = (await msgMeta(page, "E1")).map((m) => m.id);
    expect(ids).toEqual([...ids].sort()); // M0..M4 already lexically sorted == chronological here
  });

  test("4.4.4/4.4.14/4.4.15 only messages within the (inclusive) lookback window", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const ids = (await msgMeta(page, "E1")).map((m) => m.id);
    expect(ids.sort()).toEqual([...manifest().full.anchor_event.lookback_10].sort()); // M0 (boundary) in, M5 out
  });

  test("4.4.5 the anchor message is always included", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const ids = (await msgMeta(page, "E1")).map((m) => m.id);
    expect(ids).toContain(readEvent("E1").message_id);
  });

  test("4.4.6 an image attachment renders as a thumbnail, not inline full-size", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const img = page.getByTestId("context-panel-E1").getByTestId("chat-image").first();
    await expect(img).toBeVisible();
    const box = await img.boundingBox();
    expect(box!.width).toBeLessThanOrEqual(220);
  });

  test("4.4.7/4.4.8/4.4.9 clicking a thumbnail opens a larger view with an OK to dismiss", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await page.getByTestId("context-panel-E1").getByTestId("chat-image").first().click();
    await expect(page.getByTestId("image-overlay")).toBeVisible();
    await expect(page.getByTestId("image-overlay-close")).toBeVisible();
    await page.getByTestId("image-overlay-close").click();
    await expect(page.getByTestId("image-overlay")).toHaveCount(0);
    await expect(page.getByTestId("detail-panel-E1")).toBeVisible(); // still expanded
  });

  test("4.4.10 a text-only message shows just its bubble, no broken-image placeholder", async ({ page }) => {
    await login(page);
    await expand(page, "E3"); // S3 messages are text only
    await expect(page.getByTestId("context-panel-E3").getByTestId("chat-media-unavailable")).toHaveCount(0);
    await expect(page.getByTestId("context-panel-E3").getByTestId("chat-image")).toHaveCount(0);
  });

  test("4.4.11 sender name renders correctly", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const senders = await page
      .getByTestId("context-panel-E1")
      .getByTestId("context-message-sender")
      .allTextContents();
    expect(senders.join(" ")).toContain("דוד");
    expect(senders.join(" ")).toContain("דני דין"); // assistant label
  });

  test("4.4.12 timestamp shown / orderable", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    const times = await page
      .getByTestId("context-panel-E1")
      .getByTestId("context-message-time")
      .allTextContents();
    expect(times.length).toBeGreaterThan(0);
    expect(times).toEqual([...times].sort());
  });

  test("4.4.13 multiple images each have independent thumbnail/lightbox behavior", async ({ page }) => {
    await login(page);
    await expand(page, "E1"); // S1: M2 and M3 both carry a (real) image
    const thumbs = page.getByTestId("context-panel-E1").getByTestId("chat-image");
    await expect(thumbs).toHaveCount(2);
    await thumbs.nth(0).click();
    await expect(page.getByTestId("image-overlay")).toBeVisible();
    await page.getByTestId("image-overlay-close").click();
    await expect(page.getByTestId("image-overlay")).toHaveCount(0);
    await thumbs.nth(1).click();
    await expect(page.getByTestId("image-overlay")).toBeVisible();
  });

  test("4.4.16 a video/audio message shows a non-playable placeholder in v1", async ({ page }) => {
    test.fixme(
      true,
      "No fixture message carries a video/audio attachment yet, and the v1 non-playable " +
        "placeholder for them is a Stories 4-8 viewable→done gap. PLAYWRIGHT-TEST-PLAN 4.4/4.5.16."
    );
  });

  test("4.4.17 a document attachment (PDF/DOCX) renders/opens like an image", async ({ page }) => {
    test.fixme(
      true,
      "Doc attachments currently fall through ChatImage and show 'media unavailable' rather " +
        "than a clickable thumbnail opening the browser's PDF view. Stories 4-8 viewable→done. " +
        "PLAYWRIGHT-TEST-PLAN 4.4/4.5.17."
    );
    await login(page);
    await expand(page, "E13");
    await page.getByTestId("context-panel-E13").getByTestId("chat-image").nth(0).click();
    await expect(page.getByTestId("image-overlay")).toBeVisible();
  });
});

test.describe("4.6 Graceful degradation (5)", () => {
  test("4.6.1 missing/unresolvable session shows a clear 'unavailable' message", async ({ page }) => {
    await login(page);
    await expand(page, "E16"); // session resolves but GHOST message id doesn't
    await expect(page.getByTestId("context-panel-E16").getByTestId("context-unavailable")).toBeVisible();
  });

  test("4.6.2 right panel renders fully even when the left panel fails", async ({ page }) => {
    await login(page);
    await expand(page, "E16");
    await detailReady(page, "E16");
    await expect(page.getByTestId("detail-fields")).toBeVisible();
    expect(await fieldText(page, "E16", "client_name")).toContain("נוי שגב");
  });

  test("4.6.3 no crash / infinite spinner on unresolvable context", async ({ page }) => {
    await login(page);
    await expand(page, "E16");
    await expect(page.getByTestId("context-panel-E16").getByTestId("context-unavailable")).toBeVisible();
    await expect(page.getByTestId("app-ready")).toBeVisible();
  });

  test("4.6.4 graceful when the session has no conversation at all (reconciliation event)", async ({ page }) => {
    await login(page);
    await expand(page, "E15"); // message_id null -> no_conversation
    await expect(page.getByTestId("context-panel-E15").getByTestId("context-unavailable")).toBeVisible();
  });

  test("4.6.5 graceful when a message's image_path points to a missing file", async ({ page }) => {
    await login(page);
    await expand(page, "E13"); // M132 -> media/does-not-exist.jpg (backend omits the media entirely)
    const panel = page.getByTestId("context-panel-E13");
    // the message itself still renders (as text), the chat and the app don't crash
    await expect(panel.getByTestId("chat-msg-M132")).toBeVisible();
    await expect(panel.getByTestId(/^chat-msg-/)).toHaveCount(4);
    await expect(page.getByTestId("app-ready")).toBeVisible();
  });
});

test.describe("4.7 Layout / positioning (3)", () => {
  test("4.7.1 right panel positioned right of left panel on desktop", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await detailReady(page, "E1");
    const d = await page.getByTestId("detail-panel-E1").boundingBox();
    const c = await page.getByTestId("context-panel-E1").boundingBox();
    expect(d!.x).toBeGreaterThan(c!.x);
  });

  test("4.7.2 both panels sit directly below the expanded row", async ({ page }) => {
    await login(page);
    await expand(page, "E1");
    await detailReady(page, "E1");
    const toggle = await page.getByTestId("expand-toggle-E1").boundingBox();
    const exp = await page.getByTestId("expanded-E1").boundingBox();
    expect(exp!.y).toBeGreaterThanOrEqual(toggle!.y + toggle!.height - 2);
  });

  test("4.7.3 expanding one row doesn't visually corrupt unrelated rows", async ({ page }) => {
    await login(page);
    const ids = await rowIds(page);
    const other = ids.find((i) => i !== "E1")!;
    await expand(page, "E1");
    await detailReady(page, "E1");
    const box = await row(page, other).boundingBox();
    expect(box!.width).toBeGreaterThan(200); // still a well-formed row
  });
});
