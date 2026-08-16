# User Stories: Reminders — Functionality and Management

**Feature Branch**: `feature/054-reminders-functionality-mgmt`
**Related Spec**: `spec.md` (same directory)

---

### User Story 1 - Create a one-time reminder with guided detail capture and approval (Priority: P1)

As a godfather/admin user, I want to tell DeniDin I want a reminder and have it walk me through
the details (what to say, when to say it), then confirm before it's actually saved, so I don't
accidentally create a wrong or incomplete reminder.

**Why this priority**: This is the entry point for the entire feature — without creation, there
is nothing to deliver, modify, or delete.

**Independent Test**: As a godfather, say "remind me to call the accountant tomorrow at 10am."
Verify the AI asks for/confirms the message text and exact date/time, presents a summary, and
only persists the reminder after an explicit "yes" (typed or button tap).

**Acceptance Scenarios**:

1. **Given** a godfather/admin user with fewer than 20 active reminders, **When** they state
   intent to create a reminder with a future date/time and message text, **Then** the AI
   confirms/fills in any missing detail, presents a summary, and asks for approval.
2. **Given** the approval summary has been presented, **When** the user replies "yes" (typed or
   button), **Then** the reminder is persisted to durable storage and the user receives a
   confirmation.
3. **Given** the approval summary has been presented, **When** the user replies "no" (typed or
   button), **Then** no reminder is created and no partial state persists.
4. **Given** a godfather/admin user requests a reminder for a date/time in the past, **When** the
   AI processes the request, **Then** it declines with a friendly message and asks for a valid
   future date, without creating anything.
5. **Given** a client or blocked-role user, **When** they attempt to create a reminder, **Then**
   the request is declined the same way other godfather/admin-only tools are declined.
6. **Given** a godfather/admin user who already has 20 active reminders, **When** they attempt to
   create a 21st, **Then** the request is declined with a friendly message naming the cap.

---

### User Story 2 - Scheduled delivery via a single shared mechanism, with per-occurrence status (Priority: P1)

As a godfather/admin user, I want DeniDin to actually message me when a reminder becomes due, so
the reminder is useful rather than just a stored note — and I want this to keep working no matter
how many reminders exist system-wide.

**Why this priority**: Delivery is the entire point of a reminder; without it the feature has no
observable value. Tied for P1 with creation because a reminder that's created but never fires is
equivalent to not having the feature at all.

**Independent Test**: Create a one-time reminder due a few minutes out. Wait for it to become due.
Verify the reminder text arrives as a WhatsApp message in the same chat it was created from, and
that the occurrence's status changes from `pending` to `fired` at that point — without a
dedicated new background process being spun up per reminder.

**Acceptance Scenarios**:

1. **Given** a reminder occurrence whose due date/time has arrived, **When** the shared delivery
   mechanism next checks for due occurrences, **Then** the reminder's message text is sent as a
   proactive WhatsApp message to the chat it was created from, and the occurrence's status
   changes from `pending` to `fired`.
2. **Given** multiple reminders (from the same or different users) are simultaneously due,
   **When** the delivery mechanism runs, **Then** all are delivered, using the same single shared
   mechanism rather than one instance per reminder.
3. **Given** a reminder occurrence became due while the delivery mechanism was not running (e.g.
   during a restart), **When** the mechanism resumes, **Then** the overdue `pending` occurrence
   still fires (late) rather than being silently skipped.
4. **Given** a recurring reminder with multiple past occurrences, **When** its occurrence history
   is inspected, **Then** each occurrence shows its own independent status (`pending`/`fired`),
   not one shared status for the whole series.

---

### User Story 3 - Modify an existing reminder (Priority: P2)

As a godfather/admin user, I want to change a reminder I already created (its time, message, or
recurrence) without deleting and recreating it, and have DeniDin help me find the right one if I
have several.

**Why this priority**: Necessary for the feature to be usable long-term (plans change), but the
feature is still valuable with only create+delete if this were deferred — hence P2, not P1.

