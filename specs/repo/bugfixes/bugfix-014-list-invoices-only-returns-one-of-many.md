# Bugfix Spec: "All invoices from a customer" only returns one

## Bug ID
bugfix-014-list-invoices-only-returns-one-of-many

## Title
Asking for all invoices/payments from a named customer returns only a single result, even when more exist

## Status
Done — merged to `master` (PR #119, 2026-07-22). Double-counting root cause fixed, tested, and verified live end-to-end against `morning-mcp-app-dev`. Session 1's `status="paid"`-over-triggering theory did not independently reproduce and is left as a standing probabilistic check (`test_yossi_all_payments_gets_the_complete_picture`/`test_yossi_explicit_everything_request_gets_the_complete_picture` in `test_denidin_morning_mcp_e2e.py`); the pagination gap and `clientName` matching semantics remain confirmed-but-unaddressed — real, still-open risks, but no follow-up bugfix spec opened yet (revisit if either causes a future report). See "Investigation Findings" and "Implementation Summary" below.

## Date Opened
2026-07-20

## Reported By
yylevy171 (found via manual prod-environment testing, same live session as bugfix-012/013)

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — `list_invoices()`
- The AI's tool-call argument construction (`AIHandler`/`runtime_constitution.md`'s invoice-management guidance) — the actual arguments passed into the tool are as much a suspect here as the tool's own filtering logic

