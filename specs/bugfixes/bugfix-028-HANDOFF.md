# Handoff: bugfix-028 (Invoicing + Approval Gate P0 Cluster)

**As of**: 2026-08-10 (session start 2026-08-09). Root causes approved for all 10 sub-bugs
(A1–A4, B1–B5), tests written and approved, fixes implemented, and the full approved
unit/integration/billed/expensive test set is **green**. `A1-T2` was carved out mid-session
into a new bugfix (038) once investigation showed it needed infrastructure outside 028's
approved scope — see that note below, it's the most important thing to understand before
touching either bugfix.

**Nothing has been committed or pushed as of this handoff being written** — this session ends
with a commit+push of everything (code + both specs), but **no PR** — testing isn't considered
fully done (see "What's NOT proven" below).

## Where every sub-bug stands

| # | Fix implemented | Proof |
|---|---|---|
| **A1** deposit → never bare 305 | ✅ constitution + `create_invoice`'s MCP description | A1-T1 expensive **PASS** |
| **A2** VAT required/defaulted | ✅ `vat_included` required on `create_transaction_account`; unconditional default-included for a payment reference on both tools | A2-T1/A2-T2 billed **PASS**, A1-T1 expensive **PASS**, 10 integration tests **PASS** |
| **A3** real payment date | ✅ `_validate_payment_date`, accepts ISO + DD/MM/YYYY (see gotcha below) | A1-T1 expensive **PASS**, integration tests **PASS** |
| **A3b** bank details/payment method | ✅ `_build_payment_line`, default `bank_transfer`, bit support, `bank_number`/`branch`/`account` | A1-T1 expensive **PASS**, integration tests **PASS** |
| **A4** approval ≠ what gets created | ✅ **done** (2026-08-10, user confirmed) | Explicit VAT call in every approval + verbatim post-creation readback/mismatch-warning — see below |
| **B1** `לאשר` + closed question | ✅ added to whitelist, prompt now ends `אישור — כן/לא?` | Unit tests + visible in every passing billed/expensive approval text |
| **B2** bidi/RTL matching | ✅ `re.search(r"\w+")`, no character-stripping | 12 new unit tests **PASS**, not exercised in billed/expensive |
| **B3** approval states everything | ✅ `_build_pending_approval_details`, appended every turn | B3-T1 billed **PASS**, A1-T1 expensive **PASS** |
| **B4(a)** decorated name still resolves | ✅ `_strip_client_name_decoration` retry | Unit + integration (real sandbox) + B4-T1 billed, all **PASS** |
| **B4(b)** zero-execution detected | ✅ code written | ⚠️ **no test has ever exercised this path** — see below |
| **B4(c)** not-found is an error | ✅ `ClientNotFoundError` | 4 integration tests, real sandbox, **PASS** |
| **B5** response-owed contract | ✅ `AIResponse.__post_init__` + `send_response` guards | 5 unit tests **PASS** |

## ⚠️ Known gap — be honest about this, don't just report "028 is done"

**A4 resolved 2026-08-10 — turned out not to be a gap.** I'd flagged that
`_build_pending_approval_details` shows the requested amount verbatim rather than computing the
grossed-up total when `vat_included=False`. Asked the user directly; they explicitly **don't
want a calculated pre-creation total** — they prefer exactly what's already built: an explicit
VAT call in every approval (already true) plus a verbatim post-creation readback comparing what
Morning actually stored against what was requested (already true, `_read_back_stored_total` +
`_amount_mismatch_warning`, both do a real `get_invoice` fetch, never a calculation). No further
work needed here.

1. ~~**B4(b) (zero-execution detection) has never actually run.**~~ **Resolved 2026-08-10** —
   see the new unit tests in `tests/unit/test_ai_handler_zero_execution_detection.py`.
2. **B2 is unit-proven only.** No billed/expensive test sends a real bidi-marked WhatsApp
   reply end to end — worth at least one real-conversation confirmation given B2's whole origin
   was a real production log line with a literal U+200F character.

## The A3 date-format gotcha — read this before touching payment dates again

