# Bundle: Features 064, 066, 071, 099

**Branch**: `feature/f64-f66-f71-f99-f100-b72-b73` · **Specified**: 2026-10-09
**Status**: Specified - `speckit.clarify` / `plan` / `tasks` pending

One SpecKit pass for four small items, taken in this order: **064** (offer a 320 after bank evidence) -> **066** (Bit / PayBox / cheques / cash, deposit data-model flip) -> **071** (single-call PDF) -> **099** (dual-document cancellation of a 320). Each keeps its own spec, user stories and approved acceptance scenarios in its own folder.

## Process agreed with the human operator
1. SpecKit run once for the bundle (sub-files per item are fine).
2. Clarification and acceptance scenarios were done per item (complete, approved 2026-10-09).
3. Tasks up to the `billed`/`expensive` tests are done together; unit/integration keep their RED/approval gates.
4. `billed` and `expensive` tests are written and run jointly at the end; every `expensive` run still needs its own fresh approval, one at a time.

## Out of the bundle
Feature 100 (stays in progress, someone else's), bugfix-073 (stays in progress, someone else's), bugfix-072 (closed obsolete 2026-10-09).

## Shared decisions
Backbone pipeline only for 064 / 066 / 099 (071 is shared media code). No feature flags. No release or deploy decisions are made here (human-only). Ledger schema-version bump (066) is the human's decision.

## Cross-item notes
- 064's trigger widens when 066 ships (Bit, PayBox, cheques); cash is text and never triggers the image offer.
- 066's type flip touches the ledger, webapp, player, reconciliation and many existing tests (66-9); 071 makes the per-page PDF tests obsolete (71-9). All such edits need human sign-off.
- Sanity additions: 64-1 and 99-1.

## Open points to resolve at plan time
Negative 400 accepted by the Morning sandbox (099) · real PDF limits and `ai_vision_model` PDF support, by a real call (071) · cheque details Morning stores (066) · whether existing PDF E2E tests use the Backbone path (071) · schema-version number (066, human).
