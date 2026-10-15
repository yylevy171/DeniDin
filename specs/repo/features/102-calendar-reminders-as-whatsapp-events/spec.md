# Feature 102: Calendar Reminders as WhatsApp Events (.ics alongside reminders.db)

**Feature Branch**: `feature/102-calendar-reminders-as-whatsapp-events`  
**Status**: Done (PR pending)  
**Priority**: P2 (Customer Experience & Architectural Resilience)  
**User stories / acceptance scenarios**: `user-stories.md` (scenarios approved 2026-10-15)  
**Origin**: CEO Request (2026-10-15) — "calendar reminders as whatsapp events instead of (or additional to) reminders.db"  
**Depends on**: Feature 054 (Reminders Functionality & Management), Feature 063 (Dynamic Capability Backbone)  

---

## 1. Executive Summary & Business Intent

In **Feature 054**, DeniDin introduced conversational reminder scheduling. The current implementation relies on:
1. An internal SQLite database (`{data_root}/reminders/reminders.db`) storing RFC5545 recurrence records.
2. An in-process `APScheduler` background thread sweeping the database every 5 minutes.
3. Unprompted proactive WhatsApp text delivery (`bot.api.sending.sendMessage`) when an occurrence is due.

While functional, this architecture presents clear operational and UX limitations:
- **No Native Device Calendar Integration**: A WhatsApp text message does not sync with the user's phone calendar (Google Calendar, Apple Calendar, Outlook). The user does not see their reminders in their daily schedule widget or get native OS calendar alarms.
- **Downtime & Blast Radius**: If the DeniDin server container is stopped, restarted, or experiencing downtime, scheduled reminders can be delayed until a startup recovery sweep runs.
- **Operational Overhead**: Backing up `reminders.db`, handling SQLite write concurrency, maintaining APScheduler worker threads, and tracking fired occurrences state add architectural weight.

**The Goal of Feature 102**:  
Enable DeniDin to generate and deliver calendar events directly into WhatsApp as rich, actionable calendar items—either as **an alternative (stateless)** or as **an addition (hybrid)** to the persistent `reminders.db` engine.

---

## 2. Gate Zero Results (2026-10-15, real dev instance 7105257767)

| Question | Result |
| :-- | :-- |
| Does Green API have a native WhatsApp Event send method? | **No evidence of one.** The docs list none; no SDK or community project mentions one; 25 guessed method names (`sendEvent`, `sendEventMessage`, `createEvent`, ...) all returned the same nginx 403 as a made-up method, while real method `sendMessage` returned its own 400 validation error (so credentials/instance were good). |
| Does Green API deliver an incoming native event? | **No.** A real event sent from the PM's phone produced no webhook at all; a plain text sent right after did (`textMessage`). |
| Does `sendFileByUpload` deliver a `.ics` and does the phone open it? | **Yes.** HTTP 200; the PM tapped the file in WhatsApp and the phone's calendar opened with the event. |

**Decision (PM, 2026-10-15)**: native event cards are not achievable; the feature ships as a **`.ics` file only**.
No Google Calendar link, no native event card.

Known gap: the dev Green API instance is over its monthly quota (`readchat`, 100/100) - sends were unaffected.

---

### Gate Zero 2 - update / cancel / recurring on a real phone (PM's Android, 2026-10-15)

All files sent via `sendFileByUpload` to the dev chat and tapped in WhatsApp; the same `UID` is the key.

| Case | Result |
| :-- | :-- |
| One-time: create; update (same UID, `SEQUENCE+1`, new time); cancel (`METHOD:CANCEL`, `STATUS:CANCELLED`) | **All work.** Update moves the existing entry (no duplicate); cancel removes it. |
| Zero-length event, no alert | **Works.** Shown with no default alert. |
| Weekly series (`RRULE:FREQ=WEEKLY;COUNT=4`) created across the 25 Oct clock change | **Works.** All 4 occurrences at the right time. |
| Update whole series (same UID, `SEQUENCE+1`) | **Works**, all 4 move, including after the clock change. |
| Move one occurrence (override VEVENT, same UID + `RECURRENCE-ID`) | **Works**, only that one moves. |
| Delete one occurrence (`EXDATE` on the master, sent together with the existing overrides) | **Works**, only that one is removed, the moved one keeps its change. |
| Cancel whole series (`METHOD:CANCEL`, same UID) | **Works**, all occurrences removed. |

**Defect found and resolved: do NOT embed a `VTIMEZONE`.** With the `icalendar` library's generated
`VTIMEZONE` embedded, updating a recurring series shifted every occurrence one hour earlier on Android
(14:00 -> 13:00; reproduced on a series with no clock change in range). Creating a series and updating a
one-time event were unaffected. The same update **without** an embedded `VTIMEZONE` (only
`TZID=Asia/Jerusalem` on each time) was exact. Final rule: times carry `TZID=Asia/Jerusalem` only.

| One file holding several events (one-time, weekly series, one-time; each its own `UID`) | **Works.** All 3 import from a single tap. |
| Later file with only one of those `UID`s (update) | **Works.** Only that event changes; the others are untouched. |

Not tested: iOS and other calendar apps; and re-importing an **unchanged** reminder file (an on-demand re-send,
higher `SEQUENCE`, same content) onto a phone that already has the entry. The PM's decision: Android is what counts.

---

## 3. PM Functional Requirements (revised 2026-10-15)