## Description
User asked (real WhatsApp, prod, real Morning production account): "תבדוק כל התשלומים מלקוח בשם אריאן רגב" (check all payments from client Arian Regev), and again, more explicitly: "ביקשתי את *כל* התשלומים" (I asked for *all* the payments). Both times, `list_invoices` returned exactly one invoice (#112271, ₪7,213, paid 19/07/2026) — with no indication (`has_more`) that anything was omitted, and no way for the user to know whether that's genuinely the client's only invoice or whether the search under-matched.

## Evidence (from this session's real logs)

```
20:15:11 - MCP calls: [{'name': 'list_invoices', 'arguments':
  '{"status":"paid","from_date":"2026-01-01","to_date":"2026-07-20","client_name":"אריאן רגב"}',
  'output': 'חשבונית #112271 ...'}]

20:16:12 - MCP calls: [{'name': 'list_invoices', 'arguments':
  '{"status":"paid","from_date":"2026-01-01","to_date":"2026-07-20","client_name":"אריאן רגב"}',
  'output': 'חשבונית #112271 ...'}]  (identical call/result, after user explicitly said "ALL")
```

## Suspected Root Cause (unconfirmed — needs investigation before a fix is proposed)

The strongest lead from the evidence above: **the tool call includes `status="paid"` in both attempts, even after the user explicitly said "all payments."** `list_invoices()` (`tools.py:201`) applies this as a hard client-side filter (`_matches_status`, `tools.py:174`) — any invoice for this same client that is unpaid, overdue, or cancelled would be silently excluded from the result, with no signal to the user that filtering happened. This is the same *shape* of issue as bugfix-013 (unrequested/undisclosed narrowing of a search when the user asked for something broader) — here specifically a `status` filter instead of a date filter.

Other candidates that have NOT been ruled out and would need real testing to confirm/exclude:
- **Pagination**: `_extract_items()` (`tools.py:165`) takes only `response.get("items")`/`.get("data")` from a single API response with no loop over further pages. If Morning's `/documents/search` paginates and this client's invoices span more than one page, only the first page's items would ever reach the client-side filters — silently dropping the rest with no `has_more` signal (unlike the deliberate 10-item display cap in `list_invoices`, which IS tracked via `has_more`).
- **`clientName` server-side matching semantics**: `_map_list_invoices_filters()` sends `clientName` directly to Morning's search endpoint (`tools.py:144`) — if Morning does an exact/strict match rather than a fuzzy/contains match, invoices under a slightly different real client-name variant (e.g. a company suffix, alternate spelling) would never be returned at all, independent of the status/pagination issues above.
- **Whether the customer genuinely only has one invoice** has not been independently verified against the Morning dashboard the way bugfix-012's underlying data was (user manually confirmed that one). This should be checked first, the same way, before assuming the tool is wrong.

## Steps to Reproduce
1. As a confirmed GODFATHER/ADMIN, ask for "all invoices" or "all payments" from a real named client known (via the Morning dashboard) to have more than one invoice, at least one of which is not `status=paid`.
2. Observe whether `list_invoices` returns all of them, or only a subset — and whether `status="paid"` (or any other unrequested filter) appears in the tool call's arguments.

## Investigation Findings (read-only, 2026-07-21)

**Scope of this pass**: code/config/log/documentation review only. No code was changed, no tests were run, no deployment was touched, per explicit instruction. Findings below are root-cause analysis for approval, not fixes.

### Root cause found for the `status="paid"` filter: an existing constitution rule over-generalizes from a payment-related word to a hard status filter

`apps/denidin-app/data/constitution/runtime_constitution.md` (line 200):

> "Status/action words: 'שילם' / 'לשלם' / 'שולם' → `status="paid"`; ..."

The user's request was "תבדוק כל **התשלומים** מלקוח בשם אריאן רגב" ("check all the **payments** from client Arian Regev"). "תשלומים" (payments, plural noun) shares the same ש-ל-ם root as the literal trigger words the rule lists ("שילם"=paid, "לשלם"=to pay, "שולם"=was paid), but is a different part of speech with a different, broader meaning: "give me the payment/transaction history" (a request for scope) rather than "show me only the ones marked as paid" (a request for a status filter). The rule as written doesn't clearly distinguish these, and the model's tool call (`status="paid"` in both attempts, including after the user said "ALL" explicitly) is consistent with it having over-generalized the rule to the noun form.

This is corroborated by `bugfix-013`'s own logs from the same session: the Zehavit message ("כמה **שילמה** ומתי" — "how much did she **pay** and when") also triggered `status="paid"`, and there the trigger word is even more literally "שילמה" (paid, verb form) — yet the user was clearly asking for full payment *history* ("תן לי הכל" / "give me everything" in the very same sentence), not a paid-only filter. Both incidents fit the same pattern: any mention of paying/payment vocabulary is being read as an explicit request to filter to `status="paid"`, even when the surrounding sentence asks for a broader view.

This also violates the constitution's own transparency rule (lines 202-207: "Be transparent about anything you filled in yourself... If your confidence in a filled-in value is low... ask instead of guessing silently") — neither reply disclosed that a status filter had been applied, so the user had no way to know their "all payments" request had been silently narrowed.

**Recommended fix direction** (not yet approved): narrow the constitution's rule so it only triggers `status="paid"`/`status="unpaid"`/`status="cancelled"` when the word is used to qualify a specific status *of* an invoice/action (e.g. "mark it paid", "the invoice she paid", "cancel it") — not when the user is asking broadly for "all payments"/"payment history" as a scope of what to retrieve. Also worth adding an explicit example contrasting the two ("תשלומים" as scope vs. "ששולם"/"שילמה" as a status qualifier) since the literal-word-matching approach is exactly what over-generalized here.

### Pagination gap: confirmed present in code, not confirmed as this report's cause

`MorningClient.list_invoices` (`morning_client.py:63-69`) sends whatever `params` dict it's given straight to `POST /documents/search` with **no `page`/`pageSize` keys ever added**, and does **not loop over subsequent pages**. The cached Green Invoice Postman collection (`specs/in-definition/005-mcp-morning-green-receipt/Green Invoice Public API.postman_collection.json`) confirms `/documents/search` is genuinely paginated — its own example request sets `"page": 1, "pageSize": 20`, and its example response has the shape `{"pageSize":20,"page":1,"total":0,"from":1,"to":0,"pages":0,"items":[],"aggregations":{...}}`. `_extract_items()` (`tools.py:170-176`) only ever reads `response.get("items")` from whatever single response comes back — if `page`/`pageSize` are omitted, Morning's own defaults apply (not documented in the cached collection; unconfirmed what they are), and if a client has more documents than fit on the first page, everything past page 1 is silently invisible to this tool, with no `has_more`-style signal for this specific failure mode (`list_invoices`'s own `has_more` flag only reflects its own 10-item display cap over whatever page 1 already returned — it can't detect truncation Morning itself performed upstream).

This is a real, confirmed gap independent of the `status` filter issue above — but it is **not confirmed to be what caused the Arian Regev report specifically** (that would require knowing Arian Regev's actual total document count and Morning's actual default page size/count, neither of which is available from static review). It's flagged here as a separate, real latent risk worth its own fix regardless of what caused this particular incident.

### `clientName` matching semantics: still unconfirmed, needs a live check

`_map_list_invoices_filters()` (`tools.py:149-167`) sends `clientName` directly to Morning's search endpoint. Whether Morning does exact, prefix, or fuzzy/contains matching is not stated in the cached Postman collection's description text, and confirming it would require an actual live search call — out of scope for this read-only pass. Not ruled in or out as a contributing cause.

### Recommendation

Three independent candidates, not mutually exclusive:
1. **`status="paid"` over-triggering** — root cause found and documented above; fix is a constitution wording change, same category/risk as bugfix-011's precedent. Strongest, best-evidenced candidate for what actually happened in the reported session (the identical `status="paid"` appears in both attempts, including after the user said "ALL").
2. **Pagination** — confirmed as a real gap in the code, independent of what caused this specific report; worth its own fix regardless, but needs a decision on scope (separate bugfix vs. bundled with this one).
3. **`clientName` matching** — genuinely unconfirmed; would need a live, low-risk read-only API check (e.g. searching a real client with a known alternate-name variant) before any conclusion, which was out of scope this pass.

## Expected Behavior
"All invoices"/"all payments" (no status qualifier from the user) should not silently apply a `status="paid"` filter — either omit the status filter entirely (matching `list_invoices`' own `status: Optional[str] = None` default, which already means "no filter" per `_matches_status`'s `if not status or status == "all": return True`), or explicitly ask the user whether they mean paid-only. Separately, pagination and clientName-matching behavior need to be confirmed correct against real multi-invoice, multi-status client data.

## Investigation Findings (Session 2, 2026-07-22): reproduction + a deeper, related root cause

**Reproduction against real mixed-status sandbox data**: the original spec's Acceptance Criteria called for reproducing against a real client with multiple invoices of mixed status, verified via the Morning dashboard first (not done in Session 1, read-only pass). Done this session: the existing sandbox test client "יוסי שמואלי" (already used by `test_godfather_creates_invoice_via_whatsapp`) had 6 real tax invoices (type 305) across 4 distinct dates, all unpaid. Two were deliberately closed via real Morning receipts (type 400) to build a mixed set: 4 unpaid (`50499`, `50552`, `50571`, `50607`), 2 paid (`50500`, `50604`).

Two E2E reproduction tests were added to `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py` (`test_yossi_all_payments_gets_the_complete_picture`, `test_yossi_explicit_everything_request_gets_the_complete_picture`), asserting the reply reflects ALL 6 known invoices, not a status-filtered subset. **Result of the first test run (billed, 2026-07-21): PASSED** — `list_invoices` was called with only `{"client_name": "..."}`, no unrequested `status` filter, and the reply correctly listed all 6 invoices with a paid/unpaid breakdown. This means the specific `status="paid"`-over-triggering root cause from Session 1 **did not reproduce this run** (consistent with bugfix-013's own finding that these narrowing bugs are probabilistic, not 100% reproducible — a pass here is not proof the underlying wording risk is fixed).

**A second, more concrete bug was found in the same test's reply, independent of the status-filter theory**: the model's own totals double-counted paid amounts. It listed 4 items as "paid" (₪470 total) — but two of those four (`80109`, `80110`) are not separate invoices at all, they are **receipts**, each linked to one of the other two paid entries (`50500`, `50604`). The true amount actually paid is ₪235 (88 + 147), not ₪470. `list_invoices` returns receipts and credit-invoices as flat, independent line items indistinguishable in the tool's own text output from real invoices — the `Invoice` model parses a `type` field from Morning's response but never renders it, so the model has no way to tell "this is a receipt, not a new charge" from the tool output alone.

**Deep-dive into Morning's real document model** (live, read-only investigation against `config.dev.json`'s sandbox credentials — 2026-07-21/22):
- Morning has three document flows relevant here:
  1. **Combo invoice+receipt (type 320)** — a single, self-contained document issued when payment is immediate (cash/card/instant transfer at time of sale). Always already "paid," never gets a separate linked receipt.
  2. **Two-step invoice → receipt (types 305 → 400)** — `create_invoice` issues an unpaid type-305 tax invoice; later, a separate type-400 receipt document is created when payment actually arrives, referencing the original. Amount paid on the invoice = Σ of its linked receipts' amounts (usually one, covering the full amount — the code has no partial-payment path today, though Morning's data model would support one). Amount owed = invoice amount − Σ linked receipts.
  3. **Cancellation (type 330, credit invoice / "חשבונית זיכוי")** — can apply to either flow above. A new type-330 document is created, linked to the original, with its own positive `amount` field (the negative-impact sign only shows in a separate `calculatedAmountLocal` field, never surfaced anywhere in this app). For a cancelled combo doc (flow 1), the residual after netting is still considered "paid" — cancellation just reduces recognized revenue, never creates something "owed." For a cancelled two-step invoice (flow 2), owed = invoice amount − Σ linked receipts − Σ linked credits.
  4. **Non-tax "transaction account" (type 300, "חשבון עסקה") — observed by the human on the customer's real Morning site, not yet reproduced live in the sandbox.** Like flow 2's type-305 tax invoice, this is a request for payment issued before money arrives ("the client needs to pay the amount written in this doc") — but it differs from type 305 in two ways: (a) it carries no tax obligation (no VAT line), and (b) **the document that closes it once paid is a type-320 combo ("חשבונית מס/קבלה"), not a bare type-400 receipt.** This means the linked-closing-document type is NOT constant across flows — it depends on the ORIGINAL document's own type (300 → closed by 320; 305 → closed by 400) — a rule the constitution's document-type glossary and netting instructions must state explicitly, not assume. `tools.py` already has `_TRANSACTION_ACCOUNT_DOCUMENT_TYPE = 300` defined (confirmed live via `GET /documents/types`) and includes it in `_PRIMARY_INVOICE_DOCUMENT_TYPES`, but nothing in the current codebase creates one (`create_invoice`/`_build_create_invoice_payload` always hardcodes type 305) — type-300 documents can only currently arise from something outside these MCP tools (e.g. the customer's direct Morning UI use, as observed), so `list_invoices`/`get_invoice_details` must still handle them correctly when they show up in real client data even though this app never creates them itself.
     - **Related latent bug flagged, not yet in scope for this fix**: `_build_payment_receipt_payload`/`_mark_invoice_paid` (the code behind `update_invoice_status(status="paid")`) unconditionally builds a type-400 receipt payload regardless of the original document's type. Per this newly-documented flow-4 rule, calling `update_invoice_status` to mark a type-300 document paid would issue the WRONG closing document type (400 instead of the correct 320) — a real, distinct bug from the double-counting issue this bugfix is about, only reachable if a type-300 document ever gets marked paid through this app. Recommend opening a follow-up bugfix rather than folding it into this one, since it's a mutating/write-path correctness issue (wrong document created in Morning), not a read/display issue like the rest of this bugfix.

**Four new backlog features spun out of this investigation** (2026-07-22, human-directed) — document-creation surface area that came up while investigating Flow 4 but is out of scope for this (read/display-only) bugfix:
- `specs/backlog/020-flexible-invoice-payment-methods/` — support the different ways to mark something paid (installments, correct closing-doc type per original type — directly addresses the related latent bug flagged above)
- `specs/backlog/021-flexible-document-creation/` — create any Morning document type the user asks for, not just a hardcoded type-305 invoice
- `specs/backlog/022-explicit-approval-for-document-creation/` — always require explicit human approval before any document-creating action executes
- `specs/backlog/023-reference-linked-document-creation/` — general capability to create a document as an explicit reference/link to an existing one (likely overlaps with 020)
- **The real linkage mechanism is structured and bidirectional, but only visible on the single-document GET** (`MorningClient.get_invoice` / `GET /documents/{id}`) — a `linkedDocuments` array (each entry: `id`, `type`, `number`, `documentDate`, `amount`, `currency`) appears on BOTH the original invoice and the receipt/credit that links to it. Confirmed live in both directions (invoice ↔ receipt, invoice ↔ credit). **This field is completely absent from `/documents/search`** (what `list_invoices` uses) and is not present anywhere in this app's `Invoice` model or any tool's text output today. The free-text `remarks` (receipts) / `description` (credits) fields do contain a human-readable reference to the original invoice's number (e.g. `"קבלה עבור חשבונית מס 50604"`), but these are user-editable and explicitly not trusted as a linkage mechanism.
- **Three of Morning's numeric enum fields have live, authoritative translation endpoints** that this app does not use, confirmed via real sandbox calls:
  - `GET /documents/types` → document type labels (`300`="חשבון עסקה", `305`="חשבונית מס", `320`="חשבונית מס / קבלה", `330`="חשבונית זיכוי", `400`="קבלה", plus others not currently relevant).
  - `GET /payments/types` → payment method labels on `payment[]` entries (`0`="ניכוי במקור", `1`="מזומן", `2`="צ'ק", `3`="כרטיס אשראי", `4`="העברה בנקאית", `5`="פייפאל", `10`="אפליקציית תשלום", `11`="אחר").
  - `GET /documents/statuses` → status labels, and this one is a **correction** to existing code: `models.py`'s hardcoded `_MORNING_STATUS_CODES = {0: "unpaid", 1: "paid", 2: "paid", 3: "cancelled", 4: "cancelled"}` collapses distinctions the API's own names preserve (`0`="מסמך פתוח", `1`="מסמך סגור", `2`="מסמך סומן ידנית כסגור", `3`="מסמך מבטל", `4`="מסמך שבוטל" — `3`/`4` distinguish a cancelling document from the thing it cancelled, not just "cancelled" generically).

**Approved fix direction (human-directed design session, 2026-07-22)**: explicitly rejected a code-side netting/aggregation layer (a `_resolve_invoice_ledger`-style helper that would compute paid/owed and hide receipts/credits from the model entirely) as too much ongoing code to maintain. Instead:
- **Code** (kept deliberately thin — data exposure only, no netting/business logic):
  - Add `linkedDocuments` to the `Invoice` model and to `get_invoice_details`'s text output (currently dropped entirely).
  - Translate `type` (document type), `status`, and `payment[].type` (payment method) to their real Hebrew names using **static, code-level lookup tables seeded from the three live-confirmed enum endpoints above** (`GET /documents/types`, `/documents/statuses`, `/payments/types`) — deterministic 1:1 label substitution, not interpretation. This replaces/corrects the existing ad hoc `_STATUS_HE`/`_MORNING_STATUS_CODES` translation in `models.py`/`formatters.py` with the more precise, API-verified version, and adds the same treatment for `type` and payment method (currently untranslated/unexposed).
  - `list_invoices` output gains the (now-translated) document type per line, so receipts/credits are visibly distinguishable from real invoices in the tool's own text, without the tool itself excluding or netting anything.
- **Constitution** (`runtime_constitution.md`) carries all of the reasoning: the document-type glossary and the four flows described above (including flow 4's rule that the closing-document type depends on the original's type — 300 closed by 320, 305 closed by 400), plus an explicit rule that receipts/credits/combo-closing-docs are never independent charges — when answering "how much has X paid" or "how much is owed," the model must resolve each real invoice's `linkedDocuments` (via `get_invoice_details`) and net paid/owed itself (`paid = Σ linked receipts/closing docs`, `owed = invoice amount − paid − Σ linked credits`), never sum a `list_invoices` line's raw amount directly into a total. A worked example based on the real Yossi Shmueli double-counting mistake is included as a concrete negative example.
- Rationale for choosing code-level translation (not constitution-only) specifically for `type`/`status`/`payment.type`: these gate business-relevant classification (is this a chargeable document at all? is it net-paid?) — a model mistranslation here would directly reproduce this same class of bug, whereas the flow arithmetic and "don't double-count" judgment is exactly the kind of reasoning explicitly wanted in the constitution rather than in code.

## Test Gap Analysis (why didn't existing tests catch the double-counting?)

Checked `apps/morning-mcp-app/tests/integration/`: existing invoice-status tests (`test_morning_sandbox_invoice_status_tools.py`) verify a SINGLE seeded invoice's own status/details after marking it paid or cancelled (`test_update_invoice_status_to_paid_then_get_details_reflects_it`, `test_update_invoice_status_cancelled_issues_a_linked_credit_invoice`) — always via `get_invoice_details` for the one invoice, never via `list_invoices` returning that invoice alongside its own receipt/credit as separate rows. Existing `list_invoices` tests (`test_morning_sandbox_list_invoices*.py`) use single freshly-seeded, always-unpaid invoices, or check pagination/no-match/cap behavior — none seed a client with a mix of real invoices AND their linked receipts/credits, and none assert on any computed total across multiple results. `apps/denidin-app`'s own E2E suite (`test_denidin_morning_mcp_e2e.py`) had the same gap prior to this session's additions — `test_godfather_lists_invoices_via_whatsapp` uses the reusable 2026-02-07 fixed date set (6 invoices, none marked paid via a receipt in that set), so a receipt was never present in the result set an E2E test actually inspected. This is why the double-counting bug was never caught: no test at any layer ever exercised "a client whose search results include both a primary invoice and a document that links to it."

## Acceptance Criteria (double-counting root cause: fixed, tested, verified live)
- [x] Reproduce against a real client with multiple invoices of mixed status (verify ground truth via Morning dashboard/API first, as bugfix-012 was) — done this session against יוסי שמואלי's real sandbox data
- [x] Strongest Session-1 root-cause candidate (`status="paid"` over-triggering) — reproduction test written and run once; did not reproduce this run (probabilistic, per bugfix-013 precedent). **Left as a standing probabilistic reproduction check** (`test_yossi_all_payments_gets_the_complete_picture`/`test_yossi_explicit_everything_request_gets_the_complete_picture`), not separately fixed this session.
- [x] A second, concrete, deterministically-reproducible root cause found: receipts/credits counted as independent charges, double-counting paid amounts — confirmed live against real sandbox data and Morning's actual document/linkage model
- [x] Pagination gap independently confirmed to exist in the code (real, but not confirmed as this specific report's cause) — **still open, not addressed by this fix, no follow-up spec opened yet**
- [ ] `clientName` matching semantics confirmed (still needs a live check) — **still open, not addressed by this fix**
- [x] Root cause explanation(s) and fix direction approved by human (BDD gate) — 2026-07-22, this session
- [x] Test gap analysis documented (why didn't existing tests catch the double-counting?) — see above
- [x] Failing test(s) written and approved (BDD, per METHODOLOGY §VII) before any fix — unit (models/formatters), integration (real sandbox), E2E (real OpenAI+MCP) all written and approved before implementation
- [x] Fix implemented: `LinkedDocument` model + `Invoice.linked_documents`, `translate_document_type`/`translate_payment_type` (live-confirmed static tables), `list_invoices`/`get_invoice_details` output changes in `apps/morning-mcp-app`; full document-model glossary + netting algorithm added to `runtime_constitution.md`
- [x] Tests pass; no regression in the existing Morning tools test suite — 94/94 unit tests pass (48 new + 46 pre-existing, zero regressions); new sandbox integration test (`test_morning_sandbox_linked_documents.py`) functionally verified live via a direct script (blocked from running under `pytest` itself by a **pre-existing, unrelated** gap — `config.test.json` has placeholder Morning credentials, confirmed to already block an existing test the same way before this session's changes; not fixed here per "config is code")
- [x] Re-verified live against real sandbox data — `test_yossi_all_payments_gets_the_complete_picture` (real WhatsApp turn → real OpenAI Responses API → real Morning MCP server, rebuilt+redeployed to `morning-mcp-app-dev` first) now correctly replies "**סה״כ תשלומים: ₪235**" (not the double-counted ₪470), explicitly citing each payment's linked receipt by number. Not yet re-verified against production (informational only, no prod incident re-test performed).

## Implementation Summary (2026-07-22)

**Code** (`apps/morning-mcp-app/src/denidin_mcp_morning/`):
- `models.py`: new `LinkedDocument` model + `Invoice.linked_documents` field (mapped from `linkedDocuments`, only present on the single-document GET, never on `/documents/search`); new `_DOCUMENT_TYPE_NAMES`/`_PAYMENT_TYPE_NAMES` static tables seeded from live `GET /documents/types`/`GET /payments/types`. Existing canonical `_MORNING_STATUS_CODES` (used by `_matches_status` filtering) deliberately left untouched to avoid a functional regression — the more precise raw Morning status labels from `GET /documents/statuses` were investigated but not wired in, since nothing in this fix's scope needed the extra `מבטל`/`שבוטל` precision.
- `formatters.py`: new `translate_document_type`/`translate_payment_type`; `format_invoice_confirmation` now includes the translated document type per line (so `list_invoices` output visibly distinguishes invoices/receipts/credits); `format_invoice_details` now includes a `מסמכים מקושרים` (linked documents) section when present.
- No changes to `tools.py` — the fix is data-exposure only, per the approved "thin API, all reasoning in the constitution" direction (a code-side netting/ledger layer was explicitly considered and rejected).

**Constitution** (`apps/denidin-app/data/constitution/runtime_constitution.md`): new "Understanding Morning's document model — never double-count linked documents" section — the 4-flow glossary (combo/two-step/transaction-account/credit) and the per-invoice paid/owed resolution algorithm, with a concrete worked example of the exact double-counting mistake this bugfix fixes.

**Tests added**: 4 model unit tests, 9 formatter unit tests (all passing, no regressions in the other 85 pre-existing unit tests), 2 real-sandbox integration tests (functionally verified live, blocked from `pytest` by the pre-existing config gap noted above), E2E assertion extended in both Yossi tests to require the reply state the true ₪235 total, never the double-counted ₪470.

**Deployment note surfaced during this work**: `morning-mcp-app-dev`'s running container does not rebuild on `run_morning_mcp.sh` alone — required an explicit `docker compose build` (separately approved) before the fix took effect, exactly the gap CLAUDE.md already warns about. A transient DNS resolution failure immediately after container restart caused one wasted, billed E2E run — confirmed transient (resolved itself within ~15s) and unrelated to the code change, but is why the fix took two billed E2E attempts to confirm rather than one.

**Explicitly out of scope, still open**: pagination gap, `clientName` matching semantics, `status="paid"` over-triggering (left as a standing probabilistic check), Flow 4's related latent write-path bug (`_mark_invoice_paid` always issuing a type-400 receipt regardless of original type) — spun out to `specs/backlog/020-flexible-invoice-payment-methods/`. Document-creation feature ideas that came up during investigation spun out to `specs/backlog/021`, `022`, `023`.

## References
- `specs/bugfixes/bugfix-012-financial-summary-drops-nonallowlisted-invoice-types.md` (if written — see note below) and `bugfix-013` (Zehavit name/date-narrowing) — same live testing session, related "unrequested narrowing" pattern
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)

## Note
`bugfix-012` (get_financial_summary type-filter bug) was subsequently written up, fixed, and merged (`specs/done/v0.0.1/bugfix-012-financial-summary-drops-nonallowlisted-invoice-types.md`, PR #111). `bugfix-013` (Zehavit client-name garbling / unrequested date narrowing) was also subsequently written up and has now had its root cause investigated (see that spec's own Investigation Findings section, added 2026-07-21 in the same pass as this file's).
