# Bugfix 065: Synthetic Media "Stash" Turn Is Persisted As If the Human Sender Wrote It

**Status**: Open — placeholder (root cause identified, awaiting human approval to proceed per METHODOLOGY.md §VII). No fix, no test written yet.
**Severity**: High (data integrity / misattribution in the persisted conversation record)
**Components**: `apps/denidin-app/denidin.py` (`_process_media_message`, Feature 069 synthetic turn), `apps/denidin-app/src/handlers/ai_handler.py` (`get_response` message persistence, ~line 4125-4190), `apps/denidin-app/src/handlers/ai_handler.py` (`_render_media_ledger_stash`-style renderer, ~line 1075-1107)
**Found via**: Feature 087 webapp review of real prod bank-deposit events (2026-09-24)

---

## 1. Problem Statement

When a godfather/admin (e.g. Ayala) sends an image of a bank deposit / transfer (or a fee-agreement image/DOCX), DeniDin generates an internal message — `📸 התקבלה תמונה של אסמכתת העברה/הפקדה בנקאית.` followed by the recognised fields and the verbatim extracted text — and persists it in the session **as a message the human sender typed**: `role` = her RBAC role (`admin`/`godfather`), `sender_name` = her display name, `sender` = her number, and carrying her original WhatsApp message id.

She never sends this message. Her real WhatsApp activity is the image, then (after DeniDin replies) a follow-up such as a request to create a document. The persisted record therefore contradicts what actually happened in the chat, and every consumer of the record (the webapp conversation panel, any audit/export, future analytics) shows DeniDin-authored internal content as hers.

Observed in prod (event `B14092613320`, session `12e158e2-…`): order 1986 `godfather [image sent]` (real) → 1987 `assistant` OCR text (real, sent by DeniDin) → **1988 `admin`, sender אילה, `📸 התקבלה תמונה של אסמכתת…` (internal, misattributed)** → 1989 `assistant` reply. All 13 messages in prod that start with `📸` are this case.

## 2. Root Cause (identified, not yet approved)

`denidin.py` (~lines 833-848, Feature 069 Phase 9/10): when the media handler returns a `ledger_stash`, the **same notification object is mutated in place** into a synthetic `textMessage` (`messageData.clear()` + `textMessageData = {stash}`) and re-entered into `_process_conversational_message`. The notification still carries the original `senderData` (sender id, sender name) and `idMessage`, so:

1. `WhatsAppMessage.from_notification` builds a message that looks exactly like one typed by the human.
2. `AIHandler.get_response` persists it via `add_message[_with_tokens](role="user", …, sender=<human phone>, sender_name=<human name>, whatsapp_id_message=<original idMessage>, …)`.

Nothing in the persisted record marks the turn as system-originated, so it cannot be told apart from a real human message after the fact. (`whatsapp_id_message` is not a usable discriminator: it is present on this synthetic turn but absent on the human's real image record and on all assistant messages.)

## 3. Why the model needs the turn (constraint on any fix)

The stash must still reach the model as a user-side turn so it can do client resolution / approval / post-turn ledger recognition (Feature 069). The bug is in **what is persisted and how it is attributed**, not in feeding the model.

## 4. Test Gap

`tests/integration/test_ledger_client_resolution_routing.py::test_bank_image_routes_synthetic_turn_and_persists_one_event` (and the DOCX sibling) drive this exact path end-to-end but assert only the operator-visible reply, the persisted `LedgerEvent`, and that the extracted text reached the model. **Nothing asserts how the synthetic turn is persisted** — sender, sender_name, role, or any system-origin marker.

## 5. Open Design Questions (for the fix step — do not decide here)

- How to mark a persisted message as system-originated (new explicit `Message` field vs. attributing sender/sender_name/role to DeniDin) while keeping it usable as a model-facing user turn in the rolling 14-day window.
- Whether `whatsapp_id_message` should still be carried on it.
- Consumers to update once marked: `apps/webapp/backend/src/webapp_backend/context_reader.py` (conversation panel — must show or hide it correctly, not as the human).
- Historical data: the 13 already-persisted `📸` messages in prod stay misattributed unless separately corrected; a data migration/backfill on prod is a separate human decision.

## 6. Out of Scope

- Ordering of messages in the webapp conversation panel (fixed separately, Feature 087: sort by `order_num`).
- Sessions/messages whose source message no longer exists (32 of 81 prod bank events) — separate data gap.

## 7. Acceptance (to be refined at the test-definition step)

After the fix, a bank-deposit image from a godfather/admin produces, in the persisted session, no message attributed to that human other than the image record itself; the synthetic stash turn is identifiable as system-originated; the model still receives the stash and the Feature 069 flow (client resolution, approval, single `LedgerEvent`) is unchanged.
