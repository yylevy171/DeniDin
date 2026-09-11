# Contract C3: Media ledger-capture routing — `MediaHandler` → conversational pipeline

**Feature 069** | [plan.md](../plan.md) · [research.md](../research.md) R1/R2/R9 ·
[data-model.md](../data-model.md) §5 · FR-069-045/046/047 · FR-069-020/022

> **Redesign (2026-09-01).** No new OpenAI call is added to `DOCXExtractor` or any extractor
> (spec Assumption 8). Recognition now happens **once, post-turn, for every medium**, via the
> single recognition call in [recognition-and-logging.md](./recognition-and-logging.md). This
> contract is only about **routing the extractor output into the conversational pipeline** as
> a synthetic turn — not about a media-specific capture path (there is none).

## Problem

Today (`media_handler.py` Step 10, ~lines 218-235) **any** recognized ledger event from an
image — `בנק` deposit slip **or** `הסכם` fee agreement — is persisted **directly** via
`ledger_event_manager.add_ledger_events_from_call(...)`: no conversation, no Morning MCP
tools, no operator round-trip. It structurally cannot run `resolve_client_name`, so the
persisted `client_name` is whatever the OCR produced — the exact junk-client-name problem
this feature closes. A `docx` `הסכם` never reaches the ledger at all.

## Contract

*No feature flag — this is the behavior unconditionally once deployed (2026-08-31 operator
direction).*

### C3a — `MediaHandler` stops persisting captures directly

