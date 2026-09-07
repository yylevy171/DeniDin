# User Stories: Post-Turn Ledger Capture with Mandatory Client Resolution

**Feature**: 069-mandatory-client-resolution-before-ledger-event
**Created**: 2026-08-30 · **Re-specified**: 2026-09-01 (architecture redesign)
**Format**: Given-When-Then, end-to-end (real WhatsApp turn → router/handler → conversational
OpenAI + Morning MCP → operator reply sent → **post-turn recognition call** → mechanical
ledgerer → persisted `LedgerEvent` file). Every story is independently testable and,
implemented alone, delivers a real slice of the redesign.

All stories assume: the operator is a godfather/admin (ledger capture, `query_ledger_events`,
and the Morning client tools are already RBAC-gated), a live Morning sandbox with a known
client roster, and a running Morning MCP tunnel (`"status": "running"`).

---

## The mechanism these stories exercise (shared context)

Every godfather/admin turn now runs in two decoupled stages:

1. **Conversational stage** — `AIHandler.get_response` produces the operator's reply, with the
   Morning MCP tools + `query_ledger_events` (read/search only) attached. **`capture_ledger_event`
   / `LEDGER_EVENT_TOOL` is NOT attached.** The reply is sent to the operator.
2. **Recognition stage (post-turn)** — after the reply is sent, one dedicated **text-only**
   OpenAI call ("the recognition call") receives the conversation so far, the reply just sent,
   this turn's Morning MCP tool calls **and their results verbatim**, and the constitution's
   ledger section. It returns one of three verdicts:
   - **`complete`** — a complete ledger event finished *this round*; the payload is returned
     already mapped to the `LedgerEvent` schema (normalized amounts, ISO dates, fee components
     split into the `components` array, `source_type`/`event_subtype`, the resolved
     `client_name`, any `reference`/`reference_hint` established in conversation).
   - **`none`** — no complete event this round (nothing persisted, no operator-visible effect).
   - **`declined`** — the operator was offered store-anyway and explicitly refused; carries
     `source_type` + operator-stated name + `reason`.
   The recognition call's output is **never shown to the operator** and triggers **no**
   follow-up round-trip.
3. **The ledgerer** — mechanical, zero-AI. On `complete` it mints `event_id` /
   `event_datetime` / `captured_at` (and `agreement_id` / `component_id` where applicable),
   dedups, persists the immutable JSON, appends to the in-memory index, and updates
   `Message.ledger_event_ids`. On `declined` it emits one INFO breadcrumb and persists
   nothing. It never resolves a client, queries Morning, or queries the ledger.

`event_datetime` (the "hard pointer") is the **Green API notification timestamp of the
message that first introduced the event's core economic content** — never the recognition
call's own clock, never `now_local()`. In a multi-turn resolution detour, the ledgerer is
threaded that original message's timestamp.

**Client resolution is ordinary conversation.** Until the client resolves to an exact Morning
name (or store-anyway is elected), the event is not "complete", so the recognition call
returns `none` and the conversation simply continues. Resolution follows the existing
"Resolving a client by name" constitution flow — never a code state machine, never anything
the recognition call or the ledgerer does.

---

## User Story 1 — Mechanism move / decoupling (Priority: P1)

A godfather sends a fee-agreement message that names a client **already an exact match** in
Morning and gives a complete arrangement (amount, work description, implicit date). The
operator gets the normal conversational acknowledgement. Separately — after that reply is
sent — the `הסכם` event is recognized by the post-turn recognition call and persisted by the
ledgerer. There is no second reply round-trip, no inline `capture_ledger_event` tool, no
suppression guard.

**Why P1**: This is the redesign's spine. If the decoupled recognition call + ledgerer path
does not work for the simplest complete-event case, nothing else does.

**Independent Test**: Send one agreement text naming an exact-match seeded Morning client with
a complete arrangement; assert (a) the operator's normal reply is delivered, (b) exactly one
`הסכם` / `יצירה` `LedgerEvent` file is written after the turn with `client_name` == the exact
Morning name and every provided field present, (c) the reply and the event are independent —
a forced recognition-call failure changes zero bytes of the reply.

**Routing / dispatch**: `textMessage` → `denidin.py` dispatch → `_process_conversational_message`
→ `AIHandler.get_response` (Morning MCP + `query_ledger_events` attached; **no**
`capture_ledger_event`) → reply sent → post-turn recognition call → ledgerer.

**Acceptance Scenarios**:

1. **Given** Morning has an exact client "רות בן דוד",
   **When** the operator sends "סגרתי עם רות בן דוד על כתב הגנה — 9,000 ₪ כולל מע""מ",
   **Then** DeniDin replies with its normal conversational acknowledgement (no ledger-schema
   text, no "recorded to ledger" claim required).
2. **Given** scenario 1's reply has been sent,
   **When** the post-turn recognition call runs,
   **Then** it returns `complete` with `source_type` `הסכם`, `event_subtype` `יצירה`,
   `client_name` "רות בן דוד", one fixed component of 9000 for "כתב הגנה", `vat_status` `כולל`,
   and the event date; **and** the ledgerer writes exactly one `LedgerEvent` file whose
   `event_datetime` is the triggering message's Green API timestamp.
3. **Given** the same turn,
   **When** the recognition call is forced to raise in a test,
   **Then** the operator's reply is byte-for-byte unchanged and no `LedgerEvent` is written
   (SC-009).
