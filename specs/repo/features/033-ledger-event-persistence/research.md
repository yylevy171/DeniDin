# Phase 0 Research: Ledger Event Persistence

**Feature**: 033-ledger-event-persistence · **Date**: 2026-07-29

Per METHODOLOGY.md §IV, Phase 0 covers technical feasibility, dependency analysis, and
constraints, before Phase 1 design (`data-model.md`, `contracts/`, `quickstart.md`).

## 1. Feasibility of matching `Events.csv`'s `event_id` scheme exactly

Verified by direct inspection of the real file (`data/events/Events.csv`, 1159 rows, all
columns) rather than assumed:

- **Format**: `{letter}{DDMMYY}{HHMM}{seq}`, confirmed via regex match against all 1159
  `מזהה_אירוע` values: 1157/1159 match `^[ABH]\d{6}\d{4}\d$` (12 chars) exactly; the
  remaining 2 are 13-char anomalies (`A040726202912`, `A040726202910`) — pre-existing
  historical exceptions, not evidence of a "grows to 2 digits" rule (superseded by direct
  user confirmation: `seq` is always a single digit).
- **Letter mapping**: Cross-tabulated `event_id[0]` against the `מקור` column for all 1159
  rows: `A`↔`הסכם` (384/384), `H`↔`חשבונית` (532/532), `B`↔`בנק` (243/243) — 100%
  consistent, no exceptions. `capture_ledger_event` only ever produces `source_type` ∈
  {`הסכם`, `בנק`}, so this feature only ever generates `A`/`B` ids.
- **Collision counter behavior**: Grouped all ids by `DDMMYY+HHMM` (ignoring letter, since
  the letter is itself already part of the full id and a different letter can't collide even
  at the same digit): found 61 groups with >1 event sharing a minute, with `seq` values not
  always contiguous from 0 (e.g. `['8','6','4','2','0']`) — the original historical
  generation algorithm is undocumented and not fully reverse-engineered, but **not required
  to be**: this feature only needs a NEW generation rule that (a) produces same-format ids,
  (b) never collides with anything DeniDin itself has already written, (c) is simple and
  auditable. Smallest-unused-digit-starting-at-0 satisfies all three without needing to
  match the historical algorithm bit-for-bit.
- **Timezone**: `Events.csv`'s `תאריך_אירוע`/`שעת_אירוע` columns have no explicit timezone
  marker. Confirmed via direct user sign-off (2026-07-29) that these are Asia/Jerusalem
  local time, not UTC — `message_timestamp` (stored UTC per CONSTITUTION §II) must be
  converted before deriving `DDMMYY`/`HHMM`/`event_date`/`event_time`.

**Conclusion**: Feasible with Python's stdlib `zoneinfo` (3.9+, already the project's
Python floor per CONSTITUTION §IV) — no new dependency needed for the UTC→Asia/Jerusalem
conversion.

## 2. Feasibility of collision-avoidance without reading `Events.csv`

Confirmed no `280726` (28/07/2026)-prefixed ids exist anywhere in the current 1159-row file
(`grep -c "280726" Events.csv` → 0) — the file's most recent entry is 24/07/2026. Since
DeniDin only ever generates ids for events happening now-or-later, and the historical file
is static (not read/written by DeniDin), collisions against it are structurally impossible
as long as DeniDin never needs to represent a *past* (pre-feature) date. This holds for
both live captures (always "now") and the one migration this feature performs (dated
2026-07-28, already confirmed collision-free against the file).

## 3. `amount` normalization feasibility

Sampled real `סכום` values across `Events.csv`: always bare integers, no currency symbol,
no thousands separators, occasionally negative (`"-7000"`, `"-532"`). Captured `amount`
text (from `capture_ledger_event`, per its own field description, deliberately verbatim/
unconverted) uses forms like `"8,000₪"`, `"₪12,500.00"`, `"1,500 ש\"ח"`. A simple
strip-and-round approach (remove `₪`/`ש"ח`/`,`, parse as float, round to int, keep sign)
covers every real example seen. No AI/LLM involvement needed or wanted here — this is
input normalization, not currency math or interpretation, and stays entirely in code per
the tool schema's own "no math" design rationale.

## 4. Dependencies

No new third-party dependencies. Uses stdlib only: `pathlib` (existing convention),
`json` (existing convention, `sort_keys=True`/`ensure_ascii=False`/`indent=2` per
CONSTITUTION §XV), `zoneinfo` (stdlib since Python 3.9, for UTC→Asia/Jerusalem conversion),
`re` (amount parsing).

## 5. Constraints

- Must not read `data/events/Events.csv` at runtime (explicit instruction) — collision
  avoidance is scoped to DeniDin's own output only (see §2).
- Must not perform AI/LLM calls for any part of persistence-layer logic (amount parsing,
  id generation) — those are deterministic code, not model output.
- No `config.feature_flags` gate needed (see spec.md Edge Cases) — this changes the
  storage location/shape of already-shipped, always-on behavior.
