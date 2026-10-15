# Feature 102: Calendar Reminders as WhatsApp Events (Alternative/Hybrid to reminders.db)

**Feature Branch**: `feature/102-calendar-reminders-whatsapp-events`  
**Status**: Backlog  
**Priority**: P2 (Customer Experience & Architectural Resilience)  
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

## 2. Strategic Alternatives: "Instead Of" vs. "Additional To"

| Dimension | Option A: "Instead Of" (Stateless Generator) | Option B: "Additional To" (Hybrid Mode - Recommended) |
| :--- | :--- | :--- |
| **Persistence** | Zero server state. DeniDin does not store the event in `reminders.db`. | Dual storage: Persisted in `reminders.db` AND delivered as an event immediately. |
| **Scheduler** | APScheduler background worker eliminated or bypassed for events. | APScheduler remains active for proactive WhatsApp reminder pings at due time. |
| **Device Calendar** | User imports event into iOS/Android Calendar via 1-tap. | User imports event into device calendar PLUS receives a proactive bot nudge. |
| **Queryability** | DeniDin cannot list (`list_reminders`) or cancel past reminders. | Full conversational management retained (`list_reminders`, `modify_reminder`, `delete_reminder`). |
| **Server Failure Impact** | **Zero risk**. Reminder alarms are handled natively by the user's device/OS. | **Low risk**. Even if the server dies, the user's device alarm will still fire. |
| **Complexity** | Extremely low server footprint; high UX dependency on user tapping import. | Moderate: Combines existing Feature 054 flow with event dispatch. |

### PM Recommendation:
Implement a configurable strategy (`mode: "hybrid" | "stateless" | "db_only"`, defaulting to `"hybrid"`). This offers the highest customer value: the lawyer gets immediate device calendar integration to manage their week, while DeniDin maintains its executive assistant role by sending a WhatsApp nudge when the moment arrives.

---

## 3. WhatsApp Delivery Mechanism: Technical Realities & Constraints

### 3.1 WhatsApp Native Events (`eventMessage`) vs. Gateway Reality
WhatsApp native groups and communities support native **Events** (`eventMessage` in the WhatsApp protocol, containing name, description, start/end time, location, call links, and RSVP buttons).
* **The Green API Constraint**: DeniDin connects to WhatsApp via **Green API**. Green API's REST API natively supports `sendMessage`, `sendFileByUrl`, `sendLocation`, `sendContact`, and `sendPoll`. Green API does **not** currently document an official REST endpoint for constructing raw WhatsApp protobuf `eventMessage` cards.
* **Engineering Action (Spike / Gate Zero)**: Claire's team must verify whether Green API has added or supports an unannounced `sendEvent` endpoint or custom JSON payload.

### 3.2 The Reliable Cross-Platform Solution: `.ics` (iCalendar) Document Dispatch
DeniDin already bundles `icalendar` (RFC5545) in `apps/denidin-app`.
1. DeniDin generates a clean, standard `.ics` file containing the `VEVENT`, local timezone (`Asia/Jerusalem`), alarm trigger (`VALARM`, e.g., 15 minutes before), and meeting notes.
2. DeniDin sends this file via Green API's `sendFileByUrl` / `uploadFile` (e.g., `Meeting_with_Client.ics`).
3. **User Experience**: On both iOS and Android, tapping an `.ics` attachment in WhatsApp natively opens the operating system's Calendar sheet with a single-tap **"Add to Calendar"** button.

### 3.3 Complementary Quick-Link: One-Tap Calendar Web URLs
In the accompanying message text, DeniDin can provide a direct Google Calendar template URL:
`https://calendar.google.com/calendar/render?action=TEMPLATE&text=...&dates=...&details=...`
This allows instant web calendar addition without downloading a file on desktop clients.

---

## 4. PM Functional Requirements

- **REQ-102-01 (Intent & Parameter Extraction)**:
  The AI must extract reminder parameters from natural Hebrew/English dialogue:
  - Event title / summary (e.g., "פגישה עם לקוח", "דיון בבית משפט")
  - Start date and time (in Israel local time `LOCAL_TZ`)
  - Optional end date/time (defaulting to +60 minutes if unspecified for calendar events)
  - Optional location (physical address, zoom link, or courthouse)
  - Optional notes / description
