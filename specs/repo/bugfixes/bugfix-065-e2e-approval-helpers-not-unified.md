# bugfix-065: document-creation approval E2E helpers are not unified

**Status**: Open
**Discovered**: 2026-09-27, while running the bugfix-061 (VAT prompt conflict) reproduction
tests — `tests/billed/test_standalone_receipt_billed.py::test_godfather_records_a_deposit_as_a_standalone_receipt`
stalled on a client-identity clarifying question because its shared helper,
`_send_turn_and_approve_receipt`, only knows how to answer a missing-`payment_date` question and
blindly sends `"היום"` regardless of what was actually asked.

## Root cause

There is no single, unified helper for driving a document-creation approval turn (ASK → possibly
one or more clarifying turns → APPROVE) across `tests/billed/`. Despite substantial prior effort
specifically unifying these helpers, the result is inconsistent per tool/scenario — some use a
shared helper, some use a *different* shared helper with a narrower purpose, and several hand-roll
their own inline multi-turn loop directly in the test body:

| Tool / scenario | What it actually uses |
|---|---|
| `create_invoice` (305), VAT stated | `_send_turn_and_approve` (plain 2-turn) |
| `create_invoice` (305), VAT **not** stated | hand-rolled inline (`test_godfather_creates_invoice_via_whatsapp_button_tap`) |
| `create_transaction_account` (300), VAT stated | `_send_turn_and_approve` |
| `create_transaction_account` (300), VAT **not** stated | hand-rolled inline (`test_godfather_creates_transaction_account_via_whatsapp`: ASK → "כן" for VAT → "כן" approve, written by hand) |
| `create_combo_document` standalone, date/desc stated | `_send_turn_and_approve` |
| `create_combo_document` standalone, date/desc **not** stated | hand-rolled inline (`test_godfather_creates_combo_document_via_whatsapp`: 4-turn ASK→DESCRIBE→DATE→APPROVE, written by hand) |
| `create_credit_note` (330 by-ref) | `_send_turn_and_approve` |
| `create_receipt` (400, standalone or by-ref) | `_send_turn_and_approve_receipt` — its own dedicated helper, answers only a missing-date question |
| `create_combo_document_as_reference` (320 by-ref), stated | `_send_turn_and_approve_capturing_approval` |
| `create_combo_document_as_reference` (320 by-ref), unstated (`test_multi_turn_clarification_uses_the_real_internal_id_not_the_display_number`) | hand-rolled inline (up to 4 turns, written by hand) |
| Group B reference tools generally (`test_group_b_reference_approval_billed.py`) | `_send_turn_and_approve_capturing_approval` |

`_send_turn_and_approve_capturing_approval` is already documented (in its own docstring) as
generalizing `_send_turn_and_approve_receipt` "to any Group A/B tool" — it is the closest thing to
a real unified helper that exists today. But it has two problems of its own:

1. **Not consistently adopted** — 4+ tests across invoice / transaction-account / combo don't call
   it and instead hand-roll the same ask → clarify → approve loop inline, duplicating logic that
   should live in one place.
2. **Same defect class as `_send_turn_and_approve_receipt`** — it sends one fixed, hardcoded
   `"היום"` for its one allowed clarifying turn, regardless of what was actually asked. It has not
   yet been observed misfiring on a VAT or client-identity question only because none of its
   current callers have hit one — the defect is latent, not absent.

## Impact

A test whose prompt happens to produce an unexpected clarifying-question TYPE (not the one the
helper it's using was built to answer) silently stalls into a wrong or nonsensical multi-turn
exchange and fails with a confusing symptom far from the actual cause (e.g.
`test_godfather_records_a_deposit_as_a_standalone_receipt` failed with "model never invoked
create_receipt" — the real cause was an unrelated client-name-ambiguity question the helper had no
way to recognize or answer, itself caused by a separate one-off prompt-phrasing bug in that same
test - see bugfix-061's `bugfix-061-vat-test-categorization.md` for that trace).

## Proposed direction (not implemented — explicitly deferred)

One single helper, used by every document-creation approval test regardless of tool, that
inspects what it is actually being asked at each turn and answers it correctly (payment date, VAT
inclusion, client identity, etc.) — or refuses to guess and fails loudly with a clear message when
it doesn't recognize the question — replacing `_send_turn_and_approve_receipt`,
`_send_turn_and_approve_capturing_approval`, and every hand-rolled inline loop across
`tests/billed/`.

**Explicitly NOT being fixed as part of the bugfix-061 batch** (user instruction, 2026-09-27):
this is real, sizeable follow-on work of its own, opened here to track separately rather than
folded into an unrelated fix.
