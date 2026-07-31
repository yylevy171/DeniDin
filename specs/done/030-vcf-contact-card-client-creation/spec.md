# Feature Spec: Client Creation via Shared Contact Card (vCard/.vcf)

**Feature ID**: 030-vcf-contact-card-client-creation
**Priority**: P2
**Status**: Done - Merged to master (PR #154, 2026-07-31) — implemented and verified (unit +
integration + billed E2E tests all passing, no regressions). Manual live-WhatsApp walkthroughs
(`quickstart.md` US1/US2/US3, `tasks.md` T007/T009/T011) explicitly waived by user decision
(2026-07-31) — automated verification judged sufficient; not planned to be run.
**Created**: July 30, 2026

---

## Problem Statement

Godfather/admin users manage Morning clients today only by describing them in
natural language to the model, which then calls the `add_client` MCP tool
(`name`/`email`/`phone` required, `tax_id` optional — `address` is out of
scope per Feature 026, see
`apps/morning-mcp-app/src/denidin_mcp_morning/server.py:278-286`). WhatsApp
lets a user share a device contact directly as a **contact card message**
(vCard/.vcf) instead of typing the details — Green API surfaces this as its
own notification `typeMessage` (not one of the four media types DeniDin
currently handles). `denidin.py` registers routers only for `textMessage`/
`extendedTextMessage`, `imageMessage`, `documentMessage`, `videoMessage`,
`audioMessage`, plus a catch-all (`denidin.py:292-450`) — a shared contact
card today falls through to the catch-all, which does not extract or act on
it. There is no vCard parsing anywhere in the codebase currently
(`grep -ri vcf/vcard/contact.*card` across `apps/denidin-app/src` returns
nothing).

**Goal**: let a godfather/admin share a WhatsApp contact card and have DeniDin
offer to create (or route to) an `add_client` call using the card's
name/phone (and email if present), instead of requiring the details to be
typed out by hand.

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- Spec approval is BLOCKED if `user-stories.md` does not exist
- See `user-stories.md` in this directory and `.github/METHODOLOGY.md §I`

---

## Clarifications

### Session 2026-07-30

- Q: What does Green API's webhook actually send for a shared contact? → A: **Fully confirmed
  against Green API's official docs (2026-07-30), no assumption remains.** Single contact:
  `typeMessage: "contactMessage"`, fields under `messageData.contactMessageData`: `displayName`,
  `vcard` (raw vCard text), `forwardingScore`, `isForwarded`. Multiple contacts shared in one
  message: a **different `typeMessage` entirely**, `"contactsArrayMessage"`, with
  `messageData.messageData.contacts` — an array of `{displayName, vcard}` (note the doubled
  `messageData` nesting, confirmed from the docs' own example, not a typo). This means
  multi-contact detection (see next bullet) is simply "is `typeMessage` `contactsArrayMessage`?" —
  no vCard-counting/parsing needed to detect it. The raw *vCard* shape itself is additionally
  backed by a real fixture: `apps/denidin-app/tests/fixtures/contacts/00005372-גיל ברטל .vcf`, a
  genuine WhatsApp-exported vCard 3.0 with `N`/`FN`/`TEL` (with `waid=<E.164-no-plus>` param) but
  **no `EMAIL` field at all** and a WhatsApp-specific `X-WA-LID` extension. This means the
  "missing mandatory field" path (US2) is likely the **common** case for real contact shares, not
  an edge case — email is frequently absent from device contacts entirely.
- Q: RBAC scope? → A: **Same godfather/admin gating as existing Morning tools, inherited
  automatically** — no new RBAC logic. A client/blocked-role sender gets the same friendly
  "no Morning access" behavior any other Morning-related ask already gets from that role (see
  `user-stories.md` US4).
- Q: Should v1 handle multi-contact card shares? → A: **No — single-contact only for v1.** A
  multi-contact share (`typeMessage: "contactsArrayMessage"`, a distinct type from single-contact
  `contactMessage`) gets a friendly "please share one contact at a time" message; no vCard
  parsing, no AI/tool call at all (see `user-stories.md` US3). Batch/multi-contact handling is
  explicitly deferred.
- Q: Confirmation flow — auto-create immediately, or confirm first? → A: **Confirm first, and
  also ask for any missing mandatory fields before proceeding.** This is not a new mechanism to
  build: `add_client` is already in `AIHandler.APPROVAL_REQUIRED_MCP_TOOLS` (Feature 026) with an
  existing "ask for missing name/email/phone" behavior (REQ-CLIENT-012) — this feature only needs
  to feed parsed vCard fields into that same existing pipeline (see `user-stories.md` US1/US2).
- Q: Missing/malformed vCard fields? → A: Missing mandatory fields (name/email/phone) are handled
  by the existing Feature 026 "ask for what's missing" behavior (US2) — no new validation logic.
  Malformed/unparseable vCard text beyond that falls back to the project's standard friendly-error
  style (no stack trace); no bespoke vCard-repair logic is in scope.

## References

- `apps/denidin-app/denidin.py:292-450` — existing `@bot.router.message(type_message=...)` registrations and catch-all; a new `@bot.router.message(type_message='contactMessage')` router would be added here.
- `apps/denidin-app/src/handlers/whatsapp_handler.py`, `handlers/media_handler.py` — existing message-type validation/dispatch pattern to follow for consistency.
- `apps/denidin-app/src/handlers/ai_handler.py` (`APPROVAL_REQUIRED_MCP_TOOLS`, `PendingApprovalManager`) — the existing Feature 026 approval-gate/missing-field mechanism this feature reuses unchanged.
- `apps/morning-mcp-app/src/denidin_mcp_morning/server.py:278-286` (`add_client` tool) and `tools.py`'s `add_client` implementation — the eventual call target.
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py:886` (`_normalize_israeli_phone`) — already
  runs inside `add_client`/`update_client`; verified against the vCard fixture's phone value
  (both the `TEL` value and the `waid` param normalize to the same `050-7951824`) — this feature
  needs no new phone-normalization code, see `user-stories.md`'s "Phone Normalization Note".
- `specs/done/026-client-management/` (`spec.md`, `user-stories.md`) — the approval-gate and missing-mandatory-field behavior this feature depends on and must not duplicate.
- CLAUDE.md's "Morning MCP integration" section — RBAC-gating precedent (godfather/admin only) this feature should follow.
- `apps/denidin-app/tests/fixtures/contacts/00005372-גיל ברטל .vcf` (+ its `README.md`) — real
  WhatsApp-exported vCard fixture used by US1/US2's tests; confirms the vCard field shape
  (no `EMAIL`, `X-WA-LID` extension present).