4. **Given** the turn also involved a `query_ledger_events` search (the model checked for a
   prior agreement),
   **When** the recognition call runs,
   **Then** the search result is available as context and — if the model established a link —
   `reference` / `reference_hint` are carried into the persisted event; a search that found
   nothing changes nothing.

---

## User Story 2 — Morning "create" captured synchronously (Priority: P1)

The operator asks DeniDin to create a Morning **combo document** ("חשבונית מס/קבלה", Morning
document type **320** — a paid invoice+receipt, **not** the unpaid type-305 plain tax
invoice). The `create_combo_document` MCP call succeeds inside the conversation. The
document's client is resolved **by construction** (Morning would not have created it
otherwise). DeniDin does **not** ask any VAT clarifying question — a type-320 document
carries VAT by definition and Morning itself enforces amount/VAT consistency on it. The
post-turn recognition call captures the `חשבונית` event **this turn**, reading the real
Morning response — not re-deriving from prose. Feature 025's next reconciliation tick sees
the display number as already known and does **not** double-write.

**Why P1**: Closes the gap where in-conversation Morning creates were suppressed and only
Feature 025's background sweep caught them later, from Morning's side.

**Independent Test**: Ask DeniDin to create a combo document (type 320) for an existing
Morning client, stating a gross amount; approve it; assert exactly one `חשבונית`
`LedgerEvent` file is written this turn with `accounting_document_display_number`,
`event_subtype` (= the type-320 document type), `amount`, `txn_date`, and `client_name` all
taken from the Morning response, and `vat_status` recording VAT as **included** — with **no**
VAT question anywhere in the transcript; then run a Feature 025 reconciliation tick and
assert **0** additional files for that display number.

**Routing / dispatch**: `textMessage` → `_process_conversational_message` → `get_response`
with Morning MCP attached → `create_*` approval turn via `PendingApprovalManager` → `create_*`
succeeds → reply sent → recognition call (input includes the `create_*` call **and its
result**) → ledgerer → `add_ledger_events_from_call` → `_ensure_accounting_document_cache()`.

**Acceptance Scenarios**:

1. **Given** Morning has an exact client "דורית אשכנזי",
   **When** the operator asks "תוציא לדורית אשכנזי חשבונית מס/קבלה על 320 ₪ עבור ייעוץ" and
   approves the `create_combo_document` prompt,
   **Then** the type-320 Morning document is created **and** the operator gets the normal
   confirmation reply — DeniDin never asked whether the 320 ₪ was with or without VAT.
2. **Given** scenario 1's `create_combo_document` returned a real Morning document number,
   **When** the recognition call runs with that call + result in its input,
   **Then** it returns `complete` for a `חשבונית` event whose mandatory fields
   (`client_name`, `txn_date`, `event_subtype` = the type-320 document type, `amount` 320,
   `accounting_document_display_number`) all come from the Morning response, and whose
   `vat_status` records VAT as **included**; **and** the ledgerer persists exactly one file.
3. **Given** the `חשבונית` event file from scenario 2 exists,
   **When** Feature 025's reconciliation sweep next ticks and lists that Morning document,
   **Then** it matches on `accounting_document_display_number`, treats it as a duplicate, and
   writes **0** additional files (SC-008).
4. **Given** the `create_*` call succeeds but the reply or the recognition call then fails,
   **When** the turn ends,
   **Then** the Morning document exists but **no** `חשבונית` event is written this turn — and
   Feature 025's next sweep picks it up as the backstop (no double-write, because 069 wrote
   nothing).

---

## User Story 3 — Regression guard: no spurious capture / lost reply mid-MCP-flow (Priority: P1)

The two incidents the old bugfix-018 suppression guard existed for:

- **2026-07-28** — the model called `list_invoices`, read the results back into itself, and
  fired a spurious `capture_ledger_event`, losing its actual reply.
- **2026-08-02** — a two-word field-filling reply ("עבור ייעוץ") mid-`create_combo_document`
  approval was misclassified as two spurious captures, losing the reply / 400-ing the turn.
  The `create_combo_document` flow it was part of was **entirely legitimate** and, once
  completed, correctly produces one `חשבונית` event (US2).

Under the redesign both are **structurally impossible**: there is no inline
`capture_ledger_event` tool on the main turn to misfire, and the reply is produced by the
conversational stage independently of recognition.

**Why P1**: FR-069-005 removes the guard; this story is the proof that removing it is safe.

**Independent Test**: Reproduce each incident shape — (Shape A) a turn that calls
`list_invoices` and reads the result back; (Shape B) a short field-filling reply mid a valid
`create_combo_document` approval flow — and assert the operator's reply is delivered intact,
**0** ledger events are spuriously written **on the partial/read-back turn**, and (Shape B)
the combo-document flow still completes normally and yields exactly **1** `חשבונית` event
once the document is actually created.

**Routing / dispatch**: Same as US1/US2. The recognition call sees the `list_invoices` call +
result but, per constitution guidance, recognizes a read-only Morning lookup as **not** a
complete event; and it recognizes a mid-flow field-fill turn (no `create_*` success yet) as
`none`, then `complete` on the turn the `create_combo_document` call actually succeeds.

**Acceptance Scenarios**:

