# User Stories: 102 - Calendar Reminders as WhatsApp Events (.ics)

**Status**: Acceptance scenarios APPROVED by the user, 2026-10-15 (as written below). `speckit.plan` may start.

**Actors**: **User** (godfather/admin, WhatsApp, Hebrew), **DeniDin**, **Green API** (dev instance).
**Scope**: one-time reminders. **Tiers**: `billed` unless marked manual.

---

### Story 1 - A new reminder also arrives as a calendar file (P1)
1. **UAT 1.1** - User: "תזכיר לי ביום שני ב-11:00 דיון בבית המשפט". DeniDin shows the existing
   reminder approval; User approves.
   **Then** the reminder is in `reminders.db`, and DeniDin sends a `.ics` that parses as valid
   iCalendar with: `SUMMARY` = `דנידין תזכורת: דיון בבית המשפט`, DTSTART = DTEND = Monday 11:00
   Asia/Jerusalem (TZID only, **no embedded VTIMEZONE component**), **no VALARM**, UID = the reminder's id, SEQUENCE 0.
2. **UAT 1.2** - User declines the approval. **Then** no reminder and no `.ics`.
3. **UAT 1.3** - A recurring request ("כל יום ראשון ב-9:00"). **Then** DeniDin sends one `.ics` carrying the `RRULE`, and the 054 reminder is stored as today.
4. **UAT 1.4** - The reminder's due time arrives. **Then** the 054 text nudge is still delivered.

### Story 2 - Modify / delete keeps the calendar honest (P1)
1. **UAT 2.1** - User changes the time of that reminder. **Then** DeniDin sends an updated `.ics`
   (same UID, `SEQUENCE+1`); the calendar entry moves, no duplicate (Gate Zero 2: verified on Android).
2. **UAT 2.2** - User deletes it. **Then** DeniDin sends a `METHOD:CANCEL` `.ics`; the entry is removed.
3. **UAT 2.3** - User changes one occurrence of a recurring reminder. **Then** the file carries the master + an override (`RECURRENCE-ID`); only that occurrence moves.
4. **UAT 2.4** - User skips one occurrence. **Then** the file carries the master with an `EXDATE`; only that occurrence disappears and earlier single-occurrence changes are kept.
5. **UAT 2.5** - User deletes the whole recurring reminder. **Then** a `METHOD:CANCEL` removes every occurrence.

### Story 3 - Device import and safety (P2)
1. **UAT 3.1 (manual, iOS and Android)** - tapping the `.ics` opens the calendar sheet with the title
   and time, and no alert. (Android verified by the PM in Gate Zero 2; iOS not tested - out of scope.)
2. **UAT 3.2** - a client (non godfather/admin) cannot create reminders; no `.ics` is ever sent.
3. **UAT 3.3** - a forced file-send failure: the reminder is still stored and the user is told the
   calendar file could not be sent.

### Story 4 - Asking for the calendar file of an existing reminder (P1)
1. **UAT 4.1** - A reminder exists. User: "תשלח לי קובץ יומן לתזכורת של הדיון". **Then** DeniDin sends the `.ics` for that reminder (same UID as before, no approval step).
2. **UAT 4.2** - Two reminders match the description. **Then** DeniDin asks which one before sending anything.
3. **UAT 4.3** - A reminder that does not exist. **Then** DeniDin says so and sends no file.

### Story 5 - DeniDin offers the file when listing reminders (P1)
1. **UAT 5.1** - User: "אילו תזכורות יש לי?". **Then** DeniDin lists them and, in the same reply, offers a calendar file; nothing is sent yet.
2. **UAT 5.2** - User accepts. **Then** the file(s) arrive.
3. **UAT 5.3** - User ignores or declines the offer. **Then** nothing is sent and no further prompt.
4. **UAT 5.4** - An unrelated question (for example about an invoice). **Then** no calendar offer.

