# Small-bugfixes batch (027, 032, 054, 058, 061) - reproduction tests to run

Branch: `small-bugfixes-027-032-054-058-061`. None of these has been run yet. Each should be RED on
current code. Run each one through `apps/denidin-app/scripts/run_single_test.sh "<node id>"`.

| Bug | Node id |
|-----|---------|
| 027 - client stored with ASCII apostrophe can't get a document | `tests/billed/test_small_bugfixes_027_032_054_058_061_billed.py::test_bugfix_027_client_stored_with_ascii_apostrophe_can_get_a_document` |
| 032 - phone without leading zero rejected | `tests/billed/test_small_bugfixes_027_032_054_058_061_billed.py::test_bugfix_032_phone_without_leading_zero_is_normalised_not_rejected` |
| 054 - startup drops queued messages | `tests/billed/test_small_bugfixes_027_032_054_058_061_billed.py::test_bugfix_054_message_queued_while_bot_was_down_is_answered_after_startup` |
| 058 - error reply not persisted in session | `tests/billed/test_small_bugfixes_027_032_054_058_061_billed.py::test_bugfix_058_error_reply_sent_to_user_is_persisted_in_session` |
| 061 - VAT question asked on a 320 | `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp` |

Notes:
- **061 is flaky by nature** (model ambiguity) - run it several times before concluding it passes.
  Assertion added to the existing test (no new test): the ASK reply must not contain a VAT question.
  The prompt of `tests/billed/test_e2e_ledger_069_morning_create_billed.py::test_us2_morning_create_is_captured_synchronously`
  also had "כולל מע"מ" removed (left in place, but that test is not the 061 reproduction).
- **027** needs the sandbox client `כג'די בלבואה` (ASCII apostrophe, U+0027), added to
  `apps/denidin-app/tests/fixtures/morning_sandbox_clients.json`. Requires the live Morning MCP tunnel.
- **054** starts a local fake Green API server; its background threads are daemons and never stopped.
- **058** builds an app with a deliberately invalid OpenAI key and restores the global app afterward.