- **REQ-102-02 (Interactive Approval Flow)**:
  Before dispatching the event or saving to DB, DeniDin MUST present an explicit approval summary with Yes/No interactive buttons (`approval_with_yes_no_buttons` or typed response).
- **REQ-102-03 (RFC5545 .ics Generation)**:
  Upon approval, the system must generate a valid `.ics` payload including:
  - `UID`, `DTSTAMP`, `DTSTART`, `DTEND`, `SUMMARY`, `DESCRIPTION`, `LOCATION`
  - A pre-configured `VALARM` (audio/display reminder 15 minutes prior to start).
- **REQ-102-04 (Event Dispatch via WhatsApp)**:
  The system must dispatch the event to the chat where the request originated (`delivery_chat_id`):
  - Primary: As a file document (`.ics`) via Green API's file transmission.
  - Secondary/Future-proof: If Green API native `eventMessage` is confirmed supported, emit native WhatsApp Event card.
  - Accompanied by a concise confirmation message containing the Google Calendar deep link.
- **REQ-102-05 (Storage Mode Configuration)**:
  Add `reminder_event_mode` to `AppConfiguration`:
  - `"hybrid"` (default): Create entry in `reminders.db` AND send WhatsApp `.ics`/event card.
  - `"stateless"`: Send WhatsApp `.ics`/event card ONLY. Do not write to `reminders.db`.
  - `"db_only"`: Legacy Feature 054 behavior (text notification only at scheduled time).
- **REQ-102-06 (RBAC Governance)**:
  Event creation must adhere to the same security gating as Feature 054: accessible strictly to `GODFATHER` and `ADMIN` roles. Unregistered or client numbers are blocked from scheduling.

---

## 5. User Acceptance Tests (UAT)

### UAT-1: Create Calendar Event with .ics Attachment (Hybrid Mode)
- **Given**: DeniDin is configured with `reminder_event_mode: "hybrid"`.
- **When**: The Godfather texts: *"תזכיר לי ביום שני הבא ב-11:00 דיון בבית המשפט השלום בתל אביב בנושא כהן"*.
- **Then**: 
  1. DeniDin parses the date, time (11:00 to 12:00), location, and summary.
  2. DeniDin displays the interactive approval summary with "כן" / "לא" buttons.
  3. Upon tapping "כן", DeniDin:
     - Persists the record into `reminders.db`.
     - Generates `court_hearing_cohen.ics`.
     - Sends the `.ics` document directly to the WhatsApp chat.
     - Provides a Google Calendar one-tap web link in the message body.

### UAT-2: Stateless Event Generation
- **Given**: DeniDin is configured with `reminder_event_mode: "stateless"`.
- **When**: An Admin texts: *"תקבע לי תזכורת לפגישת ייעוץ מחר ב-16:00"*.
- **Then**:
  1. DeniDin prompts for approval.
  2. Upon approval, DeniDin dispatches the calendar `.ics` document into the chat.
  3. No record is written to `reminders.db`.
  4. Querying `list_reminders` afterwards reports 0 active database reminders.

### UAT-3: Mobile Device Import Verification
- **Given**: A user receives an `.ics` attachment sent by DeniDin on iOS or Android WhatsApp.
- **When**: The user taps the document in WhatsApp.
- **Then**: The native operating system calendar application opens with pre-filled title, time, location, and 15-minute alarm, allowing immediate saving without errors.

### UAT-4: RBAC Unauthorized Rejection
- **Given**: An unknown client phone number texts: *"Remind me about our meeting tomorrow at 10am"*.
- **When**: The message is processed by DeniDin.
- **Then**: DeniDin refuses to invoke reminder/calendar tools and responds with standard unauthorized message.

---

## 6. Open Questions & Engineering Handoff (For Claire)

1. **Green API Spike**: Can Green API send native WhatsApp `eventMessage` payloads via any undocumented endpoint, or is `.ics` document dispatch the verified production path?
2. **Media Cleanup**: Where should transient `.ics` files be stored prior to upload (`data/tmp/` vs direct memory stream to Green API)?
3. **Recurring Events in .ics**: Does the initial release support recurring RRULEs in the generated `.ics`, or should recurring series remain on `reminders.db` while one-time events get the calendar `.ics`? (PM Recommendation: Phase 1 should support one-time events; recurring `.ics` in Phase 2).
