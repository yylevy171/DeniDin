# Feature Specification: Reminders — Functionality and Management

**Feature Branch**: `feature/054-reminders-functionality-mgmt`
**Created**: 2026-08-15
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-15 request;
run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description: "reminders - functionality and mgmt" — no further detail given yet.

## Notes captured so far

- Scope not yet defined. Open questions for `speckit.specify`/`speckit.clarify`:
  - Who can set a reminder (any client, or godfather/admin only)?
  - What triggers a reminder — a user-stated relative/absolute time via natural conversation
    (similar to how ledger events are recognized), or an explicit command/tool?
  - Delivery mechanism: a proactive outbound WhatsApp message at the target time? If so, this
    likely overlaps with `008-scheduled-proactive-chats` and `013-proactive-whatsapp-messaging-core`
    (both backlog) — worth cross-referencing during planning so a proactive-send mechanism isn't
    built twice.
  - "Management" implies listing/editing/cancelling existing reminders — needs a storage model
    (own file-per-reminder under `{data_root}`, similar to `managers/ledger_event_manager.py`'s
    pattern? or session-scoped?) and RBAC/ownership rules (can a user only manage their own
    reminders, or can a godfather/admin manage anyone's?).
  - Timezone handling should follow the existing Israel-local-time rule (`now_local()`) — no new
    UTC usage.
