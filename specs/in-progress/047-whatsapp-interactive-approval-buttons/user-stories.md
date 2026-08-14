# User Stories: WhatsApp Interactive Buttons for the Approval Gate

**Feature**: 047-whatsapp-interactive-approval-buttons
**Status**: Draft — backlogged, pre-clarification
**Created**: 2026-08-09

All stories are **blocked on Gate Zero** (a real button round-trip with the webhook JSON
captured — see `spec.md`). They are written as intent, not as a commitment to a mechanism that
has not yet been observed.

---

## US1 — Approve a document with one tap

**As** a godfather issuing an invoice over WhatsApp,
**I want** to approve by tapping a button,
**So that** the approval cannot fail because of how a word was spelled, autocorrected, or
invisibly prefixed by my RTL keyboard.

**Given** DeniDin has a document-creation call pending my approval
**When** it asks me to approve it
**Then** the message carries the full `📋 לאישור:` details block **and** two buttons, "אישור" and
"ביטול"

**Given** that message
**When** I tap "אישור"
**Then** the pending document is created exactly once, and I get the same confirmation I would
have got by typing `כן`

**Given** that message
**When** I tap "ביטול"
**Then** nothing is created, and DeniDin says so plainly

---

## US2 — Typing still works, always

**As** a user whose device, client version or chat type doesn't render buttons,
**I want** typing `כן` to keep working exactly as before,
**So that** a display capability never becomes a prerequisite for using the system.

**Given** a pending approval presented with buttons
**When** I ignore them and type `כן` (or `אישור`, or `לאשר`, with or without a bidi mark)
**Then** it is approved exactly as it is today — the text path is unchanged and unconditional

---

## US3 — A stale tap is never a surprise document

**As** a user scrolling back through an old conversation,
**I want** tapping a button on a long-resolved request to do nothing harmful,
**So that** an idle tap can never create a real financial document.

**Given** an approval that was already resolved, superseded, or has expired
**When** I tap its (still visible) "אישור" button
**Then** no document is created, and DeniDin tells me that request is no longer live — rather
than silently ignoring me, which is the failure bugfix-028's B5 was about

*(Exact behaviour depends on Gate Zero finding 5 — whether such a tap even reaches us.)*

---

## US4 — The question is still fully stated

**As** the person accountable for a real tax document,
**I want** the button message to state everything I am approving,
**So that** one tap is never easier than one informed decision.

**Given** any approval presented with buttons
**When** I read it before tapping
**Then** it states document type, document date, client, amount, VAT treatment and purpose — plus
transaction date, payment method, bank details and linked invoice number when known — exactly as
the text path does (bugfix-028 B3; buttons change the answer's form, never the question's content)
