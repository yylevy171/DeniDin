# Feature Specification: Reminders — Functionality and Management

**Feature Branch**: `feature/054-reminders-functionality-mgmt`
**Created**: 2026-08-15
**Clarified**: 2026-08-16
**Status**: Draft — spec/user-stories written, `plan.md`/`tasks.md` not yet started.
**Priority**: P2 (first-pass estimate, adjust if needed)
**Input**: User description: "reminders - functionality and mgmt" (2026-08-15, placeholder), fleshed
out via conversation 2026-08-16 (see Clarifications).

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I-III, §V, NO UNVERIFIED THIRD-PARTY ASSUMPTIONS): No env vars, Israel
  local timestamps, feature branch workflow, integration tests as E2E, no monkey-patching.
- **METHODOLOGY.md** (§I, II, VIII, IX, X): Spec-first development, mandatory user stories,
  Terminology Glossary, Technology Choices, Requirement IDs.

**Required Files**: `user-stories.md` ✅ · `spec.md` (this file) ✅ ·
`plan.md` ⏳ · `tasks.md` ⏳

---

## Clarifications

### Session 2026-08-16

- Q: Who can create/own reminders? → A: **Godfather/admin only.** Client and blocked roles have
  no access to reminder functionality at all — same gating tier as Morning invoice/ledger tools.
- Q: Does "modify/delete any reminder at any time" mean self-only or cross-user override? → A:
  **Self + fully symmetric godfather/admin override.** A user manages their own reminders by
  default; additionally, since this app already supports multiple admin phones
  (`config.admin_phones`) and may in future support multiple godfathers (see
  `specs/backlog/055-multiple-clients-godfathers/`), any GODFATHER or ADMIN user may modify/delete
  a reminder created by any other GODFATHER or ADMIN user — no directional restriction (confirmed
  2026-08-16, overriding an earlier ADMIN-over-GODFATHER-only draft reading).
- Q: What recurrence model? → A: **Full standard calendar-app model** — every-N-periods interval,
  weekday selection for weekly, day-of-month-or-Nth-weekday for monthly, plus never/after-N/until-date
  end conditions. Matches Outlook/Google Calendar recurrence semantics. **No yearly cadence.**
- Q: Max active reminders (X) and scope? → A: **20 per user**, tracked independently per
  godfather/admin identity, not a system-wide shared pool. A reminder *series* (whether one-time
  or recurring) counts as one against this cap — individual occurrences of a recurring reminder do
  not each count separately.
- Q: Should modify/delete of a recurring reminder support acting on a single occurrence, not just
  the whole series? → A: **Yes** (added 2026-08-16, after initial spec draft) — same "this
  occurrence" vs. "the whole series" distinction as Outlook/Google Calendar. When the target of a
  modify/delete is part of a recurring series, system MUST ask which scope applies before
  proceeding, unless the user's original request already made the scope unambiguous (e.g. "cancel
  just this Monday's reminder" vs. "cancel my daily reminder entirely"). This reverses the initial
  draft's whole-series-only restriction — see updated FR-010/FR-012.

## Origin

User-supplied end-to-end flow (2026-08-16):
1. User states intent to create a reminder → AI guides through all reminder details
   conversationally → explicit approval stage → on "yes", a reminder entry is persisted.
2. When a reminder is due, the system wakes up and fires the reminder text to the user.
3. User can modify or delete any reminder at any time: system helps identify the correct
   reminder → for modification, system guides what to change → system acts on the confirmed
   change.

Design guardrails supplied directly by the user, carried through into Requirements below:
past-dated reminders are rejected; a hard cap on total active reminders exists; delivery runs
from exactly one shared background mechanism, never one per reminder; recurrence follows
standard calendar-app semantics; each individual firing (occurrence) is tracked with its own
pending/fired status, independent of the parent reminder's own state.

## Scope

**In scope**: conversational create/modify/delete of reminders (godfather/admin only), an
explicit approval gate before persisting any create/modify/delete, one-time and recurring
reminders (daily/weekly/monthly cadences), a single shared delivery mechanism that fires due
occurrences as proactive outbound WhatsApp messages, and per-occurrence status tracking.

**Out of scope**: the general scheduled/proactive-messaging framework described in
`specs/backlog/008-scheduled-proactive-chats/` and
`specs/backlog/013-proactive-whatsapp-messaging-core/` (event-driven triggers, condition-based
triggers, sending arbitrary AI-composed messages to *other* people on the godfather's behalf).
This feature builds only the minimal proactive-send capability needed to deliver a reminder back
to its own creator at a scheduled time — it does not attempt to generalize into a reusable
proactive-messaging platform. A future feature may refactor reminder delivery onto a shared
mechanism if/when 008 or 013 is built; that refactor is not part of this feature.

**Explicitly not solved by this feature**: yearly recurrence cadence; reminders that fire to a
chat other than the creator's own (no "set a reminder for someone else" capability, consistent
with 013 being out of scope).

