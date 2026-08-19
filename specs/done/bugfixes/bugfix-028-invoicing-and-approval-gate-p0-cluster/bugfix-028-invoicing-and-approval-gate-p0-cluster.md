# Bugfix Spec: Documents come out wrong and the approval gate cannot complete a request (P0 cluster)

## Bug ID
bugfix-028-invoicing-and-approval-gate-p0-cluster

## Title
Nine confirmed production defects (plus one bundled P2), found together in the 7–9 Aug 2026
production review, that
between them make **every Morning document DeniDin issues wrong in at least one material
field** and make the **approval gate unable to complete a document-creation request at all**.
Filed as one bug by explicit user decision (2026-08-09) — to be fixed together in one pass, not
one at a time.

## Priority
**P0** — critical, first work item. Two of these produced real, live, wrong tax documents in
production; four of them, together, caused a ₪40,000 document to be approved eight times and
never created, with the user told nothing.

## Status
**Done.** Moved from `specs/in-progress/bugfixes/` to `specs/done/bugfixes/` on 2026-08-18.

**In Progress (2026-08-09 – 2026-08-13, kept below for history).** Moved from
`specs/bugfixes/` to `specs/in-progress/bugfixes/` on 2026-08-10 (this project's bugfix specs
have no documented in-progress folder in CLAUDE.md/METHODOLOGY — this location was created for
this bugfix at the user's explicit direction). All ten root causes approved 2026-08-09 (A3, A3b,
B1, B2 as originally written; A1, A2, A4, B3, B4, B5 only after being reinvestigated and
restated — original wording preserved below each, marked *as originally filed*). Test-gap
analysis and the full `billed`/`expensive` test set approved the same day. Fixes implemented and
merged across several sessions (`66f6334`, `57fbd40`, and this session's merge) — see
[`bugfix-028-HANDOFF.md`](bugfix-028-HANDOFF.md) for the full live history, including the A1-T2
scenario carved out into `bugfix-038` once investigation showed it needed infrastructure outside
this bugfix's approved scope.

**As of 2026-08-13**: the full `tests/billed/` sweep is finished clean (90/90, 1 obsolete test
deliberately removed, 1 environment-dependent skip, zero known failures) and the full
`tests/expensive/` sweep (21 tests) is clean except for the one test that structurally belongs
to `bugfix-038` (`test_given_a_deposit_matching_an_existing_tax_invoice_then_a_receipt_closes_it`,
left red on purpose - not this bugfix's scope). `bugfix-038`'s own spec was substantially
expanded this session (root cause + fix direction agreed, not yet implemented) after this
sweep's own investigation surfaced that `close_transaction_account` duplicates
`create_combo_document`'s entire payload-building logic - see that bugfix's own spec for the
full finding.

**PR #212** (opened 2026-08-13, merged the same day as commit `9bbec50`) carries this session's
work (and the prior uncommitted sessions' work merged alongside it) to `master`.

**Closed 2026-08-18**: with PR #212 merged, all ten approved root causes (A1-A4, B1-B5, plus the
bundled P2) are fixed and live on `master`, and the `billed`/`expensive` regression sweep is
clean except for the one test explicitly carved out into `bugfix-038` (itself now closed, see
`specs/done/bugfixes/bugfix-038-group-b-approval-missing-reference-data.md`). Two minor,
non-blocking gaps from the handoff's last "Exact next steps" were never separately tracked and
are accepted as-is rather than reopening this bugfix: (1) a test-assertion-only bug in
`test_create_document_for_existing_client_happy_path` (and four sibling sites) that can spuriously
fail when a randomly-drawn sandbox client name contains an apostrophe, because the assertion
compares the raw name against Morning's own geresh-normalized formatted output — not a production
defect, Morning's normalization itself is correct pre-existing behavior; (2) roughly 31 of the
denidin-app "List A" billed tests and all "List B" billed tests were never swept in this specific
session (the full `tests/billed/` suite reported clean as of 2026-08-13 above, via a separate,
later full run, superseding the partial List-A/B sweep referenced in the handoff).

## Date Opened
2026-08-09

## Reported By
yaronlev171, from live production use 7–9 Aug 2026, plus code/data forensics against the
read-only prod mount and prod logs. Full evidence and provenance:
[`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../../docs/production-analysis/2026-08-09-aug7-9-review.md).

---

## Session Context (2026-08-09 Production Review)

> **This section is the shared context for bugfix-028 through bugfix-037.** All ten were
> opened from one investigation; each of the others points back here rather than repeating it.
> Read this first if you are picking up any of them cold.

### What this was
The first structured post-hoc review of real production usage in this project. Trigger: the
user reported *"a lot of issues, small and large"* after the 7–9 Aug 2026 weekend of live use.
Goal was analysis and a ranked issue list — **not** fixes, and explicitly **no actions against
production**.

Two analysts: **Yaron** (product/UX findings, from having lived the conversations) and
**Ruth** (code and data forensics). Findings were produced independently, then merged and
re-ranked — the merge is recorded in the review doc's §2b traceability table.

### How it was run — strictly read-only
No prod state was modified. No container was started, stopped, or redeployed. No Morning
document was created, edited, or cancelled.

| What | How |
|---|---|
| Prod data (sessions, events, memory) | pre-existing sshfs mount at `/Users/yaron/denidin-winprod-data`, mounted `-o ro` |
| ChromaDB | `sqlite3.connect('file:…/chroma.sqlite3?mode=ro&immutable=1', uri=True)` |
| Prod logs | `wsl_ssh_run denidin-winprod 'sed -n …'` over SSH — read-only `sed`/`cat` |
| Container inventory | `docker --context denidin-winprod ps` |
| Ground truth | user-supplied screenshot of the Morning document list |

Full runbook for repeating this:
[`docs/production-analysis/README.md`](../../../docs/production-analysis/README.md).

### What was examined
- **21 ledger event files** (`{data_root}/events/*.json`)
- **4 sessions**, 252 messages total — `12e158e2` (118), `17df631a` (102, expired),
  `047cacb7` (30), `80649a08` (2, expired)
- **`denidin.log`** — 2.4 MB; the Aug 7+ slice is 2004 lines (1634 INFO / 24 WARNING /
  119 ERROR)
- **`morning-mcp.log`** — 88 lines total (which is itself finding bugfix-036)
- **ChromaDB** — 2 collections, 29 records
- Source in both apps for every implicated path

### Ground truth — the five documents Morning actually holds

| Doc # | Date | Type | Client | Morning | DeniDin reported |
|---|---|---|---|---|---|
| 100015 | 09/08 | 305 | רלי אוחנה | ₪1,500.00 | ₪1,500 |
| 100014 | 09/08 | 305 | שלמה נזרי | ₪2,000.00 | ₪2,000 |
| 100013 | 09/08 | 305 | עדו דניאל | ₪3,000.00 | ₪3,000 |
| 100012 | 09/08 | 305 | טלאל קרעאן | ₪2,300.00 | ₪2,300 |
| 90195 | 07/08 | 300 | רן סופר | **₪2,784.80** | **₪2,360** |

Plus one document approved 8× and **never created** (₪40,000 חשבון עסקה, הסתדרות כללית חדשה).

**The single most valuable data point in the whole review — ₪2,784.80 — appears only in the
Morning UI and nowhere in our own logs or data.** Any future review must obtain independent
ground truth; our logs alone would have shown a clean run.

### The unifying theme
**DeniDin reports intent as outcome.** It said ₪2,360 when Morning had stored ₪2,784.80; it
logged *"Response sent successfully… 0 chars"* for an empty message; it logged *"ChromaDB
storage completed"* immediately before failing the same operation; it re-asked the same
approval question eight times without once saying the previous attempt had failed. Most of the
ten bugs are a variation on this.

Second theme: **failures that don't look like failures** — `error=None` on a business failure,
`WARNING … skipping` on dropped data, an empty result set for an invalid input.

### Findings map — all ten bugfixes from this session

| Bug | Title | Pri | Approach |
|---|---|---|---|
| **028** *(this)* | Invoicing + approval gate P0 cluster — A1–A4, B1–B5, A3b | P0 | one pass, all together |
| **029** | Conversation quality — duplicate deposits, sycophancy, OCR dump | P1 | parallel with 028 |
| **030** | Message-sequencing ambiguity | P2 | ties to spec 032 |
| **031** | Hebrew `status` value returns empty instead of error | P2 | |
| **032** | Phone number not normalised | P2 | |
| **033** | Credit notes dropped from financial answers | P2 | |
| **034** | **Ledger bugs** — L1–L7 | P2 | |
| **035** | **Hourly maintenance bugs** — H1–H2 | P2 | **do first — actively accruing cost** |
| **036** | MCP server has no audit trail | P2 | |
| **037** | Mixed timestamp representation | P3 | |

### Decisions taken during triage (all by the user, 2026-08-09)

**Existing bad data — leave everything as it is.** Doc 90195's ₪424.80 overstatement, the four
mis-typed 305s, and the uncreated ₪40,000 document are all accepted. **Every bug from this
session is fix-forward only.** Do not "helpfully" remediate live documents.

**Ranking rule:** backend accounting, ledger and memory internals are **P2 unless they have
direct impact on user messages.** This is why bugfix-034/035 sit at P2 despite being
substantial, and why "tell the user this deposit is a duplicate" (029) is P1 while
"deduplicate the ledger" (034 L1) is P2.

**Closed as not-bugs — do not re-raise:**
- `add_client` requiring an email — required by design.
- ~~`payment[0].type = 1` (מזומן) — all payments are intentionally booked as cash.~~
  🔄 **REVERSED 2026-08-09** — the user was under a wrong impression when this was closed; the
  payment type must reflect how the money actually arrived (default type 4, bank transfer). See
  "Live sandbox verification" below. Ruth's original defect report stands after all.
- Group summaries stored `scope: PRIVATE` — verified harmless: `_filter_by_user` skips
  scope/owner filtering when `can_see_all_memories` is set, and the group resolves to ADMIN.
- OCR name instability across re-captures — removed, not of interest.

**Scope narrowed:** A3 covers the **payment-line date only**. The document date being "today"
is correct and stays.

### Gotchas for anyone continuing this work

- **`python3` resolves to another clone's venv on this machine** (observed:
  `coder2/apps/morning-mcp-app/venv/bin/python3`). Using it is a cross-clone violation. Run
  `which -a python3` and use an absolute path.
- **Log timestamps are UTC. Ledger `event_time`/`event_date`/`event_id` are local IDT (UTC+3).**
  Comparing them directly shows a phantom 3-hour gap. This is bugfix-037.
- **`wsl_ssh_run` is a shell function** — it cannot be wrapped in `timeout`.
- **`docker logs` only covers since the container was last recreated** (Aug 7 23:33 IDT here).
  The persisted files under `~/denidin-prod/apps/*/logs/prod/` go further back.
- Prod ran four versions across the window (`v0.2.1 → v0.2.2 → v0.2.3 → v0.3.0`); the
  `[vX.Y.Z]` prefix on each log line tells you which.

### Open verification items — carried, not resolved
1. **Does `get_financial_summary` route through the `ge=0` models?** If it does, the August
   figure of ₪126,658.80 is understated by the credit notes bugfix-033 describes. If it
   computes server-side at Morning, only `list_invoices` is affected. **Do not assume either
   way** — see bugfix-033.
2. **The 27 duplicate memory records** in `memory_120363210094632983_at_g.us` still need
   purging. That is a production write and needs its own explicit approval — deliberately not
   done as part of this session. See bugfix-035.

### Artifacts
| Source | Location |
|---|---|
| Full review doc | [`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../../docs/production-analysis/2026-08-09-aug7-9-review.md) |
| Read-only runbook | [`docs/production-analysis/README.md`](../../../docs/production-analysis/README.md) |
| Prod data mount | `/Users/yaron/denidin-winprod-data/` (ro) |
| Prod logs | `denidin-winprod:~/denidin-prod/apps/*/logs/prod/` |

---

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — payload builders
  (`_build_create_invoice_payload`, `_build_transaction_account_payload`,
  `_build_combo_document_payload`), `_resolve_client_by_name`,
  `_resolve_client_for_document_creation`, `list_clients`
- `apps/denidin-app/src/handlers/ai_handler.py` — `_is_affirmative_reply`,
  `_AFFIRMATIVE_REPLIES`, `_resolve_pending_approval`, `_build_pending_approval_fallback_text`,
  `_finalize_response`
- `apps/denidin-app/src/handlers/whatsapp_handler.py` — `send_response`
- `apps/morning-mcp-app/src/denidin_mcp_morning/server.py` — MCP tool signatures and
  descriptions (`create_invoice`'s generic description, A1; `create_transaction_account`'s
  missing `vat_included`, A2)
- `apps/morning-mcp-app/src/denidin_mcp_morning/formatters.py` —
  `_format_client_summary_line` (the display label of B4a), `format_invoice_confirmation`
- `apps/denidin-app/src/handlers/ai_handler.py` — also the `capture_ledger_event` schema
  (`vat_status`/`txn_date` present, bank details absent — A2, A3, A3b)
- `apps/denidin-app/src/managers/ledger_event_manager.py` — `reference` hardcoded `None` (A3b)
- `apps/denidin-app/config/runtime_constitution.md` — document-type selection guidance
  (`:231-256`), Ledger Event Recognition (`:611+`, capture-only — A1)

## Production impact already incurred

| Doc # | Type | Client | Morning holds | Should have been |
|---|---|---|---|---|
| 100012 | 305 חשבונית מס, פתוח | טלאל קרעאן | ₪2,300, dated 09/08 | 320, payment dated 06/08 |
| 100013 | 305 חשבונית מס, פתוח | עדו דניאל | ₪3,000, dated 09/08 | 320, payment dated 04/08 |
| 100014 | 305 חשבונית מס, פתוח | שלמה נזרי | ₪2,000, dated 09/08 | 320, payment dated 06/08 |
| 100015 | 305 חשבונית מס, פתוח | רלי אוחנה | ₪1,500, dated 09/08 | 320, payment dated 06/08 |
| 90195 | 300 חשבון עסקה, פתוח | רן סופר | **₪2,784.80** | ₪2,360 |
| — | חשבון עסקה | הסתדרות כללית חדשה | **never created** | ₪40,000 |

**Remediation decision (user, 2026-08-09): leave all existing documents as they are.** This
bug is fix-forward only. Doc 90195's ₪424.80 overstatement, the four mis-typed 305s, and the
uncreated ₪40,000 document are all accepted as-is.

---

## Cluster A — the documents themselves are wrong

### A1 · Payment received ⇒ must be חשבונית מס קבלה (320), not חשבונית מס (305)
All four Aug 9 invoices were created **from bank-transfer screenshots** — proof the money had
already landed — yet issued as type 305, which Morning leaves `פתוח`/unpaid. The user stated
it directly in-session (`047cacb7` turn 7): *"היית אמור לכל אלו להוציא חשבונית מס קבלה"*.
DeniDin agreed (*"נכון, את צודקת — טעיתי בסיווג"*) and took no corrective action.

**Approved root cause (2026-08-09).** A deposit reference is not treated as a document-type
signal anywhere, while 305 is simultaneously the declared default. Four pulls toward 305, and
no rule forbidding it:
1. `runtime_constitution.md:231-233` — `create_invoice` is the *"default choice when the user
   just says 'תפיק חשבונית' with no other document-type wording."*
2. `runtime_constitution.md:237-241` — the 320 entry is scoped to payment received
   *"immediately … at the time of sale"*, so a transfer that landed days ago self-excludes.
3. **Code-level affinity**: `server.py:166-177` — `create_invoice` is the only creation tool
   whose MCP description is generic (*"Create a new invoice/document in Morning."*); every
   sibling names its document type. Reinforced by the constitution's own worked examples
   (`:322`, `:412`), which use `create_invoice` as the stand-in for "create an invoice".
4. The Ledger Event Recognition section (`:611+`) is **capture-only** — it recognizes a `בנק`
   deposit and extracts its date, then says nothing about what document that implies.

**Approved fix direction (user, 2026-08-09).** A document whose reference is a **deposit** can
never be a bare 305. It resolves to exactly one of: **320** combo (money arrived, no prior
document), **400** receipt via `create_receipt` (an earlier 305 exists for that money), or
`close_transaction_account` → 320 (an earlier **300** exists — the existing 300→320 / 305→400
rule at `:245-256`). **If which one applies is not clear, the system MUST ask** — never pick.
Where any default exists in code or guidance, 320 is the go-to, not 305; `create_invoice`'s own
MCP description must spell out its type so it stops reading as the generic "make a document"
tool.

**As originally filed.** The deposit→document flow selects `create_invoice` (305). The correct
tool already exists: `create_combo_document`, type **320 = "חשבונית מס / קבלה"** (`tools.py:40`,
`models.py:38`). Selection/guidance gap, not a missing capability.

**Consequence.** `get_financial_summary` reports `לא שולם: ₪11,584.80` — entirely money
already in the bank.

### A2 · `create_transaction_account` silently adds 18% VAT
Approved ₪2,360 → Morning stored ₪2,784.80 (×1.18).

**Approved root cause (2026-08-09) — three causes.** VAT treatment is never definitively
established before a type-300 document is created:
1. **No parameter can express it.** `create_transaction_account` (`server.py:180-185`) is the
   only creation tool with no `vat_included` argument — `create_invoice`,
   `create_combo_document` and `close_transaction_account` all have one. The payload's VAT
   state is undefined by construction.
2. **No guidance links a payment reference to "VAT included."** `vat_status`
   (`כולל`/`לא כולל`/`לא צוין`, *"never assumed"*) is captured on every ledger-event component
   (`ai_handler.py:357-361`) with detailed derivation rules (`runtime_constitution.md:723-730`)
   — and is stranded there. Nothing connects the **referenced source's type** (deposit
   screenshot vs. fee agreement vs. plain request) to the VAT treatment of the document.
3. **VAT is never replayed for approval.** The ₪40,000 request said *"לפני מע״מ"* in the user's
   own words; the approval prompt did not.

**What fills the void.** An income line sent with **no `vatRate` field** is not read by Morning
as zero VAT — Morning applies its own account-level default (~18%) and stores a higher total.
Twice confirmed at exactly ×1.18: feature 023 saw a `40.0` line come back as a real `47.2`
owed (`tools.py:828-830`), and production doc 90195 took `2,360` to `2,784.80`.

**Approved fix requirements (user, 2026-08-09).**
1. **VAT is mandatory at creation — "unknown" is not a permitted state.** `vat_included` must be
   required, not defaulted; the model must be able to state definitively with-or-without before
   any document is created.
2. **A payment reference defaults to VAT *included*** — the money already arrived, so the amount
   shown is inclusive unless the user says otherwise. The missing link (cause 2) must be stated
   explicitly as guidance.
3. **VAT treatment must appear in the approval replay** (mechanics belong to B3/A4; its
   presence is a hard requirement).

**Provenance — how the code got this way** (kept for the test-gap analysis, not itself a cause):
bugfix-014 Flow 4 recorded a *business* fact — type 300 *"carries no tax obligation (no VAT
line)"* — explicitly marked *"observed by the human on the customer's real Morning site, not
yet reproduced live in the sandbox."* `_build_transaction_account_payload` turned that
unverified statement into an API-payload rule (*"no vatType/vatRate field anywhere … since the
field's mere presence implies a tax document"*), which CONSTITUTION's NO UNVERIFIED
THIRD-PARTY ASSUMPTIONS rule forbids. Feature 023 later confirmed the opposite live, in this
same file, and the finding was worked around downstream (`close_transaction_account` takes
Morning's authoritative `total`) instead of being applied back to the creation path.

**As originally filed.** `_build_transaction_account_payload` (`tools.py:174-183`) builds the
income line with **no `vatRate` and no `vatType`**, per the bugfix-014 premise that type-300
"carries NO VAT obligation". Morning applies its **default ~18%** to any income line omitting
`vatRate`. `_build_create_invoice_payload` (`tools.py:123`) sets `"vatRate": 0` explicitly —
which is why the four 305s came out correct.

### A3 · Payment-line date is "today", never the extracted transfer date
All three payload builders hardcode:
```python
today = datetime.now(timezone.utc).date().isoformat()
"date": today,
"payment": [{"type": 1, "price": amount, "date": today}],
```
No create tool accepts a transaction/payment date (`due_date` is a *future* due date).
Confirmed against ground truth: invoices dated **09/08**, deposits value-dated **04/08,
05/08→06/08, 06/08, 06/08**.

**Approved root cause (2026-08-09).** Same failure pattern as A2: the real transaction date is
captured upstream and stranded.
- **It's captured.** `txn_date` is a field on every ledger-event component (`ai_handler.py:338`)
  and is normalized to `YYYY-MM-DD` with a warning when it can't be (`ledger_event_manager.py:310-320`);
  the constitution has explicit extraction rules for it (`runtime_constitution.md:817-820`).
- **Nothing can carry it.** No create tool has a transaction/payment-date parameter. `due_date`
  is not it — it maps to `dueDate`, a *future* deadline, and never touches `payment[0].date`.
- **Nothing requires it.** No rule says a document issued against a deposit must carry that
  deposit's real date.

Feeds A4/B3: the date approved must be the date that will be written.

**Scope (settled with user):** the **document** date being today is **correct and stays**.
Only `payment[0].date` must carry the real transaction date — already extracted from the
screenshot and already stored on the ledger event as `txn_date`.

~~**Checked and cleared — not part of this bug:** `payment[0].type = 1` (מזומן). All payments
are intentionally booked as cash.~~ 🔄 **REVERSED 2026-08-09** — the payment type is now in
scope: default **4** (`העברה בנקאית`), other types when the user supplies them. See A3b.

### A3b · Bank/branch/account not carried onto the receipt *(bundled in by user decision, 2026-08-09 — was P2-2)*
`מספר בנק`, `מספר סניף`, `מספר חשבון מחויב` and `מספר אסמכתה` are present in the extracted text
of every bank screenshot and all discarded. Bundled here rather than filed separately because it
is **the same payment object, the same builders and the same call site as A3** — the transaction
date and these fields travel together or not at all.

**Approved root cause (2026-08-09) — two gaps, not one.**
1. **Nothing captures them.** Unlike `txn_date` (A3), these fields are **not in the
   `capture_ledger_event` schema at all** — its fields are `source_type`, `event_subtype`,
   `client_name`, `payer_name`, `amount`, `description`, `components`, `agreement_label`,
   `replaces_hint`, `reference_hint`, `raw_message_excerpt` — and `ledger_event_manager.py:350`
   hardcodes `"reference": None` (*"always blank in this feature"*). They exist only in the
   raw extracted image text.
2. **Nothing carries them.** `payment[0]` is built with exactly three keys (`type`, `price`,
   `date`) in all three builders.

🚨 **Unverified third-party assumption, must be settled before fix design:** "Morning's payment
object accepts them" is **not confirmed** by any real call. CONSTITUTION's NO UNVERIFIED
THIRD-PARTY ASSUMPTIONS rule requires a real sandbox call confirming which of these fields
Morning's payment object actually accepts, before any fix is designed around them — this is
precisely the class of assumption that caused A2.

Not a P0 in its own right; it rides along because splitting it would mean touching the same
code twice.

### A4 · The user approves A and the system creates B
**Approved root cause (2026-08-09) — this is a *create-stage* defect, not an after-the-fact
verification one.** The approval gate approves **the request, not the document that will be
created.** Nothing in the flow derives the true, final field values before the approval prompt
is built, so the user authorizes figures that will not match what exists a second later:
approved ₪2,360 → Morning stored ₪2,784.80.

**Requirement.** When a requested amount's VAT treatment is unresolved, the system MUST
establish it, and if the document's actual total will be **larger than the requested figure**,
that larger figure is what the user approves — **having seen it**. This holds for **every
field prior to the creation event**, not only amount.

**Failsafe (separate, added after the fix — not the bug).** A `GET` after creation verifying the
stored document matches exactly what was sent. On mismatch it MUST notify the user, show the
mismatch, and ask what to do next — never silently reconcile. The read-back pattern is already
proven live here: `close_transaction_account` takes Morning's authoritative `total` off a
fetched document precisely because a local sum *"would miss any VAT Morning silently applied"*
(`tools.py:825-830`).

**Supporting evidence.** The confirmation is not built from the created document at all: in all
three create tools the `Invoice` takes `client_name`, `amount` and `due_date` from the
**request**, only `id`/`number`/`currency`/`status` from the POST response, and
`total_amount=response.get("total", amount)` (`tools.py:223/323/370`) falls back to the amount
we asked for; `format_invoice_confirmation` (`formatters.py:62`) prints it as authoritative.
Document type, document date, payment date and VAT never appear at all. This is why A2 went
unnoticed for two days — but it is the *symptom*: the defect is that the approval never carried
the true values in the first place.

---

## Cluster B — the approval gate is broken

### B1 · The prompt invites a word the parser rejects
The confirmation prompt ends `— לאשר?`. `_AFFIRMATIVE_REPLIES` (`ai_handler.py:176`) contains
`אישור` but **not `לאשר`**. Live consequence (`12e158e2` turns 18–26): user answers `לאשר`
twice, gets the identical prompt back twice, gives up with `לא`. The phone update never
happened. `מאשאת` (typo for `מאשרת`) also rejected.

**Direction (user's, and the structural fix):** stop asking open-ended `לאשר?`; ask a closed
question — **`אישור — כן/לא?`** — so the prompt teaches an answer the parser accepts. Widening
the whitelist alone treats the symptom.

**Root cause and direction approved as filed (2026-08-09).**

### B2 · An explicit "כן" is read as a refusal when WhatsApp prefixes an RTL mark
`_is_affirmative_reply` (`ai_handler.py:185`) does `text.strip().casefold()` then
`.split()[0]`. **U+200F RIGHT-TO-LEFT MARK is not whitespace** (`'‏'.isspace() is False`), so
`‏כן` yields leading token `'‏כן'`, which misses the whitelist. Verified live: Aug 9
04:00:45 UTC the user sent `‏כן\nלהפיק…` and the log shows `approve=False`. 8 user messages in
the window carry bidi control characters; WhatsApp inserts them unpredictably on RTL
keyboards, so this fires intermittently.

**Root cause approved as filed (2026-08-09), re-verified empirically**: `'‏כן'.strip().casefold().split()[0]`
→ `'‏כן'`, and `'‏'.isspace()` is `False`.

**Fix direction NOT approved as filed (user, 2026-08-09).** Stripping a known list of bidi
characters was rejected — the matcher should work by substring/containment rather than by
enumerating characters to remove. ⚠️ Open tension to settle at fix design: the current
leading-token approach was chosen deliberately to avoid false positives
(`ai_handler.py:188-190` — *"not a substring-anywhere check, to avoid false positives on
longer unrelated sentences"*); a plain `"כן" in text` would approve
*"לא, אני לא בטוחה שזה נכון"*. A Unicode word-boundary match satisfies both (bidi marks and
punctuation stop mattering, without matching mid-sentence) and should be put up as an option
alongside plain containment.

### B3 · The approval prompt doesn't say what is being approved
**Approved root cause (2026-08-09).** Nothing in the pipeline ever constructs a **definitive
statement of what is being approved** — document type, client, amount, VAT treatment, dates.
The message the user sees is *either* the model's free narration *or*, when it narrates
nothing, a string built from tool arguments alone. Neither is guaranteed to state the actual
document that will be created.

**Not a "fallback" defect** (user's correction, 2026-08-09): in the 22 in-window turns where
the model narrated nothing, that constructed string **was** the direct path — the only message
sent. Naming it a fallback obscures that the system has no authoritative approval text at all.
This is A4 seen from the other side: you cannot approve what was never stated.

22 in-window occurrences of `WARNING Model produced no narrating text alongside a pending
approval … using fallback confirmation prompt`. The constructed text
(`ai_handler.py:1333-1350` → `_build_pending_approval_fallback_text`) renders from tool
arguments only — and the `create_transaction_account` branch (`:153`) does not interpolate
`description` at all — dropping the description and the user's own qualifiers:
```
16 DENIDIN  … על סך 40,000 ₪ לפני מע״מ, עבור צו מניעה תומר מרסיאנו, ללקוח … להפיק ולאשר?
18 DENIDIN  להפיק חשבון עסקה להסתדרות הכללית החדשה על סך 40000 ₪ — לאשר?   ← qualifiers gone
```
Consecutive attempts become indistinguishable and the user cannot tell what she is
authorising.

### B4 · The requested document was never created — client lookup rejects the name DeniDin printed
**Approved root cause (2026-08-09) — three distinct causes:**
- **(a) The system's own output is not valid input to its own tools.** `list_clients` returns a
  *display label* with `(ח.פ …, טלפון …)` appended (`formatters.py:180-186`); the create tools
  resolve by token-prefix match on the bare stored name. The name DeniDin printed is a name
  DeniDin cannot accept.
- **(b) A tool that had to run exactly once ran zero times, undetected.**
  `_resolve_pending_approval` guards `len(approved_tool_executions) > 1` (`ai_handler.py:1754`)
  with nothing checking `== 0`, and no cross-turn failure counter — hence eight approvals of the
  same ₪40,000 document with nothing created.
- **(c) "Client not found" is not treated as an error.** It returns as ordinary tool output with
  `error=None`, indistinguishable from success at every layer above it.

**Search semantics — corrected 2026-08-09 by live probe** (the original description below was
wrong, and the correction matters for the fix): the query must be a **word-aligned prefix of the
whole stored name**, not a per-word match anywhere in it. Against a seeded
`הסתדרות כללית חדשה …`:

| Query | Result |
|---|---|
| the exact stored name | ✅ 1 match |
| `הסתדרות כללית חדשה` (leading words) | ✅ found |
| `הסתדרות` (first word alone) | ✅ found |
| `כללית חדשה …` (middle words) | ❌ 0 |
| `הסתדרות חדשה …` (real words, one skipped) | ❌ 0 |
| `הסתדרות הכללית החדשה …` (ה-prefixed — live failure #1) | ❌ 0 |
| `הסתדרות כללית חדשה … (ח.פ 512345679)` (the composite — live failure #2/3) | ❌ 0 |

So a name is *narrowable* but never *decorated*: appending anything after the stored name —
a ח.פ, a phone, a parenthesis — takes it from 1 match to 0.

**Originally filed (inaccurate):** Morning's client search matches whole words, from the start of
each word — every word sent must prefix a word in the stored name. Stored client:
`הסתדרות כללית חדשה`.

| # | Sent as `client_name` | Why it found nothing |
|---|---|---|
| 1 | `הסתדרות הכללית החדשה` | Leading **ה** on words 2–3; `הכללית` doesn't prefix `כללית` |
| 2, 3 | `הסתדרות כללית חדשה (ח.פ 589103852)` | `(ח.פ` and `589103852)` are treated as words that must also match |

`list_clients {"name":"הסתדרות כללית חדשה"}` — the **bare** name — returned exactly one match
every time it was tried. The correct query existed throughout and was never sent to the create
tool, because `list_clients` returns a *display label* with the ח.פ suffix appended and the
model reasonably fed that back as the identity. **The search tool's output is not valid input
to the creation tool.**

**Why it retried forever:** the tool returns `לא נמצא לקוח בשם הזה.` as normal output with
`error=None` — indistinguishable from success. `_resolve_pending_approval`
(`ai_handler.py:1699`) guards hard against the approved tool running *more than once*
(lines 1754-1776) but has **no guard for it running zero times** and no cross-turn failure
counter.

### B5 · DeniDin sent no answer at all — repeatedly
**Approved root cause (2026-08-09).** The "never leave the user with no signal" rule is **not
actually enforced anywhere**. A send that doesn't raise is logged as
*"Response sent successfully … 0 chars"* — **a zero-character message counts as a reply.** The
single guard for this sits inside one branch (`ai_handler.py:1333`, the pending-approval path),
so every other route out of a turn is unguarded, and `send_response`
(`whatsapp_handler.py:132-149`) validates nothing at all. The second half is the same rule
failing on **meaning** rather than length: the real failure (`לא נמצא לקוח בשם הזה.`) was stated
once and then replaced on every retry by a message that said nothing about it — non-empty, but
not a reply to what happened.

**(1) A literally empty WhatsApp message** (`047cacb7` turn 22; also `12e158e2` turn 16). The
"never leave the user with no signal" fallback at `ai_handler.py:1333` is scoped **inside the
`if approval_requests and effective_chat_id:` branch only**. A turn producing
`[mcp_list_tools, reasoning, function_call…]` — no `message` item, no approval request —
leaves `response_text = ""`, `should_reply = True` (`"" != NO_REPLY_SENTINEL`,
`ai_handler.py:1367`), and `send_response` (`whatsapp_handler.py:132`) has no empty guard. It
logged *"Response sent successfully … 0 chars"*.

**(2) Four replies that said nothing** (turns 24, 26, 28, 30). The failure
`לא נמצא לקוח בשם הזה.` was surfaced **once** (turn 20) and never again — each retry emitted a
fresh approval request with no narration, so B3's fallback overwrote the explanation.

---

## Fix sequencing (do not split these pairs)
- **A1 + A3 + A3b** — one payload change across the three builders. A 320 issued today is
  still dated wrong, and the bank details live on the same payment object.
- **B1 + B2** — both gate the same word. Fixing the prompt still loses to the RTL mark.
- **B4 + B5** — fixing creation still leaves the user un-told when something else fails.
- **A2 + A3 + A4 + B3 (new, from the 2026-08-09 approvals)** — these converge on one thing:
  **the approval must state the true, final values of the document that will be created**
  (type, client, amount *after* VAT, payment date). A2 supplies the VAT treatment, A3 the
  payment date, A4 the requirement that the user approves those actual values, B3 the
  authoritative statement that carries them. Fixing any one alone still leaves the user
  approving something other than what gets created.

## Live sandbox verification (2026-08-09)

Six probe rounds against the **real Morning sandbox**, run to satisfy CONSTITUTION's NO
UNVERIFIED THIRD-PARTY ASSUMPTIONS before any test or fix was designed. Everything below is
observed behaviour, not inference.

### A2 — the mechanism is `vatType`, not `vatRate`
| Type-300 payload | Sent | Morning stored |
|---|---|---|
| **no `vatType` at all** (what the code sends today) | price 11 | **12.98** — `vatRate: 0.18`, `vat: 1.98` |
| `vatType: 0` (price *excludes* VAT) | price 11 | **12.98** — identical to sending nothing |
| `vatType: 1` (price *includes* VAT) | price 11 | **11** — `vatRate: 0`, `vat: 0` |

Omitting `vatType` is treated exactly as "price excludes VAT". The fix is therefore to send
`vatType` explicitly, driven by the mandatory `vat_included` of A2's requirement 1 — confirmed
to produce the correct total. Adding `vatRate: 0` alone is **not** the fix.

Related: a type-320 whose income total and payment total disagree is **rejected outright**
(`errorCode 2422 — קיים חוסר התאמה בין סכום התקבולים לסכום התשלומים`), so on a combo document a
VAT mistake fails loudly instead of inflating silently.

### A4 — the POST response genuinely has no total
`POST /documents` returns exactly: `client`, `id`, `lang`, `number`, `signed`,
`taxAuthorityConfirmationInitiated`, `taxAuthorityConfirmationLastError`, `type`, `url`,
`vatRate`. **No `total`, no `amount`.** `response.get("total", amount)` therefore *always*
returns what we sent. A4's premise is now verified rather than inferred.

### A3 — verifiable, but only on 320/400
`GET /documents/{id}` returns a `payment` array, and the stored line carries **`"date":
"2026-07-12"`** — the date sent, not today. Critically, it is populated **only on types 320 and
400**; on a type 300 or 305 the array comes back `[]` even when a payment line was accepted
without error. The document types A1 says a deposit must produce are exactly the ones that
persist payments, so A3 is testable end-to-end on the real target.

### A3b — the premise is false as filed; needs a decision
Bank details persist **only on payment type 4 (`העברה בנקאית`)**, never on type 1 (`מזומן`),
which silently drops every one of them. Real field names, confirmed:

| Field | Accepted on type 4 | Note |
|---|---|---|
| `bankName` | ✅ | |
| `bankBranch` | ✅ | *not* `branchNumber` |
| `bankAccount` | ✅ | *not* `accountNumber` |
| `transactionId` / `chequeNum` / `ref` / custom `description` | ❌ silently dropped | `transactionId` persists only on type 5 (PayPal) |

Morning also auto-renders the three into a human-readable line:
`"description": "בנק בנק הפועלים / סניף 613 / מס' חשבון 123456"`.

### Payment types — the full map (probed, not guessed)
| `type` | Morning's name | Fields it persists |
|---|---|---|
| 1 | מזומן | — (silently drops everything else) |
| 2 | צ׳ק | rejects without cheque details (`errorCode 2443`) |
| 3 | כרטיס אשראי | `cardNum`, `cardType`, `dealType`, `numPayments` |
| **4** | **העברה בנקאית** | **`bankName`, `bankBranch`, `bankAccount`** — no `transactionId` |
| 5 | פייפאל | `accountId`, `transactionId` |
| 10 + `appType` | אפליקציית תשלום | `transactionId`; **`appType: 1` = bit**, 2 = Pay, 3 = PayBox, 4 = Colu, 5 = Google Pay, 6 = Apple Pay |
| 11 + `subType` | אחר | 1 = ביטקוין, 2 = שווה כסף, 3 = V-CHECK |

Types 6–9 and 12 don't exist (`קוד סוג תשלום לא תקין`).

### 🔄 Triage decision REVERSED (user, 2026-08-09)
The earlier entry under "Closed as not-bugs" — *"`payment[0].type = 1` (מזומן) — all payments are
intentionally booked as cash"* — **is withdrawn.** The user: *"I was under the wrong impression
that all deposits are regarded as cash, but that's not so."*

**New policy:** the payment type must reflect how the money actually arrived.
- **Default: type 4 (`העברה בנקאית`)** — a bank deposit is booked as a bank transfer, carrying
  `bankName`/`bankBranch`/`bankAccount`.
- **Any other type when the user supplies the information** — cash, cheque, credit card, PayPal,
  or a payment app.
- **bit** is `type: 10, appType: 1` — *"lay the land for bit deposits"* (user). Worth noting it
  **does** persist `transactionId`, rendered as `"bit / מס' עסקה 987654321"`, so an **אסמכתה can
  be carried on a bit payment even though a bank transfer has nowhere to put one.**

### B4 — precondition satisfied, semantics corrected
Two clients sharing a first name-word with different (check-digit-valid) tax IDs coexist
happily, and a first-word search returns them both, so **B4-T1 is buildable as approved**. The
search semantics themselves were mis-stated in the original filing — see the corrected table
under B4. Note tax IDs must satisfy the Israeli check digit or `add_client` refuses with
`errorCode 1111`.

---

## Test-gap analysis

The root-cause gate (METHODOLOGY.md §VII step 2) is **passed** — all ten approved individually,
2026-08-09. The billed/expensive test set below was then reviewed sub-bug by sub-bug and approved
the same day; tier placement was decided by the user (only `billed`/`expensive` were reviewed —
unit/integration coverage is left to the implementer's judgement).

### Why the existing suites caught none of this
- **A1** — `tests/expensive/test_ledger_event_capture_e2e.py` stops at *capture*; it never asks
  for a document afterwards. `tests/billed/test_denidin_morning_document_creation_e2e.py` only
  ever requests document types **by name** (*"תפיק חשבון עסקה"*), so tool selection was never
  exercised as a judgement call. Nothing went deposit-image → document.
- **A2** — the sandbox tests assert a type-300 is *created* (an id/number comes back); none reads
  the stored total back, so an 18% inflation is invisible to them.
- **A3** — every sandbox test creates and asserts on the same day, so `payment[0].date == today`
  is indistinguishable from correct.
- **B1** — every approval E2E test replies with the literal `"כן"`, the one word guaranteed to be
  in the whitelist. No test ever answers the prompt with the word the prompt itself invites.
- **B2** — no test has ever sent a bidi control character, though real WhatsApp traffic is full
  of them.
- **B3/A4** — no test asserts on the *content* of the approval message; they assert on what
  executed after it.
- **B4/B5** — no test feeds a tool's own output back as another tool's input, and none drives a
  turn that fails to produce a reply.

### Approved test set — `expensive` (2 runs)
- **A1-T1** — extend `test_given_real_bank_deposit_image_then_full_fields_correctly_persisted`
  (`tests/expensive/test_ledger_event_capture_e2e.py:506`) to continue into document creation.
  🚨 Rewriting an approved test — **explicitly signed off by the user, 2026-08-09**; it starts
  requiring a live Morning tunnel and a godfather chat. **Test data must be cleared before and
  after** (user requirement) to prevent collisions/duplicates. One vision call, four sub-bugs:
  - **A1** — `create_combo_document` (320) executes; `create_invoice` never does
  - **A3-T2** — the created document's `payment[0].date` is **2026-07-12** (the screenshot's
    date), not the run date
  - **A2-T3** — the approval states *כולל מע״מ*; Morning's stored total is **1,500**
  - **B3 optionals** — bank details and transaction date appear in the approval
- ~~**A1-T2**~~ — 🔄 **MOVED to bugfix-038, 2026-08-10.** Originally: seed a real 305 matching
  the deposit, send the same bank image, assert `create_receipt` (400) against it with the
  approval naming the invoice. Investigating its failure showed the real blocker isn't a
  bugfix-028-scoped issue: `create_receipt`'s only reference argument is `original_invoice_id`
  (an internal Morning id the constitution forbids showing), and none of the three "Group B"
  tools (`create_receipt`/`create_credit_note`/`close_transaction_account`) carry the
  referenced document's real data (display number, amount, actual VAT) anywhere
  `_build_pending_approval_details` can read it — a structural gap `_build_pending_approval_details`
  was never built for, spanning three tools, not a bugfix-028 fix. Test physically relocated to
  `tests/expensive/test_group_b_reference_approval_e2e.py`; see
  `specs/bugfixes/bugfix-038-group-b-approval-missing-reference-data.md` for the full
  root-cause writeup and the design directed by the user.

### Approved test set — `billed` (4)
- **A2-T1** — *"תפיק חשבון עסקה ל-X על סך 47 ₪ כולל מע״מ"* → approve → Morning's stored total is
  **47**. *Today:* 55.46, while the confirmation says ₪47.00.
- **A2-T2** — same request, VAT unstated → DeniDin **asks** whether VAT is included and creates
  nothing that turn. *Today:* creates silently with undefined VAT.
- **B3-T1** — *"…על סך 47 ₪ לפני מע״מ, עבור ייעוץ משפטי"* → the approval message must carry all
  **six mandatory elements**: document type, document date (today), client name, amount (**not
  necessarily final** — may be pre-VAT), VAT treatment (included/not), purpose. Any one missing
  fails. *Today:* VAT and document date are absent, and `create_transaction_account`'s path
  can't carry the purpose at all.
- **B4-T1** — seed **two clients sharing their first name-word** (the live `הסתדרות` shape,
  different ח.פ), then request a combo invoice for that name. The ambiguity forces the model to
  qualify the name — the composite that fails today. Asserts the document is created **against
  the right client**. *Precondition:* confirm the sandbox permits this before writing it.

Approval-message field contract (from B3, applies to **every** document-creation approval):
mandatory — type, document date, client, amount, VAT, purpose; optional when known — bank
details (number/branch/account), transaction date, reference invoice number.

### Left to unit/integration (user's call: *"only billed and expensive"* are reviewed here)
- **B2** — bidi-tolerant affirmative matching, plus an over-approval guard so a containment-based
  fix can't start approving refusals.
- **A3-T3/T4/T5** — payment date missing / unparseable / in the future ⇒ the create request
  **fails** rather than silently substituting today. (User notification on failure is **B4(c) +
  B5**, not A3.)
- ~~**B4-T2**~~ — a requested tool cannot end up never running; a client that is known to exist
  and isn't found raises an **error**. 🔄 **Split 2026-08-10**: the "known-existing client not
  found raises an error" half is B4(c), already covered by
  `test_morning_sandbox_client_not_found_is_an_error.py`. The "tool cannot end up never
  running" half is B4(b) specifically, covered by 6 new unit tests in
  `tests/unit/test_ai_handler_zero_execution_detection.py` — written 2026-08-10, after being
  flagged in `bugfix-028-HANDOFF.md` as assigned-but-never-actually-written.
- **B5** — the two-sided response contract (see below).
- **A3b** — after the sandbox probe.

### No test
- **B1** — fix is to redo the approval question itself (closed `כן/לא` form). User: *"No need for
  tests — just redo the approval question."*

### Tests written (2026-08-09) — awaiting the §VII step-5 approval gate
| File | Tier | Covers | Status |
|---|---|---|---|
| `apps/morning-mcp-app/tests/integration/test_morning_sandbox_payment_details.py` *(new)* | integration | A2, A3, A3-T3/T4/T5, A3b (incl. bit) | **10 red** |
| `apps/morning-mcp-app/tests/integration/test_morning_sandbox_client_not_found_is_an_error.py` *(new)* | integration | B4(a), B4(c) | **4 red** |
| `apps/denidin-app/tests/unit/test_ai_handler_approval_bidi.py` *(new)* | unit | B1, B2 | **12 red**, 6 guards green |
| `apps/denidin-app/tests/unit/test_response_owed_contract.py` *(new)* | unit | B5 | **5 red**, 2 guards green |
| `apps/denidin-app/tests/billed/test_denidin_approval_content_and_vat_e2e.py` *(new)* | billed | A2-T1, A2-T2, B3-T1, B4-T1 | 4 tests, collect-verified |
| `apps/denidin-app/tests/expensive/test_ledger_event_capture_e2e.py` *(modified)* | expensive | A1-T1 (+A2-T3, A3-T2, A3b, B3 optionals) | **PASSED** (2026-08-10, after A2 default-VAT fix + date-display fix) |

**31 tests red on current code**; no pre-existing test broke (741 passed in denidin-app's unit
suite, 243 in morning-mcp-app's). The 6 billed/expensive tests need a live Morning tunnel and
real OpenAI calls, so they are written and collect-verified but not yet run — running them is
its own approval decision.

Guard tests that pass today by design (their job is to fail if a fix over-broadens): the
bidi refusal cases (a containment-based matcher must not read `לא נכון` as approval) and the
no-reply-owed cases (Feature 039's legitimate silence must stay possible).

### Implementation status (2026-08-09)
Unit + integration are **green in both apps**: 787 passed in `denidin-app`
(102 billed/expensive deselected), 352 in `morning-mcp-app`. pylint 9.07/10, mypy clean.

| Sub-bug | What changed |
|---|---|
| **A1** | `runtime_constitution.md` — money already received is never a bare 305; it is a 320, a 400 against an existing 305, or `close_transaction_account` against a 300, **and if it isn't clear which, ask**. `create_invoice`'s MCP description now spells out its type and warns off already-received money. |
| **A2** | `vat_included` is a **required** argument on `create_transaction_account`, and drives an explicit `vatType` on the payload (the real mechanism — `vatRate` was never it). Constitution requires asking "האם הסכום כולל מע\"מ?" rather than defaulting. |
| **A3** | `payment_date` is **required** on `create_combo_document`, validated by `_validate_payment_date` — missing, unparseable, or future all raise rather than silently substituting today. |
| **A3b** | `_build_payment_line` maps method → Morning's real payment type; **default is 4 (`העברה בנקאית`)**, carrying `bankName`/`bankBranch`/`bankAccount`; bit (`type 10, appType 1`) and PayPal carry `transactionId`. |
| **A4** | `_read_back_stored_total` GETs the created document (the POST response has no total at all) and `_amount_mismatch_warning` reports any divergence to the user, showing both figures and asking — never silently reconciling. The pre-creation half is B3's block. |
| **B1** | `לאשר` added to `_AFFIRMATIVE_REPLIES`; every approval now ends with the closed `אישור — כן/לא?`. |
| **B2** | `_is_affirmative_reply` finds the leading token via `re.search(r"\w+")` — no enumerated character list (rejected by the user), and still anchored on the first word so `לא נכון` cannot read as approval. |
| **B3** | `_build_pending_approval_details` appends a structured `📋 לאישור:` block on **every** approval turn (not as a fallback), carrying all six mandatory elements plus optionals when known. |
| **B4** | (a) `_strip_client_name_decoration` retries a failed lookup without a trailing `(ח.פ …)`; (b) `_resolve_pending_approval` now detects **zero** executions of the approved tool, clears the pending approval and tells the user plainly; (c) `ClientNotFoundError` replaces the friendly-string return. |
| **B5** | `AIResponse.__post_init__` refuses to build a reply-owed response with no text; `send_response` refuses to send an empty body or one where no reply is owed. `[[NO_REPLY]]` kept, per the decision below. |

**Existing tests changed as a consequence** (flagged per METHODOLOGY's test-immutability rule —
each asserted behaviour this bugfix declares wrong, or called a signature that changed):
- `test_build_transaction_account_payload_has_no_vat_fields` → **inverted** and renamed: it
  asserted the payload carried no VAT fields at all, pinning A2's bug in place.
- `test_resolve_client_for_document_creation_zero_matches_returns_refusal` → **now expects a
  raise**; same for `test_create_invoice_zero_matches_refuses_and_creates_nothing` and
  `test_create_transaction_account_refuses_when_client_not_found` (B4c).
- ~8 further call sites updated mechanically for the new required arguments.
- `tests/unit/test_response_owed_contract.py`'s third case was rewritten by me before review:
  my first version forbade a no-reply response from carrying text, which broke two approved
  dispatch tests. The contract was wrong, not the tests.

### Design decisions taken at this gate
- **B5** — **keep the `[[NO_REPLY]]` sentinel** (Feature 039) and add a turn-level **contract**
  around it: "no reply" becomes an explicitly declared outcome the turn is checked against, so
  empty-by-intent and empty-by-failure stop being indistinguishable. Not every turn owes a reply
  — a group message aimed at someone else legitimately owes none — so "always non-empty" would be
  the wrong assertion. The billed tests exercise this implicitly: they assert on responses, so a
  missing one fails them.
- **B4(a) fix direction (user, 2026-08-09, not settled)** — the stored name was clean; the *model*
  appended the ח.פ it had learned from the client listing, and that composite broke the next call.
  Candidate fix: require the model to state client details explicitly so later references are
  unambiguous, pushing the ambiguity to the user to resolve rather than guessing.

### Carried forward, unresolved
- ~~**A3b needs a user decision**~~ — **resolved 2026-08-09**: payment type defaults to **4**
  (`העברה בנקאית`); other types when the user supplies them; bit (`type 10, appType 1`) is
  explicitly provided for. The אסמכתה is carried on bit/PayPal and dropped on bank transfer,
  where Morning has no field for it.
- **A3b scope grew** — it is no longer only "carry the bank fields": the payment **type** itself
  is now part of the fix, and the `capture_ledger_event` schema needs the bank fields plus a
  payment-method concept it doesn't have today.
- **B2's fix approach is open** — containment vs. Unicode word boundary; see B2.
- ~~**B4-T1's precondition**~~ — **resolved 2026-08-09**: the sandbox permits it; test is
  buildable as approved.
- ~~**A3b's Morning-side field support is unverified**~~ — **resolved 2026-08-09** by probe.

Note for whoever picks this up: every one of these nine reproduces through a **real** path —
real Morning sandbox documents for Cluster A, real message strings for B1/B2, real tool
responses for B4/B5. No mocking is needed or permitted (CONSTITUTION §I/§V).

## Related Work
- `specs/done/027-mandatory-client-reference-invoicing/` — introduced
  `_resolve_client_for_document_creation`, the resolution path B4 fails in
- `specs/bugfixes/bugfix-027-geresh-omitted-entirely-not-fuzzy-matched.md` — sibling
  client-name matching false-negative; same `_resolve_client_by_name` call site as B4
- `specs/done/046-*` — added `מאשר`/`מאשרת`/`בטח`/`סבבה` to `_AFFIRMATIVE_REPLIES`; B1/B2 are
  the next layer of the same problem
- `specs/backlog/047-whatsapp-interactive-approval-buttons/` — filed 2026-08-09 from a user
  suggestion during this bugfix: a tapped button carries an identifier rather than a word, so
  **B1 and B2 become structurally impossible** on that path. Deliberately does not replace the
  text route, and does **not** address B3/A4 — the approval must still state what it is asking
- bugfix-014 — the "type 300 carries no VAT" finding that A2 shows to be incomplete