**Independent Test**: With two or more existing reminders, ask to change one by a partial
description (e.g. "move my accountant reminder to 3pm instead"). Verify the system identifies the
correct reminder (disambiguating if needed), confirms the specific change, and only applies it
after approval.

**Acceptance Scenarios**:

1. **Given** a user has exactly one reminder matching their description, **When** they ask to
   modify it, **Then** the system confirms which reminder was matched, asks which field(s) to
   change, presents a summary of the change, and requires approval before applying it.
2. **Given** a user's description matches more than one of their reminders, **When** they ask to
   modify "it", **Then** the system lists the candidates and asks which one before proceeding.
3. **Given** an approved modification to a recurring reminder's recurrence rule, **When** the
   change is applied, **Then** it applies to the whole series (all remaining `pending`
   occurrences) — already-`fired` occurrences are untouched.
4. **Given** any GODFATHER- or ADMIN-role user, **When** they ask to modify a reminder created by
   a different GODFATHER- or ADMIN-role user, **Then** the system permits it (fully symmetric
   cross-user override — not restricted to any one directional precedence).

---

### User Story 4 - Delete an existing reminder (Priority: P2)

As a godfather/admin user, I want to cancel a reminder I no longer need, including a whole
recurring series, with the same "help me find it" assistance as modification.

**Why this priority**: Same tier as modification — necessary for long-term usability, not
required for the MVP delivery loop itself.

**Independent Test**: Ask to delete a specific existing reminder by description. Verify the
system identifies it (disambiguating if needed), confirms the deletion, and only removes it (and
cancels any remaining pending occurrences) after approval.

**Acceptance Scenarios**:

1. **Given** a user has exactly one reminder matching their description, **When** they ask to
   delete it, **Then** the system confirms which reminder was matched, presents the deletion for
   approval, and only deletes it once approved.
2. **Given** a recurring reminder with some `fired` and some `pending` occurrences, **When** it is
   deleted, **Then** all remaining `pending` occurrences are cancelled and `fired` occurrences
   remain as unmodified historical records.
3. **Given** the deletion summary has been presented, **When** the user declines, **Then** the
   reminder (and all its occurrences) remain unchanged.

---

### User Story 5 - Recurring reminders with standard calendar-app cadence (Priority: P3)

As a godfather/admin user, I want to set a reminder that repeats — daily, weekly on specific days,
or monthly on a date or a pattern like "first Monday" — with a defined end condition, so I don't
have to manually recreate a routine reminder every time it fires.

**Why this priority**: Adds meaningfully to the feature's value but a functioning one-time-only
reminder system (Stories 1-4) already delivers a usable MVP — hence P3, buildable last.

**Independent Test**: Create a weekly reminder for "every Monday and Thursday, for 5 occurrences."
Verify each occurrence is scheduled correctly, fires independently at the right date/time, and the
series stops after the 5th occurrence with no 6th ever created.

**Acceptance Scenarios**:

1. **Given** a user requests a daily reminder every N days, **When** approved, **Then**
   occurrences are generated on that interval indefinitely (if end condition is "never") or bounded
   by the stated end condition.
2. **Given** a user requests a weekly reminder on specific day(s) of the week, **When** approved,
   **Then** an occurrence is generated for each selected weekday per week, per the interval.
3. **Given** a user requests a monthly reminder either on a fixed day-of-month or a pattern like
   "first Monday", **When** approved, **Then** occurrences are generated matching that pattern
   each month, per the interval.
4. **Given** a recurring reminder with an "after N occurrences" end condition, **When** the Nth
   occurrence fires, **Then** no further occurrences are generated.
5. **Given** a recurring reminder with an "until <date>" end condition, **When** an occurrence's
   due date would fall after that date, **Then** it is never generated/fired.
6. **Given** a user requests a yearly-recurring reminder, **When** the request is processed,
   **Then** the system explains yearly cadence is not supported (out of scope) rather than
   silently approximating it with another cadence.
