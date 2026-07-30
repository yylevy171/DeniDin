# Feature Specification: Ledger Event Recognition

**Feature Branch**: `feature/024-ledger-event-recognition` (merged via PR #140, deleted after
merge — see Provenance)
**Created**: 2026-07-28 (original) · **Reconstructed**: 2026-07-30
**Status**: Done — merged, deployed, verified live (2026-07-28). Superseded in part by
Feature 026 (Ledger Event Persistence, 2026-07-29/30), which moved *where* captured events
are stored (`session.json`'s `pending_ledger_events` → `data/events/*.json`) without changing
this feature's recognition/classification behavior.

---

## Provenance (why this document exists, and why it can be trusted)

This spec was reconstructed on 2026-07-30 after a real investigation found that Feature 024
had **zero spec artifacts** anywhere in this repo's git history — no `spec.md`,
`user-stories.md`, or any file under `specs/024-*` was ever committed, on the feature branch
or anywhere else (verified: `git log --all --name-only` has no path containing "024" or
"ledger-event-recognition" across the *entire* reachable history; `git fsck --unreachable
--dangling` surfaced 11 dangling commits from that branch's stash history, none of which
touch any file under `specs/` either).

What DOES exist, and what this document is built from:

1. **The real shipped code** — commit `ae49b0e` ("feat: Ledger Event Recognition (Feature
   024) + temperature removal + model defaults"), confirmed as an ancestor of current
   `master`/`HEAD` (i.e. genuinely merged, not lost). This is the actual `LEDGER_EVENT_TOOL`
   schema and `AIHandler`/`ImageExtractor` wiring — ground truth for the data model below.
2. **`config/runtime_constitution.md`'s "Ledger Event Recognition" section**, as it existed
   in that same commit (`git show ae49b0e:apps/denidin-app/config/runtime_constitution.md`)
   — this is a detailed, carefully-reasoned classification/extraction rulebook (misclassification
   risk analysis, VAT phrasing rules, ambiguous-referent handling, payer-vs-client
   distinction, provenance/hard-pointer requirements) that reads exactly like the output of a
   real requirements/clarification process, even though it was authored directly into the
   constitution rather than a separate spec.md. This document's Requirements section below is
   a structured (`REQ-*`-numbered) restatement of that same content, not new invention.
3. **`HANDOFF.md`** (repo root, untracked, written 2026-07-28 at the end of that session) —
   a first-person session summary confirming what shipped, what was verified via a real live
   phone test, and the exact origin of what later became Feature 026. Found 2026-07-30 sitting
   untracked in the repo root the entire time (never lost, just never read until asked).
4. **The commit message itself**, which lists the real incidental fixes bundled into the same
   branch (temperature removal, model defaults, timestamp propagation, multi-capture
   handling, Morning-MCP suppression, test housekeeping).

Nothing in this document describes behavior that isn't independently verifiable in the
current codebase (`config/runtime_constitution.md`'s live "Ledger Event Recognition" section,
`ai_handler.py`'s `LEDGER_EVENT_TOOL`, and Feature 026's own spec docs, which cite this
feature as prior art throughout).

---

## User Stories Reference

Complete Given-When-Then acceptance criteria live in **`user-stories.md`**. Summary:

| # | Title | Priority |
|---|---|---|
| US1 | New fee agreement stated by text | P1 |
| US2 | Bank deposit / fee agreement arrives as an image | P1 |
| US3 | Multiple distinct entries in one message → multiple captures, never aggregated | P1 |
| US4 | Morning-MCP-sourced data doesn't produce false-positive captures | P2 |

## Terminology Glossary

- **`capture_ledger_event`**: A local OpenAI function tool (`type: "function"`, `strict:
  True`) — NOT a remote MCP server; nothing executes anywhere when the model "calls" it. The
  API returns structured, schema-validated arguments as a `function_call` output item
  alongside (never instead of) the model's normal reply.
- **`source_type`**: `הסכם` (fee-agreement event) or `בנק` (bank deposit). A third historical
  category, `חשבונית` (invoice), exists in the ledger but is never produced by this tool —
  invoices come only from the Morning API pull (see US4's out-of-scope note).
- **`event_subtype`**: For `הסכם` — `יצירה` (new)/`עדכון` (correction)/`ביטול`
  (cancellation)/`אישור-מימוש` (payment/milestone confirmed). For `בנק` — always `הפקדה`.
- **Two-call architecture**: Both the text and image capture paths make an extraction/reply
  call kept pure (no ledger tool attached), then a *separate* classification call that
  attaches `capture_ledger_event` — because reasoning models emit either a `function_call` OR
  a `message` in one turn, never both, so a real second round-trip
  (`previous_response_id` + `function_call_output`) is required to get the model's actual
  reply after a tool call.
- **Hard pointer**: The real Green API message timestamp — always the source of truth for a
  captured event's provenance, never processing time or a guess. Named for the historical
  finding (referenced in the constitution) that a prior manually-built ledger had rows whose
  timestamp had drifted from their real source message.

## Problem Statement

DeniDin's users (lawyers) need fee-agreement and bank-deposit events mentioned in ordinary
WhatsApp conversation captured for later bookkeeping, without manually re-entering them into
a separate system. Before this feature, no such capture existed — any money/engagement
information stated in chat was answered conversationally but never structured or retained
for ledger purposes.

## Clarifications

*(Reconstructed from the shipped constitution text — these represent real decisions embedded
in that text, restated here as an explicit Q&A per this repo's spec convention.)*

- Q: How does the system decide whether a message is ledger-worthy at all? → A: Classify
  before extracting. Misclassifying ordinary chatter as a ledger event is the main
  false-positive risk; misclassifying a *correction* to an existing event as a new
  independent one is the main double-counting risk. When genuinely unsure, prefer "neither"
  — a missed capture is far cheaper than a false one.
- Q: How should amounts/names be extracted when the source text is ambiguous? → A: Verbatim
  over guessed, always. Never normalize, complete, or "clean up" an ambiguous or partial
  name/amount/description — record exactly what's there, put uncertainty in `notes`, never a
  silent guess.
- Q: How should "עולה ל-X" ("rises to X") style phrasing be handled? → A: As a new total, not
  a delta — never add X to a prior figure (flagged as the single highest-risk misreading).
- Q: How is VAT status determined? → A: "לפני מעמ"/"לא כולל מעמ" → `לא כולל`; "מעמ כלול"/"כולל
  מעמ" → `כולל`; unstated → `לא צוין`. Never assumed.
- Q: How do relative dates/times ("היום"/"אתמול"/"מחר") resolve? → A: Against *this message's
  own timestamp*, never the model's own notion of "today" from elsewhere in the conversation.
  (Later revisited by Feature 026's `REQ-DATA-005`/`שעות_תאריך` for the specific case of
  hourly work-log entries whose *worked* date differs from the message's *sent* date.)
- Q: How are corrections handled, given the model has no access to the full historical
  ledger? → A: Record as `עדכון`, with `replaces_hint` (free text: client, approximate date,
  prior amount) populated only if identifiable from *this* conversation's own history — blank
  rather than guessed otherwise. Resolution to a real prior event ID happens downstream, not
  by the model. (Formalized in Feature 026 as the `"צריך למצוא"` placeholder mechanism,
  `REQ-DATA-002`.)
- Q: What about an ambiguous cancellation/reduction that doesn't clearly name its target
  (bare "לבטל")? → A: Do not auto-resolve to "the most recent plausible candidate" — either
  skip creating an event, or create it with the target left unnamed and the ambiguity stated
  in `notes`. (This exact gap is what motivated Feature 032, started 2026-07-30, to add real
  reply/quote-based resolution.)
- Q: How is a paying intermediary (insurer, union) distinguished from the client? → A: Record
  the real client's name and the payer separately (`payer_name`), never collapsed into one
  field — only when money is routed through an intermediary rather than paid directly.
- Q: Should multiple hourly work-log mentions in one message (even same client, same day) be
  summed into one event? → A: No — first-class events, one per occurrence, never aggregated.
- Q: Should an unpriced mention (matter + client named, no fee stated) be captured at all? →
  A: Yes, with `amount` left empty — still worth tracking rather than skipped.
- Q: What must every capture carry for later verification? → A: `raw_message_excerpt`
  (verbatim source text, or a precise image description) is required, never vague — the
  "hard pointer" that makes a capture independently checkable later. The real message
  timestamp and sender are always the provenance source, never a guess.
- Q: Does the model compute the final ledger ID? → A: No — always assigned deterministically
  downstream from the real message timestamp, entirely outside the tool call. (Formalized as
  `event_id` generation in Feature 026, `REQ-ID-001`.)
- Q: What happens when Morning MCP (existing invoice data) is the turn's data source? → A:
  Real defect found live, 2026-07-28: the model sometimes mistook its own
  `list_invoices`/`get_invoice_details` output for new fee-agreement text, and worse, a
  cascading follow-up could leave the user with a completely empty reply. Fixed by
  suppressing `capture_ledger_event` persistence when Morning MCP was used this turn, and
  stripping the ledger tool from that turn's follow-up round so the model is forced to
  produce its real answer. Genuinely capturing Morning-sourced events deferred to
  `specs/backlog/025-morning-sourced-ledger-events/`.

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-CAPTURE-001**: The system MUST provide `capture_ledger_event`, a local (non-MCP)
  OpenAI function tool, callable by both the text path (`AIHandler`) and the image path
  (`ImageExtractor`), using `strict: True` function-calling (every property listed in
  `required`, nullable ones typed `["<type>", "null"]`).
- **REQ-CAPTURE-002**: The tool MUST be called *in addition to*, never *instead of*, the
  model's normal conversational reply for that turn.
- **REQ-CAPTURE-003**: A turn MAY contain more than one `capture_ledger_event` call; ALL
  calls found MUST be resolved together in one follow-up round-trip (not just the first) —
  OpenAI rejects a follow-up that leaves any pending function call unresolved.
- **REQ-CAPTURE-004**: Hourly work-log entries MUST be captured as one event per occurrence,
  never summed/aggregated, even for the same client on the same day.
- **REQ-CLASSIFY-001**: The model MUST classify before extracting — `הסכם` (states/changes/
  cancels a fee arrangement, unambiguous target required for corrections/cancellations),
  `בנק` (bank-transfer/deposit confirmation image), or neither (no call at all). Preferring
  "neither" when unsure is correct behavior, not a gap.
- **REQ-DATA-001**: `amount`/`client_name`/`description` MUST be captured verbatim from the
  source — never normalized, completed, or guessed; ambiguity goes in `notes`.
- **REQ-DATA-002**: `vat_status` MUST be one of `כולל`/`לא כולל`/`לא צוין`, determined only
  from explicit phrasing, never assumed.
- **REQ-DATA-003**: `payer_name` MUST be populated separately from `client_name` only when
  the message explicitly indicates payment is routed through a different entity.
- **REQ-DATA-004**: `replaces_hint`/`reference_hint` MUST stay free text describing what the
  model can identify from the current conversation only — never resolved to a real prior
  event ID by the model itself (no access to the full historical ledger).
- **REQ-DATA-005**: `raw_message_excerpt` MUST always be populated (verbatim text or precise
  image description) — the required provenance "hard pointer."
- **REQ-DATA-006**: The real Green API message timestamp MUST be used as each capture's
  provenance pointer — never processing time, never a guess.
- **REQ-SUPPRESS-001**: When Morning MCP was used as the current turn's data source (a real
  `mcp_call` item present in the response), any `capture_ledger_event` call(s) that turn MUST
  be suppressed (not persisted), and the ledger tool MUST be excluded from that turn's
  follow-up round-trip's available tools.
- **REQ-ARCH-001**: Both text and image capture paths MUST use a two-call architecture — a
  pure extraction/reply call, then a separate classification call carrying the ledger tool —
  since a reasoning model emits either a `function_call` or a `message` in one turn, never
  both.

### Key Entities

- **`capture_ledger_event` arguments** (16 keys at this feature's original shipped shape —
  since extended by Feature 026 to 19: `agreement_label`/`component_label`/`hours_date`; see
  `data-model.md` in this folder for the original schema and
  `specs/in-progress/026-ledger-event-persistence/data-model.md` for the current one):
  `source_type`, `event_subtype`, `client_name`, `payer_name`, `description`, `amount`,
  `percent`, `percent_base`, `hours`, `hourly_rate`, `vat_status`, `replaces_hint`,
  `reference_hint`, `notes`, `raw_message_excerpt`.

## Technology Choices

**Technology Choice: Local function tool (not remote MCP), two-call architecture**
- **Rationale**: `capture_ledger_event` needs zero external execution (it only returns
  structured arguments for local persistence) — a remote MCP round-trip would add latency
  and a network dependency for no benefit. The two-call split exists because OpenAI's
  reasoning models (the ones this app uses) emit either a function call or a text message in
  one turn, never both — a real, load-bearing constraint discovered while building this
  feature, not a design preference.

## Success Criteria *(mandatory)*

### Measurable Outcomes (as verified live, 2026-07-28 — see HANDOFF.md)

- **SC-001**: A real fee-agreement text message (client גיליאן דוידיאן) was captured live
  with the correct client/amount and the real message timestamp as its hard pointer.
- **SC-002**: `list_invoices` for a real client (דורית אשכנזי) with genuine existing Morning
  documents did NOT produce a false-positive ledger capture, and the user received the real
  invoice-list reply (not an empty turn) — the Morning-MCP suppression fix verified live.
- **SC-003**: Multi-capture-per-turn no longer crashes the follow-up round-trip (verified via
  the fix for "No tool output found for function call ..." — a real error hit during this
  session's own testing).

## Relationship to Later Features

- **Feature 025** (`specs/backlog/025-morning-sourced-ledger-events/`): genuinely capturing
  Morning-sourced events (as opposed to suppressing false positives from them) — explicitly
  deferred from this feature.
- **Feature 026** (`specs/in-progress/026-ledger-event-persistence/`): moved captured events
  from `session.json`'s `pending_ledger_events` to permanent per-event files under
  `data/events/`, added `message_id` traceability, per-component splitting, and (later
  addenda) `agreement_id`/`component_id`/`hours_date` — all storage/data-model changes, none
  of which alter this feature's classification/extraction behavior.
- **Feature 032** (`specs/in-progress/032-whatsapp-reply-reference-resolution/`): addresses
  this feature's own documented gap (see Clarifications, "ambiguous referents") — resolving
  a reply-based cancellation to the real agreement it targets, instead of leaving it
  unresolved/ambiguous.

## References

- `.github/CONSTITUTION.md`, `.github/METHODOLOGY.md`
- `config/runtime_constitution.md` — "Ledger Event Recognition (Fee Agreements & Bank
  Deposits)" section (the live behavioral source of truth this spec restates)
- Commit `ae49b0e` (original implementation), PR #140 (merge)
- `HANDOFF.md` (repo root, as of 2026-07-30) — the session narrative this reconstruction
  leans on most heavily