1. **Given** the operator asks "מה מצב החשבוניות של רימונה כהן?",
   **When** the turn calls `list_invoices` and DeniDin answers with the summary,
   **Then** the operator receives that summary intact **and** the recognition call returns
   `none` — **0** `LedgerEvent` files written (SC-007).
2. **Given** a `create_combo_document` approval is pending and the model asked "עבור מה
   התשלום?",
   **When** the operator replies "עבור ייעוץ" (filling the description field),
   **Then** the reply threads back into the pending `create_combo_document` flow unchanged
   (no 400, no lost reply) **and** the recognition call for *that* turn returns `none` —
   **0** events written yet (the document is not created).
3. **Given** scenario 2's flow,
   **When** the operator approves the pending prompt and the `create_combo_document` call
   succeeds,
   **Then** the document is created **and** the post-turn recognition call returns `complete`
   for a `חשבונית` event — exactly **1** `LedgerEvent` file, captured synchronously from the
   real Morning response (identical to US2). The mid-flow "עבור ייעוץ" turn never produced a
   spurious or premature event.
4. **Given** either Shape A or Shape B,
   **When** the turn is inspected,
   **Then** no `capture_ledger_event` / `LEDGER_EVENT_TOOL` was attached to the main
   conversational turn at all.

---

## User Story 4 — FLAGSHIP: new-client fee agreement resolves, then captures (Priority: P1)

A lawyer types a fee-agreement message naming a client Morning has **never heard of** (the
common case — a new engagement). DeniDin runs the resolution detour as ordinary conversation
(ask the client's full name → email → phone → `add_client` approval), and only once the
client exists in Morning does the post-turn recognition call recognize the agreement as
**complete** — persisted against the resolved Morning name, carrying **every fee component,
the date, the subtype, and `payer_name`** from the original message across the detour.

**Why P1**: The single most frequent way a divergent name enters the ledger. Shipping just
this story unifies identity for most new `הסכם` events.

**Independent Test**: Send one agreement text for a **brand-new, run-unique client name**
(one that provably cannot already exist in the Morning sandbox — a `069`-tagged timestamp
suffix — with a matching run-unique email), with a distinct `payer_name`; answer the
email/phone questions; approve `add_client`; assert (a) a Morning client with that exact
run-unique name now exists (created **this run** via `add_client`, never pre-seeded),
(b) **no** `LedgerEvent` file existed before the `add_client` approval, (c) after approval
exactly one `הסכם` / `יצירה` event whose `client_name` == the newly-created Morning name,
`payer_name` persisted verbatim as free text (≠ `client_name`), and every component / date /
subtype present — exhaustive manifest match, (d) DeniDin's final reply confirms the new
client was added **and** echoes the agreement terms back.

**Routing / dispatch**: `textMessage` → `_process_conversational_message` → multi-turn
conversation (`resolve_client_name` → email/phone questions → `add_client` via
`PendingApprovalManager`). The recognition call runs **after every turn** and returns `none`
until the turn on which the client is created and the agreement is complete — then `complete`.
The ledgerer is threaded the **original agreement message's** timestamp for `event_datetime`.

**Acceptance Scenarios** (the client name `דנה כהן <run-id>` below stands for the run-unique
value the test generates — Morning has **nothing** resembling it at the start of the run):

1. **Given** Morning has no client resembling "דנה כהן <run-id>",
   **When** the operator sends "סגרתי עם דנה כהן <run-id> — ריטיינר 4,000 ₪ + 12% הצלחה +
   750 ₪ לדיון, המשלם הוא איגוד העובדים",
   **Then** DeniDin acknowledges and replies that it has no such client and asks for her
   full name, email, and phone; **and** the recognition call for this turn returns `none` —
   no `LedgerEvent` file.
2. **Given** the pending question,
   **When** the operator supplies the full name + a run-unique email + a phone,
   **Then** DeniDin presents the standard `add_client` approval prompt; recognition still
   `none`.
3. **Given** the `add_client` approval prompt,
   **When** the operator approves,
   **Then** the Morning client "דנה כהן <run-id>" is created **this run**, **and** DeniDin's
   reply confirms the client was added and echoes the agreement terms back — e.g.
   *"הוספתי את דנה כהן <run-id> למורנינג. קיבלתי את פרטי ההסכם — ריטיינר 4,000 ₪, 12% דמי
   הצלחה, ו-750 ₪ לכל דיון, המשלם איגוד העובדים."* (DeniDin does **not** announce a
   ledger event — capture is invisible.) **And** the post-turn recognition call returns
   `complete` — the ledgerer persists exactly one `הסכם` / `יצירה` event with `client_name`
   "דנה כהן <run-id>", a fixed 4,000 ₪ retainer component, a 12% success component, a 750 ₪
   per-hearing component, the event date, and `payer_name` "איגוד העובדים" as free text
   (`payer_name != client_name`, FR-069-017).
4. **Given** the operator instead replies "לא" to the `add_client` approval,
   **When** DeniDin processes that,
   **Then** no client is created, **no** `LedgerEvent` is persisted, DeniDin says the
   agreement was not recorded because the client was not created, and the recognition call
   returns `none`.

---

## User Story 5 — Ambiguous client name on a fee agreement (Priority: P1)

The agreement names a client whose name partially matches one or more existing Morning
clients (transliteration variant, first-name-only, married-name change). DeniDin surfaces
**every** candidate **and** the option to create a new client, and waits — never picks one
itself, never lets the recognition call persist the raw name.