- `MediaHandler` (or `denidin.py`'s media path) MUST NOT call `add_ledger_events_from_call`
  for recognized media ledger events. That call site is removed (FR-069-045).
- `MediaHandler` still runs its media-artifact storage step (`_store_media_turn`) for the
  image/document itself, unchanged.
- If routing/recognition later raises (tunnel down, OpenAI error): surface the existing
  friendly media-error notice; **persist nothing** (CONSTITUTION §XVIII — no guessed
  `client_name`). Do **not** fall back to `add_ledger_events_from_call`.

### C3b — routing signal (no new AI call)

| medium | classification signal | routed when |
|---|---|---|
| image | `ImageExtractor`'s existing vision-classify `source_type` on an entry in `analysis_result["ledger_events"]` | `source_type` ∈ {`בנק`, `הסכם`} |
| `docx` | `DOCXExtractor.document_analysis.document_type` — **as built 2026-09-03** this is a new deterministic keyword classmethod `_classify_document_type` (no OpenAI call); the field previously did not exist on `analyze_media`'s return and `_analyze_document` hardcoded `"generic"` | document type is `הסכם` (per `bugfix-028` a `docx` is always `הסכם` or unknown — never `בנק`) |
| `pdf` | — | **never** (FR-069-047 — Feature 071 rewrites `PDFExtractor` to a single-call extraction; it then routes here with no further 069 work) |

`source_medium` ∈ `{"image", "document"}`: `ImageExtractor` → `"image"`; `DOCXExtractor` →
`"document"`.

### C3c — build the stash and route a synthetic conversational turn

When the routing signal fires, the media path:

1. Builds the **verbatim structured stash** via
   `build_ledger_stash_text(extracted_text, analysis, source_type, source_medium)` (full
   rendered shape in [data-model.md](../data-model.md) §5):
   - `extracted_text` — verbatim OCR (image) / python-docx paragraphs + table cells (`docx`).
   - `analysis` — `ledger_events[0]` (image) / `document_analysis` + `fields` (`docx`).
   - `source_type` drives field ordering (`בנק` → banking triplet first; `הסכם` → one line
     per fee component).
   - `source_medium` drives the header + the "extracted text" frame line (`📸`/"מהתמונה" vs
     `📄`/"מהמסמך").
   - Missing/None value → `לא זוהה`. Multiple events → one labelled block each, prefixed
     `אירוע N מתוך M`.
2. Re-enters the conversational pipeline as a **synthetic text turn** (the Feature 030
   contact-card pattern, mechanically): `denidin.py`'s `_process_media_message` rewrites the
   inbound notification's `messageData` in place to a `textMessage` shape whose body is the
   stash text, keeping the original `senderData` (chat id, sender, resolved name) and
   notification timestamp, then calls `_process_conversational_message(notification)`. That
   path parses it through the same `WhatsAppMessage.from_notification` → `create_request`
   flow a real typed turn uses, so `chat_id` / RBAC phone / `is_group` / `chat_name` /
   `message_id` all resolve identically.
   - **Dating note (decision #10):** the media notification timestamp is **not** the
     `event_datetime` source. The synthetic turn persists its own user + assistant messages;
     the ledgerer dates `הסכם` / `בנק` from the **completing** message (the assistant reply
     that closes the round, whichever turn that is — the same turn for a silent exact match,
     a later turn after a resolution detour). `trigger_message_id` in the verdict stays
     informational.
3. Routes it through the **shared conversational path** (`_process_conversational_message`) —
   the same one typed turns use. That path already:
   - attaches Morning MCP tools (`resolve_client_name`, `add_client`, `create_*`) +
     `query_ledger_events` for godfather/admin (RBAC resolved from the phone; a non-ledger
     role → ordinary reply, no capture);
   - sends the reply and attaches any pending approval
     (`_send_ai_response_and_attach` — the extracted helper, C-wiring below);
   - runs the **post-turn recognition call**
     ([recognition-and-logging.md](./recognition-and-logging.md) C1/C2) — which covers the
     media capture identically to a typed turn.
4. The synthetic turn's user + assistant messages are persisted like any turn, so the stash
   is in session history for the multi-turn resolution detour.

### Scope of routing

- `source_type == "בנק"` off an image → routed. `source_medium="image"`. Flagship: **US7**
  (7a 0 matches / 7b 1 partial / 7c 2+ partial / **7d** exact Morning match — no
  disambiguation question, no `add_client`, captured directly against the existing client).
- `source_type == "הסכם"` off an image → same path. `source_medium="image"`. **US9**
  (photographed multi-component agreement).
- `document_type == "הסכם"` off a **`docx`** → same path. `source_medium="document"`.
  **US10** (docx multi-component agreement). **No** new classify call in `DOCXExtractor` —
  the existing `document_analysis.document_type` is the signal; recognition is the post-turn
  call. Because that recognition call is text-only (`config.ai_model`), US10 is a **billed**
  test, not expensive.
- `חשבונית` / accounting-reconciliation events → **not** affected (out of scope).
- `pdf` → out of scope (Feature 071).

### Follow-up turns

Operator replies ("חדש", a chosen number, an email + phone) arrive as ordinary
`textMessage`s → `_process_conversational_message` → reply → post-turn recognition call. The
synthetic media turn (with the full stash) is in session history, so the model completes
resolution and the recognition call then reads the completed event, transcribing the stashed
values (banking triplet for `בנק`, every fee component for `הסכם`). No special routing for
follow-ups.

## C-wiring — the shared send + pending-approval-attach helper (`denidin.py`)

The synthetic-turn `AIResponse` may create a pending approval (the `add_client` step). The
existing block in `_process_conversational_message` (denidin.py ~588-595) that (a) sends via
`sendInteractiveButtons` when `offer_approval_buttons`, and (b) calls
`pending_approval_manager.attach_sent_message_id(...)` +
`pending_local_tool_approval_manager.attach_sent_message_id(...)` must run for the media
ledger path too.

**Chosen approach (R1, as built 2026-09-03)**: that block was extracted into the thin
module-level helper `_send_ai_response_and_attach(notification, chat_id, ai_response)` in
`denidin.py` (Phase 2 / T007b). The media routing path does **not** call it directly and
does **not** add a second media-specific routing helper — instead `_process_media_message`
rewrites the notification to a `textMessage` and calls `_process_conversational_message(...)`
(see step 2 above), which already runs `_send_ai_response_and_attach` **and**
`_run_post_turn_ledger_recognition`. One code path, no duplication; the conversational
path's behavior is unchanged byte-for-byte (existing tests green).

## Tests

- **unit** `test_ai_handler_media_ledger_routing.py` (`build_ledger_stash_text`): stash text
  contains every non-null `analysis` field + the raw extracted-text block; `source_type="בנק"`
  → deposit header + banking-triplet-first ordering; `source_type="הסכם"` → agreement header
  + one line per fee component; `source_medium="image"` → `📸`/"מהתמונה"; `source_medium=
  "document"` → `📄`/"מהמסמך"; missing value → `לא זוהה`; multi-event → labelled blocks.
- **unit** `test_media_handler.py`: a recognized `בנק` image, a recognized `הסכם` image, and
  a `docx` with `document_type == "הסכם"` → `result["ledger_stash"]` /
  `["ledger_stash_source_type"]` are set and `add_ledger_events_from_call` is **not** called,
  the media turn's `Message.ledger_event_ids` stays empty; no ledger classification → routed
  as an ordinary media turn (unchanged), no stash. **No** assertion about a new
  `DOCXExtractor` OpenAI call (there isn't one).
- **unit** `test_denidin_media_ledger_routing.py`: `_process_media_message` rewrites the
  notification `messageData` to a `textMessage` carrying the stash (keeping `senderData` /
  `timestamp` / `idMessage`) and calls `_process_conversational_message`; a no-stash or
  `None` result → no synthetic turn.
- **integration** `test_ledger_client_resolution_routing.py`: real `imageMessage` /
  `documentMessage` webhook JSON → router → (OpenAI stubbed: exact-match reply, then a
  `complete` recognition verdict) → exactly one `LedgerEvent` file with the resolved name,
  linked from the completing `Message`, and **no** direct-persist call. One `בנק` image
  case, one `הסכם` image case, one `הסכם` `docx` case.
- **billed** (acceptance): US10 (`docx` `הסכם` — text-only recognition) — real OpenAI + real
  Morning sandbox. Two-hop fidelity (`contracts/payload-fidelity-manifest.md`).
- **expensive** (acceptance): US7 (7a/7b/7c/7d), US9 — real vision + real Morning
  sandbox. Two-hop fidelity.