## User Stories Reference

**NOTE**: Complete user stories are defined in **`user-stories.md`** (same directory). This
spec's Requirements section is the authoritative source for FR identifiers; `user-stories.md` is
the authoritative source for Given-When-Then acceptance criteria.

## Terminology Glossary

- **Reminder**: A godfather/admin-owned instruction for DeniDin to proactively send a specified
  message back to that user's own WhatsApp chat at a scheduled time — one-time or recurring.
- **Occurrence**: A single scheduled firing of a Reminder. A one-time reminder has exactly one
  occurrence; a recurring reminder generates one occurrence per cadence cycle (bounded by its end
  condition). Each occurrence has its own status, independent of sibling occurrences.
- **Recurrence Rule**: The cadence definition for a recurring reminder — an interval (every N
  days/weeks/months), a cadence unit (day/week/month), a weekday selection (for weekly), a
  day-of-month or Nth-weekday pattern (for monthly), and an end condition (never / after N
  occurrences / until a specific date).
- **Occurrence status**: `pending` (not yet due, or due but not yet delivered), `fired`
  (delivery to the user has completed), or `cancelled` (removed before firing, either directly or
  as a side effect of a whole-series deletion). Set independently per occurrence.
- **Series**: All occurrences generated by one recurring Reminder's Recurrence Rule, collectively.
  Modify/delete actions on a recurring reminder apply either to a single occurrence within the
  series or to the whole series (all remaining `pending` occurrences) — see FR-010/FR-012.
- **Detached occurrence**: A single occurrence that has been individually modified (a different
  due datetime and/or message text than its Recurrence Rule would otherwise generate). It remains
  part of its series for whole-series deletion purposes, but a whole-series *modification* does
  not overwrite a detached occurrence's own overrides.
- **Reminder delivery mechanism**: The single shared background process responsible for checking
  which occurrences are due and delivering them — not one mechanism per reminder or per user (an
  explicit design guardrail from the Origin conversation, distinct from any per-request thread).