- **5a — 1 partial match**: exactly one similar Morning client exists.
- **5b — 2+ partial matches**: several similar Morning clients exist.

**Why P1**: The `הסכם`-side equivalent of the deposit problem the August audit found. Silent
auto-pick or silent create-new both produce a divergent or duplicate identity.

**Independent Test**: Seed the candidate roster per 5a / 5b, send an agreement naming a
near-match; assert DeniDin lists every candidate + "create new", the recognition call returns
`none` on every turn until the operator picks, then `complete` against exactly the chosen
identity.

**Routing / dispatch**: Same as US4. The candidate list comes from `resolve_client_name`
returning a non-exact / multi-candidate result, relayed verbatim per the constitution.

**Acceptance Scenarios**:

1. **Given** Morning has "אבי לוי" and "אבי לוין" (5b),
   **When** the operator sends "הסכם חדש עם אבי לוי — ליווי שוטף, 2,000 ₪ לחודש",
   **Then** DeniDin names both "אבי לוי" and "אבי לוין" as candidates **and** offers to create
   a new client "אבי לוי"; **and** the recognition call returns `none` — no `LedgerEvent`.
2. **Given** the pending disambiguation,
   **When** the operator replies "אבי לוין",
   **Then** the post-turn recognition call returns `complete` with `client_name` exactly
   "אבי לוין"; the ledgerer persists one event (`event_datetime` = the original agreement
   message's timestamp).
3. **Given** the pending disambiguation,
   **When** the operator replies "לקוח חדש" and then supplies email + phone and approves
   `add_client`,
   **Then** a new Morning client "אבי לוי" is created and the event is persisted against it.
4. **Given** a single non-exact candidate only (5a — Morning has "אבי לוי", the message says
   "אבי לוי " with different spacing/nikud),
   **When** the operator sends the agreement,
   **Then** DeniDin still states the one candidate **and** the create-new option (never just
   "please be more specific").
5. **Given** the pending disambiguation from scenario 1,
   **When** the operator replies with something that fits none of the options (a bare "כן",
   an unrelated sentence),
   **Then** DeniDin re-asks **once** as an explicit closed choice listing "אבי לוי",
   "אבי לוין", and "create new"; recognition returns `none`; a second still-ambiguous reply
   is abandonment — nothing is ever persisted for that agreement (FR-069-018).

---

## User Story 6 — Exact-match client resolves silently (Priority: P2)

Guardrail against the feature adding friction: when the agreement or deposit names a client
that **already exactly matches** Morning, nothing new is asked — the event is captured in the
ordinary post-turn flow with zero extra operator questions and no measurable increase in
turns-to-capture.

**Why P2**: A resolution gate that interrogates the operator on every clean capture would be
a regression. This story pins "silent on exact match".

**Independent Test**: Send an agreement (and separately a deposit) each naming an
exactly-matching seeded Morning client; assert each event is captured with **zero** extra
turns versus pre-feature behaviour and no client-identity question is asked.

**Acceptance Scenarios**:

1. **Given** Morning has a client "זהבית צור" (exact),
   **When** the operator sends "עדכון: זהבית צור — סגרנו על 12,000 ₪ סה""כ",
   **Then** the `הסכם` / `יצירה` event is persisted against "זהבית צור" with **no**
   client-identity question asked; DeniDin's normal reply is unchanged (SC-003).
2. **Given** the same conversation later contains a correction to the same arrangement,
   **When** the operator sends "לתקן ל-13,000",
   **Then** a fresh `יצירה` event is captured reusing "זהבית צור" with **no** second
   `resolve_client_name` call.
3. **Given** an exact-match client and a deposit whose slip names that same client,
   **When** the operator sends the deposit image,
   **Then** the `בנק` event is persisted against the exact Morning name with no
   client-identity question (validated by Phase 7's routing + the expensive suite).

---

## User Story 7 — Bank-deposit image, partial-match client, operator replies "new" (Priority: P1)

**The single most likely real-world path and the one that MUST have end-to-end coverage**
(user, 2026-08-30). The operator forwards a bank-transfer screenshot. The account-holder /
"העברה מ-" name on the slip is **not** a full match to any Morning client. `MediaHandler`
routes the extracted slip into the conversational pipeline as a synthetic turn carrying a
verbatim stash of the deposit fields; `resolve_client_name` presents what it found plus
"create new"; the operator replies "new"; the standard new-client flow runs (the operator
states the client's full name explicitly — the slip text is only a hint — then email → phone
→ `add_client` approval); and only then does the post-turn recognition call recognize the
`בנק` event as **complete** — persisted with **every** slip detail (amount, deposit date,
**bank number, branch number, account number**) plus the freshly-resolved client.

All `resolve_client_name` outcomes MUST be covered as separate test cases — the three
non-full-match outcomes plus the clean exact-match path:

- **7a — 0 matches**: no Morning client resembles the slip name.
- **7b — 1 partial match**: exactly one similar Morning client exists.
- **7c — 2+ partial matches**: several similar Morning clients exist.
- **7d — exact match**: the slip name is already an exact existing Morning client. **No**
  question is asked, **no** new client is created, and the `בנק` event is captured directly
  against that existing Morning client name — the image analog of US6's silent exact-match
  path.

**Why P1**: Exercises the whole redesign in one flow — deposit-image recognition → routing →
resolution → disambiguation → new-client creation → deferred recognition-call capture with
full banking detail — against the exact failure the August audit found. If only one media
story ships, this is it.

**Independent Test**: For each of 7a/7b/7c, send one deposit image whose slip name is a
non-full-match, drive the flow to "new" → email → phone → approve; assert a single `בנק`
event file is written with `client_name` == the newly-created Morning client's stored name
**and** `amount`, deposit date, `bank_number`, `bank_branch`, `bank_account` all equal to the
slip values — verified **two-hop** (extractor output == slip manifest; persisted event ==
extractor output). For 7d, send one deposit image whose slip name is already an exact Morning
client; assert **no** client-identity question is asked, **no** `add_client` runs, and a
single `בנק` event is written against the existing Morning name with the same two-hop
manifest fidelity.

**Routing / dispatch**: `imageMessage` → `denidin.py` → `WhatsAppHandler.handle_media_message`
→ `MediaHandler` (ImageExtractor: OCR + vision classification, incl. banking fields). On a
`בנק` classification, `MediaHandler` **stops persisting directly** and instead routes the
extractor output + extracted text into the `AIHandler` conversational pipeline as a synthetic
turn (Feature 030 contact-card pattern), with the structured deposit fields carried verbatim
as a transient stash. Resolution, disambiguation, `add_client` (via `PendingApprovalManager`),
and — post-turn — the recognition call + ledgerer then all run on the same machinery a typed
turn uses. `event_datetime` = the deposit image message's Green API timestamp.

**Acceptance Scenarios** (scenarios 1–5 apply to 7a, 7b, and 7c unless noted; scenario 6 is 7d):

1. **Given** a bank-transfer screenshot whose slip shows sender name "רונית בר", amount
   "₪ 6,200", a deposit date, bank 12, branch 645, account 418302, a reference number, **and**
   Morning's roster per the variation (7a: nothing similar; 7b: only "רונית ברק"; 7c: "רונית
   ברק" + "רונית בר-און"),
   **When** the operator sends the image,
   **Then** DeniDin gives its normal reply **and**:
   - 7a → says it has no client "רונית בר" and asks for her full name, email, and phone;
   - 7b → names the candidate "רונית ברק" **and** offers to create a new client "רונית בר";
   - 7c → lists "רונית ברק" and "רונית בר-און" **and** offers to create a new client;
   **and** in all three the post-turn recognition call returns `none` — **no** `LedgerEvent`
   file exists yet.
2. **Given** the pending question/choice,
   **When** the operator replies "לקוח חדש" (7b/7c) — or, for 7a, answers with email + phone —
   **Then** DeniDin asks for any still-missing required field and then presents the standard
   `add_client` approval prompt for "רונית בר".
3. **Given** the `add_client` approval prompt,
   **When** the operator approves,
   **Then** the Morning client "רונית בר" is created **and** the post-turn recognition call
   returns `complete` — the ledgerer persists exactly one `בנק` / `הפקדה` event with
   `client_name` "רונית בר" (never the raw OCR string), `amount` 6200, the slip's deposit
   date, `bank_number` "12", `bank_branch` "645", `bank_account` "418302", `vat_status`
   `כולל`, and `event_datetime` = the image message's timestamp. Two-hop manifest match.
4. **Given** the flow has reached the email/phone step,
   **When** the operator declines phone or email,
   **Then** DeniDin asks the explicit closed question "לשמור את ההפקדה בלי פרטי לקוח מלאים,
   או לא?" (a **single** ask — no re-ask) — persisting nothing until answered (ties to US8).
   No Morning client is created.
5. **Given** the flow has reached the disambiguation choice (7b/7c),
   **When** the operator instead picks an existing candidate ("רונית ברק"),
   **Then** the `בנק` event is persisted with `client_name` "רונית ברק" and the same full
   banking + amount + date detail (no new client created).
6. **Given** a bank-transfer screenshot (7d) whose slip name "זהבית צור" is **already an
   exact** Morning client,
   **When** the operator sends the image,
   **Then** DeniDin gives its normal reply and asks **no** client-identity question and runs
   **no** `add_client`; the post-turn recognition call returns `complete` — the ledgerer
   persists exactly one `בנק` / `הפקדה` event against "זהבית צור" with the full banking +
   amount + date detail, `event_datetime` = the image message's timestamp, and two-hop
   manifest fidelity (image analog of US6, SC-003).

---

## User Story 8 — Operator won't provide email/phone: store-anyway or don't-store (Priority: P3)

`add_client` requires name + email + phone. If the operator can't or won't give both, DeniDin
asks the explicit closed choice **once** (no re-ask): **store anyway** (the operator-stated
name as free-text `client_name` + a fixed `[לקוח לא אומת במורנינג]` marker written into the
event's `description` field, no Morning client created, every other field still
manifest-exact) or **don't store** (the recognition call returns `declined`; the ledgerer
emits one INFO "declined by operator" line; nothing persisted). The operator may also
**proactively** elect store-anyway up front ("תרשום גם בלי אימייל וטלפון") — DeniDin honours
it directly, with **no** "בטוח?" / "are you sure?" confirmation. The operator has the final
say; DeniDin never silently drops the capture and never silently stores an unresolved one,
and never volunteers store-anyway before the operator has either declined the contact details
or proactively asked to store without them.

**Why P3**: An important boundary but a low-frequency one; the core value is delivered by
US1–US7. This story pins the operator-final-say escape hatch (clarified 2026-08-31; single-ask
+ proactive election locked 2026-09-01).

**Independent Test**: Trigger the no-match flow, decline email/phone once, then (a) answer
"store anyway" and confirm exactly one `LedgerEvent` with the free-text name + the marker in
`description` and **no** Morning client created; (b) in a separate run answer "don't store"
and confirm no `LedgerEvent` and one INFO "declined by operator" line; (c) in a separate run
have the operator proactively say to store without email/phone before being asked, and
confirm exactly one marked `LedgerEvent` with **no** "are you sure?" turn in the transcript.

**Acceptance Scenarios**:

1. **Given** the no-match flow has asked for "נועה שגב"'s email and phone,
   **When** the operator replies "אין לי טלפון שלה כרגע",
   **Then** DeniDin asks the explicit closed question "לשמור את האירוע בלי פרטי לקוח מלאים,
   או לא?" — a **single** ask, no re-ask first; still nothing is persisted.
2. **Given** that closed question,
   **When** the operator answers to store it anyway,
   **Then** the post-turn recognition call returns `complete` with `client_name` "נועה שגב"
   as free text **and** the marker `[לקוח לא אומת במורנינג]` inside `description`; the
   ledgerer persists exactly one `LedgerEvent`; **no** Morning client was created; all other
   provided/extracted fields present per FR-069-020 and manifest-exact (SC-006).
3. **Given** that closed question,
   **When** the operator answers not to store it,
   **Then** the recognition call returns `declined`; the ledgerer writes **no** `LedgerEvent`
   and emits one INFO "declined by operator" line (source type, stated name, reason)
   (SC-005).
4. **Given** that closed question,
   **When** the operator never replies,
   **Then** **no** `LedgerEvent` is written; there is no dedicated abandonment log line — the
   drop is discoverable only as an INFO "recognized" breadcrumb with no matching "written" /
   "declined" line.
5. **Given** scenario 1's closed question,
   **When** the operator instead supplies both email and phone,
   **Then** the flow resumes normally: `add_client` approval → client created → the
   originally-recognized event captured with its original details. The store-anyway option is
   not taken.
6. **Given** the no-match flow has just told the operator it has no client "נועה שגב" and
   asked for full name, email, and phone,
   **When** the operator proactively replies "אין לי אימייל וטלפון, תרשום ככה" (before any
   store-anyway prompt),
   **Then** DeniDin honours it directly with **no** "בטוח?" confirmation turn; the post-turn
   recognition call returns `complete` with the free-text `client_name` + the
   `[לקוח לא אומת במורנינג]` marker in `description`; exactly one `LedgerEvent`; no Morning
   client created; manifest-exact on every other field.

---

## User Story 9 — Photographed multi-component fee agreement (Priority: P2)

The lawyer photographs a **printed** fee agreement (a signed page, not a typed WhatsApp
message) and sends the JPEG. The client named on the page is **not** an exact Morning match.
Today such a photo is recognized off the OCR'd text and persisted **directly** with the OCR
client string — the same junk-client-name hole this feature closes, on the image side of
`הסכם`. This story routes a photographed `הסכם` through the identical synthetic-turn +
resolution detour + post-turn recognition path as a photographed `בנק` slip, and asserts
that **every fee component** on the page survives the detour into the persisted event.

**Why P2**: The objective covers agreements regardless of how they arrive. P2 (not P1) only
because photographed agreements are less frequent than typed agreements (US4/US5) and deposit
screenshots (US7).

**Independent Test**: Send one photo of a printed fee agreement listing several distinct fee
components (fixed retainer + success percentage + per-hearing fee) for a near-but-not-exact
Morning match; drive the flow to "new client" → email → phone → approve; assert a single
`הסכם` event with `client_name` == the newly-created Morning name **and** every fee
component, the agreement date, and the subtype from the photo — verified **two-hop**
(extractor output == page manifest; persisted event == extractor output).

**Routing / dispatch**: `imageMessage` → `WhatsAppHandler.handle_media_message` →
`MediaHandler`. On a `הסכם` classification off an image, `MediaHandler` routes the extractor
output + extracted text into the `AIHandler` conversational pipeline as a synthetic turn
(same path as US7, `source_medium="image"`), with every extracted fee component carried
verbatim in the transient stash. Resolution, disambiguation, `add_client`, and — post-turn —
the recognition call + ledgerer run on existing machinery.

**Acceptance Scenarios**:

1. **Given** a photo of a printed fee agreement for "מרים בן שעיה" listing a fixed retainer
   of 4,000 ₪, a 12% success fee on recovered sums, and a 750 ₪ per-hearing fee, dated on the
   page, **and** Morning has only "מרים בן שחר" (a near match),
   **When** the operator sends the image,
   **Then** DeniDin gives its normal reply **and** names the candidate "מרים בן שחר" **and**
   offers to create a new client "מרים בן שעיה"; the recognition call returns `none` — no
   `LedgerEvent`.
2. **Given** the pending choice,
   **When** the operator replies "לקוח חדש", supplies email + phone, and approves `add_client`,
   **Then** the Morning client "מרים בן שעיה" is created **and** the post-turn recognition
   call returns `complete` — the ledgerer persists exactly one `הסכם` / `יצירה` event with
   `client_name` "מרים בן שעיה" (never the raw OCR string), a 4,000 ₪ fixed retainer
   component, a 12% success component, a 750 ₪ per-hearing component, the page's agreement
   date, and `event_subtype` `יצירה`. No fee component from the page is missing and none the
   page does not show is present (FR-069-022, bidirectional; two-hop).
3. **Given** the pending choice,
   **When** the operator instead picks the existing candidate "מרים בן שחר",
   **Then** the `הסכם` event is persisted with `client_name` "מרים בן שחר" and the same full
   multi-component payload (no new client created).
4. **Given** the flow has reached the email/phone step,
   **When** the operator declines,
   **Then** the US8 store-anyway / don't-store closed choice applies unchanged (single ask);
   nothing is persisted until it is answered.

---

## User Story 10 — `docx` multi-component fee agreement (Priority: P2)

The lawyer sends a **`.docx` document** of a fee agreement (a Word file, not a photo, not a
typed message). The client named in the document is **not** an exact Morning match. Today
`DOCXExtractor` produces a document summary and nothing else — a `docx` fee agreement never
becomes a `LedgerEvent`. Under the redesign, `MediaHandler` routes the extracted `docx` text
into the **same** conversational pipeline + synthetic-turn path as a photographed `הסכם`
(US9), differing only by `source_medium="document"` (which switches the stash header/frame
wording to `📄` / "מסמך"). Recognition happens **once, post-turn**, for every medium — no
separate recognition call is added to `DOCXExtractor`. Per `bugfix-028`, a `docx` is always
`הסכם` or unknown, never `בנק`. Because recognition is text-only (`config.ai_model`, no
vision), the US10 acceptance scenario is **`billed`**, not `expensive`.

**Why P2**: Same rationale as US9 — the objective covers agreements regardless of how they
arrive; `docx` is the common way a drafted (not yet signed) agreement is shared. `pdf`
agreements are **not** in this feature — deferred to Feature 071.

**Independent Test**: Send one `.docx` fee agreement listing several distinct fee components
for a near-but-not-exact Morning match; drive the flow to "new client" → email → phone →
approve; assert a single `הסכם` event with `client_name` == the newly-created Morning name
**and** every fee component, the agreement date, and the subtype from the document — verified
**two-hop** (`DOCXExtractor` extracted text/analysis == document manifest; persisted event ==
extractor output).

**Routing / dispatch**: `documentMessage` → `WhatsAppHandler.handle_media_message` →
`MediaHandler` → `DOCXExtractor.analyze_media` (python-docx paragraphs + table cells +
optional AI document analysis). `MediaHandler`, seeing a fee-agreement-shaped document
analysis, routes the extracted text into `AIHandler`'s conversational pipeline as a synthetic
turn with `source_medium="document"`. The post-turn recognition call recognizes the `הסכם`
event once the client is resolved and the agreement is complete.

**Acceptance Scenarios**:

1. **Given** a `.docx` fee agreement for "מרים בן שעיה" listing a fixed retainer of 4,000 ₪,
   a 12% success fee, and a 750 ₪ per-hearing fee, with an agreement date in the body,
   **and** Morning has only "מרים בן שחר",
   **When** the operator sends the document,
   **Then** DeniDin gives its normal reply (document summary) **and** names the candidate
   "מרים בן שחר" **and** offers to create a new client "מרים בן שעיה"; the recognition call
   returns `none` — no `LedgerEvent`.
2. **Given** the pending choice,
   **When** the operator replies "לקוח חדש", supplies email + phone, and approves `add_client`,
   **Then** the Morning client "מרים בן שעיה" is created **and** the post-turn recognition
   call returns `complete` — exactly one `הסכם` / `יצירה` event with `client_name`
   "מרים בן שעיה" (never the raw document string), all three fee components, the body's
   agreement date, and `event_subtype` `יצירה`. Two-hop, bidirectional (FR-069-022).
3. **Given** the pending choice,
   **When** the operator instead picks the existing candidate "מרים בן שחר",
   **Then** the `הסכם` event is persisted with `client_name` "מרים בן שחר" and the same full
   multi-component payload (no new client created).

---

## Cross-cutting test requirements

- **Normal reply preserved** (FR-069-006, SC-009): every story asserts the operator still
  receives their ordinary conversational answer for the triggering message, produced by the
  conversational stage independently of recognition. At least one scenario per feature slice
  forces a recognition-call failure and asserts the reply is byte-for-byte unchanged.
- **No inline ledger tool** (FR-069-001, SC-007): tests assert `capture_ledger_event` /
  `LEDGER_EVENT_TOOL` is **not** among the tools attached to the main conversational turn;
  `query_ledger_events` **is** (FR-069-008).
- **Recognition is post-turn and text-only** (FR-069-002): exactly one recognition call per
  godfather/admin turn, fired after the reply is sent, its output never surfaced to the
  operator, no follow-up round-trip.
- **Multi-event / staggered captures** (FR-069-016, gate G16): covered at the **unit** tier
  only — `tests/unit/test_recognition_call.py` asserts that when a turn's context holds one
  now-complete event plus a sibling still missing a mandatory field, the recognition call
  returns `complete` for the finished one only, and that a later turn supplying the sibling's
  last field yields `complete` for the sibling on that turn (one event per turn, no lost
  sibling — G16's "staggered set of captures across turns"). No dedicated `billed`/`expensive`
  acceptance scenario: a real multi-event operator turn is disproportionate to stage against
  the sandbox, and the per-turn emit behaviour is deterministic given a fixed recognition-call
  response.
- **`event_datetime` hard pointer** (redesign constraint): every scenario ending in a
  persisted event asserts `event_datetime` equals the **triggering message's Green API
  notification timestamp** (the message that first introduced the event's core economic
  content), not `now_local()` and not the recognition-call time — even after a multi-turn
  detour.
- **Lifecycle breadcrumb logging** (FR-069-035): every scenario that persists an event
  asserts the INFO "recognized" and "written" lines both appear and pair on source type /
  session; the explicit "don't store" scenario asserts the INFO "declined by operator" line;
  abandon scenarios assert no "written" / "declined" line follows the "recognized" one; a
  `none` result asserts no INFO line (DEBUG only).
- **No placeholder writes** (FR-069-004, SC-005): every abandon branch, every "don't store"
  branch, and every declined-`add_client`-approval branch asserts `{data_root}/events/`
  gained **no** new file. The **only** exception is an explicit operator "store anyway" (US8
  scenarios 2 and 6), which writes exactly one event carrying the `[לקוח לא אומת במורנינג]`
  marker in `description` (SC-006) — never an unmarked raw name.
- **Store-anyway is operator-elected, never default** (FR-069-033): assert DeniDin does not
  mention or offer store-anyway until *after* the operator has declined email/phone once — or
  proactively asked to store without them (US8 scenario 6). No "are you sure?" confirmation on
  a proactive election.
- **Full-payload fidelity — CRITICAL** (FR-069-022, SC-004): **every scenario in this file
  that ends in a persisted `LedgerEvent`** — US1.2, US2.2, US4.3, US5.2/5.3, US6.1/6.2,
  US7 sc.3 (×7a/7b/7c), US7 sc.5, US7 sc.6 (7d), US8.2, US8.6, US9.2/9.3, US10.2/10.3 —
  asserts the persisted event matches that fixture's committed **ground-truth manifest
  exhaustively and exactly**:
  - every field a careful reader identifies in the triggering text/image/document is in the
    manifest with its normalized expected value (amounts as numbers, dates as ISO, the full
    banking triplet split out, every `הסכם` component line, `event_subtype`, `agreement_id`,
    `payer_name` when present);
  - assertion is bidirectional: no manifested field missing/empty on the event (**silent
    drop**), and no field populated that the manifest doesn't list (**hallucinated value**).
    A `contains` / subset check does **not** satisfy this.
  - **Media sources (US7 images incl. 7d; US9 image; US10 `docx`) assert two hops**: extractor
    output == slip/page/document manifest, **and** persisted event == extractor output — so a
    detail lost *during the resolution detour* is distinguishable from one never extracted.
  - US8.2 / US8.6 (store-anyway): same exhaustive manifest match on **all** fields *except*
    that `client_name` is the operator's free-text string and `description` additionally
    contains the marker phrase.
  - **Fixtures MUST be deliberately detail-rich** (authored in `tasks.md` Phase 9): a `הסכם`
    fixture with a single amount and nothing else makes this assertion vacuous. Each carries
    ≥3 components / an explicit date / a subtype / (where relevant) `agreement_id` or
    `payer_name`; each `בנק` slip shows amount + date + all three banking numbers + a
    reference number.
  - `schema_version` is **never** asserted (CLAUDE.md — ledger schema is human-only).
- **Feature 025 dedup** (FR-069-025/026, SC-008): US2 asserts a Feature 025 reconciliation
  tick after a synchronous `חשבונית` write produces **0** additional files for that display
  number.
- **Constitution boundary** (FR-069-041, METHODOLOGY §XXI): a review check (not an automated
  test) that `runtime_constitution.md`'s rewritten "Ledger Event Recognition" section states
  ledger capture is a post-turn recognition step (not inline), the per-type mandatory-field
  contract, the mandatory client-resolution rule (resolved by ordinary conversation via
  "Resolving a client by name"), the store-anyway exception + marker phrase, and when the
  gate does NOT apply (`payer_name`; `חשבונית` client resolved by construction; ambiguity →
  ask). Bidirectional cross-reference with "Resolving a client by name"; out-of-scope notes
  in "Reminder Management" and "Invoice Management".
- **Acceptance tier**: US1, US2, US3, US4, US5 (incl. scenario 5), US6, US8, and **US10**
  (`docx` multi-component `הסכם`) are `billed` (text-only OpenAI + real Morning sandbox) —
  `docx` recognition runs on `config.ai_model` post-turn, no vision call. US7 (flagship,
  7a/7b/7c **plus 7d**) and US9 (photographed multi-component `הסכם` **image**) involve a
  vision extraction call → `expensive` tier, each requiring its own explicit per-run approval.
  Exact node ids are defined in `tasks.md`'s Acceptance phase and written + run once,
  together, after all unit/integration tasks are green (METHODOLOGY §VI).
- **Priority ordering for delivery**: US7 (flagship deposit path) is P1 alongside US1–US5. If
  the acceptance suite must be trimmed for cost, US7's variations (7a/7b/7c) are the
  non-negotiable core.
