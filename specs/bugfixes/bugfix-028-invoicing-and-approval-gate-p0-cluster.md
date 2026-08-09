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
**Open — backlogged.** No fix designed or implemented. Per Bug-Driven Development
(METHODOLOGY.md §VII), the next step is human approval of the root causes below before
test-gap analysis or fix design begins.

Filed in `specs/bugfixes/` because that is the canonical home for open bugfix specs
(CLAUDE.md, `specs/bugfixes/README.md`); there is no `specs/backlog/bugfixes/`. "Backlogged"
is recorded here in Status rather than by folder.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from live production use 7–9 Aug 2026, plus code/data forensics against the
read-only prod mount and prod logs. Full evidence and provenance:
[`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md).

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
[`docs/production-analysis/README.md`](../../docs/production-analysis/README.md).

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
- `payment[0].type = 1` (מזומן) — all payments are intentionally booked as cash. *(Ruth
  initially raised this as a defect; withdrawn.)*
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
| Full review doc | [`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md) |
| Read-only runbook | [`docs/production-analysis/README.md`](../../docs/production-analysis/README.md) |
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
- `apps/denidin-app/config/runtime_constitution.md` — document-type selection guidance

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

**Root cause.** The deposit→document flow selects `create_invoice` (305). The correct tool
already exists: `create_combo_document`, type **320 = "חשבונית מס / קבלה"** (`tools.py:40`,
`models.py:38`). Selection/guidance gap, not a missing capability.

**Consequence.** `get_financial_summary` reports `לא שולם: ₪11,584.80` — entirely money
already in the bank.

### A2 · `create_transaction_account` silently adds 18% VAT
Approved ₪2,360 → Morning stored ₪2,784.80 (×1.18).

**Root cause.** `_build_transaction_account_payload` (`tools.py:174-183`) builds the income
line with **no `vatRate` and no `vatType`**, per the bugfix-014 premise that type-300 "carries
NO VAT obligation". Morning applies its **default ~18%** to any income line omitting
`vatRate`. The same file already documents this at `tools.py:826-831`:
*"confirmed live: a 40.0 item with no vatRate became a real 47.2 'amount' owed"*.
`_build_create_invoice_payload` (`tools.py:123`) sets `"vatRate": 0` explicitly — which is why
the four 305s came out correct.

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

**Scope (settled with user):** the **document** date being today is **correct and stays**.
Only `payment[0].date` must carry the real transaction date — already extracted from the
screenshot and already stored on the ledger event as `txn_date`.

**Checked and cleared — not part of this bug:** `payment[0].type = 1` (מזומן). All payments
are intentionally booked as cash.

### A3b · Bank/branch/account not carried onto the receipt *(bundled in by user decision, 2026-08-09 — was P2-2)*
`מספר בנק`, `מספר סניף`, `מספר חשבון מחויב` and `מספר אסמכתה` are present in the extracted text
of every bank screenshot and all discarded. Morning's payment object accepts them. Bundled here
rather than filed separately because it is **the same payment object, the same builders and the
same call site as A3** — the transaction date and these fields travel together or not at all.

Not a P0 in its own right; it rides along because splitting it would mean touching the same
code twice.

### A4 · Confirmations report the requested amount, not the document's real total
`tools.py:249` — `total_amount=response.get("total", amount)`. Morning's `POST /documents`
response carries no usable `total`, so it falls back to **the amount we asked for**;
`format_invoice_confirmation` (`formatters.py:61`) prints that as authoritative. This is why
A2 went unnoticed for two days: the MCP returned `סכום: ₪2,360.00` for a document Morning had
stored at ₪2,784.80. Structural — any server-side adjustment is invisible.

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

### B2 · An explicit "כן" is read as a refusal when WhatsApp prefixes an RTL mark
`_is_affirmative_reply` (`ai_handler.py:185`) does `text.strip().casefold()` then
`.split()[0]`. **U+200F RIGHT-TO-LEFT MARK is not whitespace** (`'‏'.isspace() is False`), so
`‏כן` yields leading token `'‏כן'`, which misses the whitelist. Verified live: Aug 9
04:00:45 UTC the user sent `‏כן\nלהפיק…` and the log shows `approve=False`. 8 user messages in
the window carry bidi control characters; WhatsApp inserts them unpredictably on RTL
keyboards, so this fires intermittently.

### B3 · The approval prompt doesn't say what is being approved
22 in-window occurrences of `WARNING Model produced no narrating text alongside a pending
approval … using fallback confirmation prompt`. The fallback
(`ai_handler.py:1333-1350` → `_build_pending_approval_fallback_text`) renders from tool
arguments only, dropping the description and the user's own qualifiers:
```
16 DENIDIN  … על סך 40,000 ₪ לפני מע״מ, עבור צו מניעה תומר מרסיאנו, ללקוח … להפיק ולאשר?
18 DENIDIN  להפיק חשבון עסקה להסתדרות הכללית החדשה על סך 40000 ₪ — לאשר?   ← qualifiers gone
```
Consecutive attempts become indistinguishable and the user cannot tell what she is
authorising.

### B4 · The requested document was never created — client lookup rejects the name DeniDin printed
Morning's client search matches **whole words, from the start of each word** — every word sent
must prefix a word in the stored name. Stored client: `הסתדרות כללית חדשה`.

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

## Test-gap analysis
Not started — blocked on human approval of the root causes above (METHODOLOGY.md §VII).

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
- bugfix-014 — the "type 300 carries no VAT" finding that A2 shows to be incomplete
