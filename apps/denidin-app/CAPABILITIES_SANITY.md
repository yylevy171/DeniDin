# Capabilities Sanity — the 10 tests (T1–T10)

Reconstructed from the actual sanctioned run (`_capabilities_sanity_n5_flagoff_20260915_183255.txt`,
run via `scripts/run_sanity_parallel.sh`) plus the substitutions you asked for (T1/T2/T10 swapped
in: bank deposit image, client add, create combo invoice). This is the authoritative list — use
these exact node ids and this exact numbering from now on, nothing else.

**Reset 2026-09-30**: all flag=ON results cleared again — the message-storage refactor (every message stored at the WhatsApp boundary the moment it's sent/received, `src/core/chat_log.py`) touches every turn, so the sweep starts over from T1 order. Old traces deleted.

**Earlier reset 2026-09-16**: statuses below cleared and starting over — the backbone was rebuilt
under the capability-resolution-loop.md redesign (Intent Identification/Planning removed
entirely, replaced by one merged tool-driven loop; stateless `approval_with_yes_no_buttons`
tool; cap_reminders_write now direct-executes). Every prior flag=ON result above is obsolete.

| # | Flow (`flow_*`) | Capabilities it loads | Test node id | flag=OFF | flag=ON |
|---|---|---|---|---|---|
| **T1** | `flow_payment_received_by_bank_slip_image` | `cap_media_analysis` (+ whichever payment flow it routes into) | `tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_image_then_full_fields_correctly_persisted` | ⬜ not yet run | ⬜ not yet run |
| **T2** | `flow_add_client` | `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` | `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_requires_approval` | ⬜ not yet run | ⬜ not yet run |
| **T3** | `flow_create_reminder` | `cap_reminders_write`, `cap_approval_with_buttons` | `tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_godfather_creates_one_time_reminder_button_approval` | ⬜ not yet run | ✅ **PASSES (2026-09-30)** after the store-at-boundary refactor, plus one real fix: a button-tap turn's `send_progress_update` calls were silently dropped, because `Backbone.resolve_button_tap` passed no `progress_callback`. The tap now runs with the same progress sender and sender/chat details as a typed turn, via the shared `_make_progress_callback` in denidin.py. The rerun confirms all 3 tap-turn progress updates are delivered, and approval still comes first: `create_reminder` runs only after the tap. Trace: `debug_traces/T3_PASSED_flag_on_1443_IDT.md`. |
| **T4** | `flow_modify_reminder` | `cap_reminders_read`, `cap_reminders_write`, `cap_approval_with_buttons` | `tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_modify_single_occurrence_of_recurring_reminder` | ⬜ not yet run | ✅ **PASSES (2026-09-30)** after the store-at-boundary refactor, plus one real fix. The first run's final tap turn ended in plain text (no `send_to_user`), and the Backbone sent that text anyway. Now a reply reaches the user only via `send_to_user`/`approval_with_yes_no_buttons`: plain text gets one reminder round (`PLAIN_TEXT_REPLY_REMINDER`), and a second plain-text answer is replaced by the friendly error. The rerun hit exactly this (event 84 plain text, not sent → event 86 `send_to_user`). Approval came first for both writes; the change touched a single occurrence only. Trace: `debug_traces/T4_PASSED_flag_on_1455_IDT.md`. |
| **T5** | `flow_invoicing_query` | `cap_client_read`, `cap_invoicing_read` | `tests/billed/test_denidin_morning_list_invoices_e2e.py::test_godfather_lists_invoices_via_whatsapp` | ⬜ not yet run | ⬜ not yet run |
| **T6** | `flow_user_question` | `cap_ledger_query` (+ `cap_client_read`/`flow_invoicing_query` as needed) | `tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_hours_by_client_last_month` | ⬜ not yet run | ⬜ not yet run |
| **T7** | `flow_issue_invoice_for_payment_due` | `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` | `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp_button_tap` | ⬜ not yet run | ✅ **PASSES (2026-09-30)**, first run after the store-at-boundary refactor and the new outcome-reaction timing rule (`cap_react_to_message.md`). Reactions look right: 🫡 on the request, 👍 on the tap, and ✅ only in the round after `create_invoice` returned (invoice 52567). Open: in the same response as the `create_invoice` call, the model sent the progress update 'החשבונית נוצרה בהצלחה.', which claims success before the result is back. Trace: `debug_traces/T7_PASSED_flag_on_1503_IDT.md`. |
| **T8** | — (ledger capture is post-turn recognition, not a flow/capability) | — | `tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_gilyan_davidian_agreement_text_when_processed_then_captured_per_component` | ⬜ not yet run | ⬜ not yet run |
| **T9** | `flow_fee_agreement_provided_by_user` | `cap_media_analysis`, `cap_client_read` (+ `flow_add_client` if the client doesn't exist) | `tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_multi_component_agreement_image_then_components_correctly_persisted` | ⬜ not yet run | ⬜ not yet run |
| **T10** | `flow_issue_invoice_receipt_combo` | `cap_media_analysis` (optional), `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` | `tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_combo_document_via_whatsapp` | ⬜ not yet run | ✅ **PASSES (2026-09-30)**, first run after the store-at-boundary refactor, no fixes needed. `resolve_client_name` → missing details asked → approval buttons → `create_combo_document` only after the tap (doc 60595); no plain-text rounds. Observation: in the tap turn the model sent a ✅ reaction and a 'completed successfully' planning note in the same response, ordered before the `create_combo_document` MCP call. So the ✅ precedes the actual result. Trace: `debug_traces/T10_PASSED_flag_on_1459_IDT.md`. |

There are no meta-capabilities (no separate intent/planning step; see
capability-resolution-loop.md) — every one of T1–T10 now exercises the single merged
resolution loop directly.

## Status right now
- **All 10 tests reset (2026-09-30)** — sweep restarting after the store-at-boundary refactor.
