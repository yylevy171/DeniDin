# Quickstart: Verifying WhatsApp Interactive Approval Buttons

**Feature**: 047-whatsapp-interactive-approval-buttons

Manual verification scenarios for each user story, to run against a running `dev` container
(per CLAUDE.md's environment rules — starting `dev` needs its own explicit approval, every
time). These complement, not replace, the automated test suite in `tasks.md`. Requires the real
godfather/admin dev number and (for US-groups behavior) the project's existing test group
(`קבוצה נסיונית עם דנידין`, used directly during Gate Zero — see `research.md`).

## Prerequisites

- `denidin-app-dev` running.
- A real document-creation request ready to issue (e.g. "צור חשבונית ל[לקוח קיים] על סך 100 ש״ח
  עבור בדיקה"), against a client that already exists in the Morning sandbox (dev environment).

## US1 — Approve a document with one tap

1. Send the document-creation request in a 1:1 chat with DeniDin.
2. Confirm the reply carries the full `📋 לאישור:` block **and** renders as two native WhatsApp
   buttons labeled exactly `"כן"` and `"לא"` (not `"אישור"`/`"ביטול"`).
3. Tap `"כן"`.
4. Confirm: the document is created exactly once (check Morning sandbox / `list_invoices`), and
   the confirmation text matches what typing `כן` would have produced.
5. Repeat the whole flow, tapping `"לא"` this time at step 3 — confirm nothing is created and
   DeniDin says so plainly.

## US2 — Typing still works, unconditionally

1. Trigger a new pending approval (as above).
2. Ignore the buttons; type `כן` (or `אישור`, or `לאשר`, with or without a leading RTL mark)
   instead.
3. Confirm it resolves exactly as before this feature existed — the text path is provably
   unaffected by buttons rendering alongside it.

## US3 — A stale tap does nothing observable

1. Trigger a pending approval, resolve it via text (`כן` or `לא`) — do **not** tap the button.
2. Now tap the (still-visible) button on that already-resolved message.
3. Confirm: no second document is created (or, for a decline-then-tap-כן sequence, no document
   is created at all), and **no reply is sent** — nothing observable happens. This is the
   clarified "silently ignore" behavior, not a bug if nothing appears to happen.
4. Separately: trigger a pending approval, then — **before** resolving it — send a second,
   different document-creation request so a *new* pending approval replaces the first
   (`PendingApprovalManager` keeps only the most recent). Now tap the button on the **first**
   (now-superseded) message. Confirm the *second* request is **not** approved/declined by this
   tap, and nothing observable happens — this is the `stanza_id` mismatch guard specifically
   (data-model.md's state diagram), the scenario a naive "any pending approval exists" check
   would get wrong.

## US4 — The question is still fully stated

1. Trigger any pending approval.
2. Before tapping, read the message body — confirm it states document type, document date,
   client, amount, VAT treatment, and purpose (plus transaction date/payment method/bank
   details/linked invoice number when known) — identical in content to the pre-047 text-only
   prompt, just delivered with buttons attached.

## Groups (Clarifications: buttons behave the same as 1:1)

1. In the test group, from the godfather or admin account, trigger a document-creation request.
2. Confirm the buttons render in the group the same as 1:1.
3. Tap `"כן"` — confirm the tap is attributed to the actual tapping member (check logs for the
   resolved sender), and the document is created exactly once.

## Send-failure surfaces an error (not a silent fallback)

Hard to trigger deliberately without simulating a Green API failure — if one occurs naturally
during testing (e.g. a transient `sendInteractiveButtons` error), confirm: the user receives a
distinct plain-text error notice (not the `📋 לאישור:` block itself, no buttons), and the
pending approval remains resolvable by typing `כן`/`לא` afterward (it was never cleared).

## Audit trail

After any button-resolved approval, check `logs/dev/` for a `[047]`-prefixed log line
distinguishing "resolved via BUTTON TAP" from the existing `[022]` text-resolution logging —
confirms the approval mechanism is recorded, not just the outcome.