- **REQ-102-01 (a calendar file with every reminder)**: whenever DeniDin creates a reminder (Feature 054),
  one-time **or recurring**, it also sends a `.ics` file for it into the chat the reminder was created from
  (`delivery_chat_id`; for a later modify/delete/on-demand file, the chat the user is asking in),
  **alongside** `reminders.db`, never instead of it: the reminder is stored and
  delivered by the 054 text nudge exactly as before. A recurring reminder is a single `.ics` carrying its
  `RRULE` (a series), not one file per occurrence.
- **REQ-102-02 (shape of the event, mirrors DeniDin reminders)**:
  - Zero duration: `DTEND` = `DTSTART`.
  - No alert/`VALARM` of any kind.
  - `SUMMARY` is always `דנידין תזכורת: <reminder text>`.
  - Times as `TZID=Asia/Jerusalem` with **no embedded `VTIMEZONE`** (Gate Zero 2 defect above).
  - `UID` = the reminder's own stable RFC5545 UID; `SEQUENCE` is a per-reminder counter: every file generated for a
    reminder (create, change, delete, on-demand) carries a value strictly higher than every earlier file for it
    (the first is 0); no location or description required.
  - File name `reminder_<id8>.ics` (one reminder) or `reminders_<YYYYMMDD>.ics` (several), no caption.
- **REQ-102-03 (approval)**: no new approval. The `.ics` is sent when the existing 054 approval is given.
- **REQ-102-04 (modify / delete - verified working)**: every change to a reminder that has an `.ics`
  sends a new `.ics`, always the complete picture of the reminder in one file:
  - modify the whole reminder: same `UID`, `SEQUENCE+1`, new values;
  - modify one occurrence of a recurring reminder: the master plus an override `VEVENT` with
    `RECURRENCE-ID` (all existing overrides are re-sent every time);
  - delete one occurrence: the master with an `EXDATE`, plus the existing overrides;
  - delete the reminder (one-time or whole series): `METHOD:CANCEL` + `STATUS:CANCELLED`,
    `SEQUENCE+1`.
  `reminders.db` already holds the master and per-occurrence exceptions (`reminder_exceptions`) from
  which these files are generated.
- **REQ-102-05 (scope)**: one-time and recurring reminders alike.
- **REQ-102-06 (RBAC)**: same as 054 - GODFATHER/ADMIN only; no new tool is exposed to any other role.
- **REQ-102-07 (failure)**: if the file send fails, the reminder is still stored (or changed/deleted) and
  the user is told plainly that the calendar file could not be sent.
- **REQ-102-08 (prompt boundaries)**: the backbone prompts (`config/prompts/`: `cap_reminders_read.md`,
  `cap_reminders_write.md`, the reminder flows, a new calendar-file flow and `backbone.md`) state when the
  calendar file applies (automatic after a reminder write; on request; offered after listing), when it does NOT
  (never for invoices, clients, documents, the ledger or agreements; never to interpret a confirmation reply),
  and that ambiguity is resolved by asking. Every other tool-bearing capability prompt excludes calendar files
  back (both directions, per the tool-bearing-feature rule). `runtime_constitution.md` no longer exists.

- **REQ-102-09 (on-demand .ics for an existing reminder)**: a user can ask for the calendar file of any
  existing reminder ("תשלח לי קובץ יומן לתזכורת של ..."). DeniDin finds it and generates and sends the
  `.ics` (same `UID`, a strictly higher `SEQUENCE` than any earlier file, so importing it onto a phone that
  already has the entry is expected to update it rather than duplicate it - an unchanged re-send is not yet
  verified on a phone, see section 2). It is read-only, so it needs **no approval**. If several reminders
  match, DeniDin asks which one (never guesses). Applies to one-time and recurring reminders.
- **REQ-102-10 (offering the .ics)**: when the user asks about their reminders in general, or asks to list
  them (`list_reminders`), DeniDin answers as today and then **offers** the calendar file (in the same
  reply): for one specific reminder, for several, or for all the listed ones. It sends nothing until the
  user accepts. It does not offer in any unrelated context.

Removed from the earlier PM draft: the `hybrid`/`stateless`/`db_only` modes, the Google Calendar link,
the 15-minute alarm, native event cards, location/end-time fields, the embedded timezone definition.

---

## 4. Decisions (PM, 2026-10-15)

1. **No feature flag.**
2. The transient `.ics` is authored exactly as the Feature 083 docx is (same temp-file handling, then `sendFileByUpload`).
3. The `.ics` is sent **after** the confirmation text of the reminder creation.
4. An open-ended recurring reminder (no `COUNT`/`UNTIL`) produces an open-ended series on the calendar - intended.
5. Modifying/deleting a reminder created before this feature: **send the update/cancel `.ics` as usual**.
6. "All my reminders" (REQ-102-10): **one `.ics` file with several events**, each with its own stable `UID` (Gate Zero 2: verified on Android).
7. The offer in REQ-102-10 is asked with the backbone's `approval_with_yes_no_buttons` capability (stateless, yes/no buttons or a typed "כן"/"לא"), e.g. "לייצא את התזכורות שלך לקובץ יומן (ics)?". A yes sends the file; a no ends it.
8. Backbone only: the legacy `AIHandler` path and the backbone feature flag are gone from master (merged 2026-10-15); nothing in this feature targets a legacy path.

## 5. Open items

None.
