# User Stories: Feature 092 (Clients Tab — Resolution Corrections & Explicit Line Status)

Acceptance scenarios below are the **approved** set from `spec.md` (approved 2026-10-03). They
run as Playwright tests in `apps/webapp/e2e/tests-clients/`, using a seeded fixture and the
Morning **sandbox**. No OpenAI is involved, so the `billed`/`expensive` tiers don't apply.

---

## US1 — Close a line without faking its numbers (P1; spec R5, R6; absorbs bugfix-068)
**As** the firm's operator, **I want** to mark a client "done" with one click, **so that** it
leaves my open-work sections while its agreed and paid amounts stay true.

- **Given** a red line (agreed ₪10,000, paid ₪2,000), **when** I click **לסגור**, **then** it
  moves to the green section and still shows ₪10,000 / ₪2,000. *(UAT 1)*
- **Given** that closed line, **when** I click **לפתוח**, **then** it returns to red. *(UAT 1)*
- **Given** a green line where agreed equals paid, **when** I click **לפתוח**, **then** it moves
  to **לקוחות פעילים**. *(UAT 2)*

## US2 — Classify a line as "check" or "active" (P1; spec R7, R8, R9)
- **Given** any non-gray line, **when** I click **לבדוק**, **then** it moves to the blue
  section. *(UAT 3)*
- **Given** any non-gray line, **when** I click **לקוח פעיל**, **then** it moves to the
  light-blue section. *(UAT 3)*
- **Given** a line, **when** I type `לבדוק` or `לסגור` into its comment and save, **then** its
  section doesn't change. *(UAT 3)*
- **Given** a gray (past) line, **then** none of the four buttons are shown. *(UAT 4)*

## US3 — Nothing moves on deploy (P1; spec R10)
- **Given** lines that are blue, light blue or closed-green today because of their comment,
  **when** the new version first loads, **then** every one is in the same section, with its
  comment text unchanged. *(UAT 5)*

## US4 — Resolve "Unknown" events one by one (P2; spec R2)
- **Given** three ledger events with no client name, **then** the resolve list shows three
  separate lines, each named `Unknown-<event_id>`. *(UAT 6)*
- **Given** I map two of them to different clients, **then** each client's totals grow by exactly
  that event's amount. *(UAT 6)*
- **Given** a fourth no-name event arrives with an older date, **then** it appears as a new line
  and the first three keep their names and mappings. *(UAT 6)*

## US5 — Undo a wrong name mapping (P2; spec R3)
- **Given** I mapped "Yisrael I" to "Israel Israeli", **when** I unlink it from Israel Israeli's
  line, **then** the alias disappears from that line, the totals revert, and "Yisrael I" is back
  in the resolve list with its note. *(UAT 7; also covers `Unknown-<event_id>` names, UAT 6)*

## US6 — Drop a name from the resolve list (P3; spec R1)
- **Given** an unresolved name, **when** I click **הסר מהרשימה**, **then** it disappears and
  stays gone after a refresh. *(UAT 8)*

## US7 — ESC closes the client dropdown (P3; spec R4)
- **Given** the client dropdown is open, **when** I press Escape, **then** it closes and nothing
  is mapped. *(UAT 9)*