- **Approval gate**: The existing explicit yes/no confirmation step (Feature 022, extended with
  WhatsApp buttons by Feature 047) required before any state-changing action is committed. This
  feature reuses that same UX pattern for reminder create/modify/delete, as a new local-tool-style
  confirmation (parallel to `capture_ledger_event`'s pattern) rather than literally reusing
  `PendingApprovalManager`, which is scoped specifically to OpenAI Responses API MCP tool calls.

## Technology Choices

- **Storage**: One JSON file per reminder under `{data_root}/reminders/{reminder_id}.json`,
  mirroring the existing `managers/ledger_event_manager.py` pattern (Feature 033) of one
  immutable-once-written-append-only file per entity rather than a shared mutable index file.
  Occurrence status is tracked as part of that same reminder record (see `data-model.md`, to be
  written in the planning phase) rather than one file per occurrence, to keep the per-user
  active-reminder cap (FR-006) a simple directory-entry count.
- **Delivery mechanism**: A single shared background sweep, following the existing pattern
  already used for session cleanup (`services/cleanup_service.py`'s `SessionCleanupThread`) —
  one periodic checker for the whole process, never one thread per reminder. Exact sweep interval
  is a planning-phase decision (`plan.md`), bounded only by the requirement that no reminder
  fires meaningfully late under normal operation.
- **RBAC**: Reuses the existing `UserManager` role resolution (admin/godfather/client/blocked) —
  no new role or permission concept is introduced.

## User Scenarios & Testing *(mandatory)*

See `user-stories.md` for the five prioritized user stories (P1: create with approval gate, P1:
scheduled delivery / occurrence status, P2: modify existing reminder, P2: delete existing
reminder, P3: recurring reminder cadence) and their edge cases.

### Edge Cases

- **Past-dated request**: user requests a one-time reminder in the past, or a recurring
  reminder whose first occurrence (or `until` end date) is in the past → system rejects with a
  friendly message and re-prompts for a valid date, rather than silently adjusting it (FR-005).
- **Cap reached**: a godfather/admin already has 20 active reminders and requests a 21st →
  declined with a friendly message naming the cap, no partial reminder created (FR-006).
- **Ambiguous target for modify/delete**: the user's description matches more than one of their
  reminders → system lists the candidates and asks which one, mirroring the existing
  multi-match disambiguation pattern used elsewhere in this app (e.g. contact-name resolution) —
  no destructive action taken until disambiguated.
- **Missed sweep window**: the delivery mechanism was not running (e.g. container restart) when
  an occurrence became due → on the next sweep, the overdue `pending` occurrence still fires
  (late) rather than being silently skipped or auto-cancelled; the user is not notified that
  delivery was late.
- **Deleting a recurring reminder mid-series**: if scoped to the whole series, all remaining
  `pending` occurrences are cancelled; occurrences already `fired` remain as historical records,
  untouched. If scoped to a single occurrence, only that one is cancelled — the rest of the
  series continues unaffected.
- **Ambiguous single-vs-series scope**: the user asks to modify/delete a recurring reminder
  without indicating whether they mean one occurrence or the whole series → system asks before
  proceeding, rather than guessing.
- **Concurrent due occurrences**: two different reminders (same or different users) become due at
  the same time → both are delivered independently by the single shared delivery mechanism; no
  ordering guarantee between them is required.
- **Role change after creation**: a reminder's creator's role changes after the reminder was
  created (e.g. no longer godfather/admin) → the reminder still fires as scheduled (delivery is
  keyed to the creator's chat, not re-validated against current role at fire time) — see
  Assumptions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Only users whose resolved role is GODFATHER or ADMIN MAY create, view, modify, or
  delete reminders. CLIENT and BLOCKED roles MUST have no access to reminder functionality —
  requests from those roles are declined the same way other godfather/admin-only tools are
  declined today.
- **FR-002**: System MUST support creating a reminder entirely through natural conversation: the
  user states intent to create a reminder, and the AI guides the user through specifying all
  required details (reminder message text, and either a one-time target date/time or a full
  recurrence rule) before proceeding to approval.
- **FR-003**: Before persisting a new reminder, system MUST present a summary of the reminder's
  details and require the user's explicit approval (yes/no), reusing the existing approval-gate
  UX (typed reply or WhatsApp button tap, per Feature 022/047).
- **FR-004**: On approval, system MUST persist the reminder to durable storage and confirm
  creation to the user. On decline, no reminder is created and no partial state persists.
- **FR-005**: A one-time reminder's target date/time, and a recurring reminder's first occurrence
  and (if set) `until` end date, MUST NOT be in the past at the moment of creation. A request
  that would violate this MUST be rejected with a friendly message and the user re-prompted for a
  valid date — never silently adjusted or truncated to "now."
- **FR-006**: System MUST enforce a maximum of 20 active reminders per user (godfather/admin
  identity, tracked independently — not a shared system-wide pool). A reminder series (one-time
  or recurring) counts as one against this cap regardless of how many occurrences it will
  generate. A creation request that would exceed the cap MUST be declined with a friendly message
  naming the limit, not silently dropped or queued.
- **FR-007**: A reminder MAY be one-time or recurring. Recurring reminders MUST support: an
  interval (every N days/weeks/months), for weekly cadence one or more selected days of the
  week, for monthly cadence either a fixed day-of-month or an "Nth weekday of month" pattern
  (e.g. "first Monday"), and an end condition of never / after N occurrences / until a specific
  date. Yearly cadence is explicitly out of scope.
- **FR-008**: System MUST deliver a reminder's message as a proactive outbound WhatsApp message
  to the same chat the reminder was created from, at or after its due date/time. Delivery MUST
  originate from a single shared background mechanism common to all reminders and all users —
  the number of active reminders MUST NOT change the number of concurrent delivery mechanisms
  running.
- **FR-009**: Each occurrence of a reminder MUST be tracked with its own status — `pending` or
  `fired` — set independently per occurrence, so a recurring reminder's history of past firings
  is individually inspectable regardless of the reminder's own overall state.
- **FR-010**: System MUST support modifying or deleting an existing reminder entirely through
  natural conversation at any time: the user states intent → system helps identify the correct
  reminder (disambiguating among candidates if the description matches more than one) → if the
  target is part of a recurring series, and the user's request doesn't already make it
  unambiguous, system asks whether the action applies to a single occurrence or the whole series
  → for a modification, system guides the user through which field(s) to change → system requires
  the same explicit approval gate as creation (FR-003) before applying the change or deletion.
- **FR-011**: A user MAY modify or delete reminders they personally created, and MAY additionally
  modify or delete a reminder created by any other GODFATHER- or ADMIN-role user (fully symmetric
  cross-user override) — not restricted to any one directional precedence.
- **FR-012**: Modify/delete on a recurring reminder MUST support both scopes:
  - **Single occurrence**: deleting one `pending` occurrence cancels only that occurrence — the
    rest of the series is unaffected and continues generating/firing on schedule. Modifying one
    `pending` occurrence changes only that occurrence's due datetime and/or message text (a
    Detached occurrence) without altering the Recurrence Rule or any sibling occurrence.
  - **Whole series**: deleting the whole series cancels all of its remaining `pending`
    occurrences (including any Detached occurrences); occurrences already `fired` MUST remain as
    unmodified historical records regardless. Modifying the whole series changes the Recurrence
    Rule and/or message text going forward — it MUST NOT overwrite a Detached occurrence's own
    per-occurrence overrides, only apply to occurrences still following the series' default
    pattern.
  A single-occurrence modification's new due datetime is subject to the same past-date rejection
  as FR-005.

### Key Entities

- **Reminder**: A godfather/admin-owned record — owner (user identity), target chat, message
  text, schedule (either a single target datetime, or a Recurrence Rule), created-at timestamp,
  and overall status (active/cancelled).
- **Recurrence Rule**: Interval count, cadence unit (day/week/month), weekday selection (weekly
  cadence only), day-of-month-or-Nth-weekday pattern (monthly cadence only), end condition
  (never/after-N-occurrences/until-date).
- **Occurrence**: One scheduled firing belonging to a Reminder — due datetime, status
  (pending/fired/cancelled), (once fired) the actual delivery timestamp, and, if individually
  modified, its own overriding due datetime/message text (Detached occurrence) distinct from
  what the parent Recurrence Rule would otherwise generate.

## Assumptions

- **Delivery target is always the creator's own chat**: no capability to set a reminder that
  fires to a *different* person's chat — that would overlap with `013-proactive-whatsapp-messaging-core`
  (out of scope, see Scope section).
- **Edit/delete granularity is single-occurrence or whole-series, not "this and following"**:
  unlike some calendar apps' three-way "this occurrence" / "this and following occurrences" /
  "entire series" distinction, this feature supports only the first and third — a two-way choice.
  "This and following" (i.e. split a series at a point and apply changes only from there
  onward) is a narrower future enhancement if requested, not built here.
- **Role re-validation at fire time**: a reminder fires based on its stored creator/chat identity
  regardless of that user's *current* role at delivery time — RBAC is enforced at
  creation/modification/deletion time only (FR-001/FR-011), not re-checked per occurrence.
- **Sweep interval**: the exact polling cadence of the single shared delivery mechanism (FR-008)
  is a planning-phase decision, not fixed by this spec — only the "no per-reminder mechanism"
  constraint is a hard requirement here.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A godfather/admin user can create a one-time reminder end-to-end — state intent,
  guided detail capture, approval, confirmation — within a single conversational exchange, with
  no need to know or type any internal identifier.
- **SC-002**: 100% of due reminder occurrences are delivered using exactly one shared delivery
  mechanism per running environment, regardless of how many reminders exist across all users
  (bounded by the per-user cap in FR-006).
- **SC-003**: A user can locate, modify, and cancel an existing reminder through natural
  conversation alone — including a single occurrence of a recurring series, or the whole series —
  and including when their description is ambiguous, without needing to know or type any
  internal identifier.
- **SC-004**: 0% of created reminders (one-time or recurring) ever have a start time or first
  occurrence in the past — verified across both reminder types at creation time.
- **SC-005**: Recurring reminder occurrences fire matching their configured cadence (daily,
  weekly with selected weekdays, monthly with day-of-month or Nth-weekday) and end condition
  (never/after-N/until-date), with each occurrence individually trackable as pending or fired,
  matching standard calendar-app (Outlook/Google Calendar) recurrence semantics.

## Related work

- `specs/backlog/008-scheduled-proactive-chats/` and
  `specs/backlog/013-proactive-whatsapp-messaging-core/` — the general proactive-messaging
  framework this feature deliberately does not build (see Scope).
- `specs/done/022-explicit-approval-for-document-creation/` and
  `specs/done/047-whatsapp-interactive-approval-buttons/` — the approval-gate UX pattern this
  feature reuses for reminder create/modify/delete.
- `specs/done/033-ledger-event-persistence/` (via `managers/ledger_event_manager.py`) —
  the one-file-per-entity storage pattern this feature's Technology Choices follows.
- `specs/backlog/055-multiple-clients-godfathers/` — relevant context for FR-011's cross-role
  override reasoning (multiple godfather/admin identities existing simultaneously).