`_validate_payment_date` (morning-mcp-app/tools.py) accepts **both** `YYYY-MM-DD` and
`DD/MM/YYYY`, and always returns ISO to Morning. This was **not** the original design — it
started ISO-only, and A1-T1 failed against it because the ledger event stores `txn_date` as
`DD/MM/YYYY` (`_normalize_iso_date` in `ledger_event_manager.py` is misleadingly named — it
converts **from** ISO **to** DD/MM/YYYY, matching `event_date`'s own convention) and nothing
converted between the two. If you touch payment-date handling anywhere in this chain, re-read
this — there are now two representations of "the same date" in this codebase by design, not by
accident, and bugfix-037 (mixed timestamp representation) is the place that eventually needs to
resolve this properly. The user was explicit: *"For now I don't care about the ledger events.
Fix this first"* — meaning the tool-side acceptance of both formats is a deliberate, scoped
patch, not a final answer.

## bugfix-038 was carved out mid-session — read its spec before assuming 028 covers Group B

While verifying A1-T2 (deposit matching an existing type-305 → should close it with a receipt,
not a fresh 320), investigation showed `create_receipt`'s only reference argument is
`original_invoice_id` — an internal Morning GUID the constitution forbids showing the user —
and none of the three "Group B" tools (`create_receipt`/`create_credit_note`/
`close_transaction_account`) carry the referenced document's real data (display number, amount,
actual VAT) anywhere the approval builder can read it. This is a real, separate, three-tool gap
— not a 028 fix. Filed as
[`bugfix-038-group-b-approval-missing-reference-data.md`](bugfix-038-group-b-approval-missing-reference-data.md),
root cause and fix direction discussed live with the user (recorded in the spec), but **not yet
through its own METHODOLOGY §VII approval gate** — treat that as not-started, not
"in-progress-and-safe-to-continue-without-re-checking."

The test itself was **physically moved**, not duplicated: it now lives only in
`apps/denidin-app/tests/expensive/test_group_b_reference_approval_e2e.py`, still red (expected
— the fix isn't built). `test_ledger_event_capture_e2e.py` (028's own suite) has a note where
the test used to be, pointing to where it went, and collects clean at 6 tests, all passing.

**Important design decision already made for 038, in case it gets picked up before this session
returns to it**: the user explicitly rejected a direct HTTP fetch from `ai_handler.py` to the
Morning MCP tunnel to enrich the approval preview (*"the AI needs to do it all"*) — the model
must resolve everything itself via real tool calls, with the resolved data threaded through as
explicit tool arguments so the existing pure-function approval builder can render it. Don't
re-propose the direct-fetch design; it was already considered and turned down.

## Backlog spin-off filed this session

[`specs/backlog/047-whatsapp-interactive-approval-buttons/`](../backlog/047-whatsapp-interactive-approval-buttons/)
— your idea (interactive WhatsApp buttons would make B1/B2 structurally impossible). Draft/P2,
gated behind a "Gate Zero" real button round-trip before any design work. Not touched further
this session.

## What's NOT proven yet, in case "done" gets said too early tomorrow

- The two gaps above (A4 pre-creation total, B4(b) zero-execution) are real open items, not
  polish.
- `dev` is currently rebuilt and running this session's code (both apps), tunnel live, lock
  held by `Ruth`. Nobody has redeployed to `prod`, and nobody should without a separate,
  explicit request per CLAUDE.md.
- No PR yet, by explicit instruction — this bugfix isn't considered finished until the two
  gaps above are resolved (or explicitly deferred with the user's sign-off, the way A1-T2 was).

## Quick orientation for a fresh session

1. Read `bugfix-028-invoicing-and-approval-gate-p0-cluster.md` top to bottom — it's long, but it
   is the actual record of every decision, including several places where an earlier
   implementation/test turned out wrong and was corrected (search for 🔄 for the reversed ones).
2. Read this handoff's two "Known gaps" before doing anything else.
3. Run `pytest tests/unit/ tests/integration/` in both apps first to confirm you're starting
   from the same green baseline this handoff describes, before adding anything.
4. If continuing 028: decide A4's pre-creation gap and B4(b)'s missing test with the user before
   writing code for either.
5. If moving to 038: it needs its own root-cause approval gate (METHODOLOGY §VII step 2) before
   test design — the live discussion isn't a substitute for that gate.
