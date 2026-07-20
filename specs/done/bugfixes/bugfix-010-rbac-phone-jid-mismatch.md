# Bugfix Spec: RBAC Phone/JID Format Mismatch

## Bug ID
bugfix-010-rbac-phone-jid-mismatch

## Title
Real godfather/admin WhatsApp users silently resolve to CLIENT role

## Status
Fixed - merged to master

## Date Opened
2026-07-20

## Reported By
yylevy171 (found via manual dev-environment testing during 019-env-separation rollout)

## Affected Area
- `apps/denidin-app/src/managers/user_manager.py` (`UserManager.get_user()`)
- RBAC role resolution for all real WhatsApp traffic (both dev and prod)

## Description
Real Green API webhooks populate the sender as a WhatsApp JID (e.g.
`"972522968679@c.us"`), while `godfather_phone`/`admin_phones`/`blocked_phones`
are configured as bare digit strings (e.g. `"972522968679"`). `UserManager.get_user()`
did an exact string comparison between the two, so real godfather/admin users
silently resolved to `CLIENT` — denying memory/RBAC privileges and Morning MCP
tool attachment — despite correct configuration. The rejection was silent: the
first line of `AIHandler._build_morning_mcp_tools()` (`role not in
MORNING_MCP_AUTHORIZED_ROLES: return None`) logs nothing, unlike its two sibling
rejection branches (server unavailable / auth token missing), which both log a
warning.

## Steps to Reproduce
1. Configure `godfather_phone` as a bare digit string (e.g. `"972522968679"`).
2. Send a real WhatsApp message from that number.
3. Observe: role resolves to CLIENT (visible via absent `"Attaching Morning MCP
   tools"` log line, or via reduced token limit/memory access) despite the
   number matching `godfather_phone`.

## Expected Behavior
A real WhatsApp sender matching a configured `godfather_phone`/`admin_phones`/
`blocked_phones` entry (with or without the WhatsApp JID suffix) resolves to
the correct role.

## Actual Behavior
Real senders (JID-suffixed) never matched bare-digit config values; always
fell through to the CLIENT default.

## Impact
- Every real production godfather/admin interaction was silently downgraded to
  CLIENT — no memory access beyond client scope, no Morning MCP tool (no
  invoicing capability at all, despite the whole feature being built and
  believed working).
- Went undetected because the unit test suite (`test_rbac.py`,
  `test_ai_handler_rbac.py`, `test_user_manager.py`) hand-constructs
  `WhatsAppMessage`/`UserManager` fixtures with bare-digit `sender_id`/`user_phone`
  values matching bare-digit config values — never exercising the real JID
  format produced by `WhatsAppMessage.from_notification()` (itself correctly
  tested, in isolation, by `test_message.py:96`). No test connected the two.

## Root Cause Analysis
`UserManager.get_user()` (and its callers in `AIHandler.create_request()`/
`get_response()`) compared the raw `phone` argument against `godfather_phone`/
`admin_phones`/`blocked_phones` with `==`/`in`, with no normalization. The
`phone` argument's real-world value (`message.sender_id`, or `sender=`/
`user_phone=` derived from it) always carries a WhatsApp JID suffix in
production; the config values never do.

## Evidence
- Found live: dev-environment WhatsApp test on 2026-07-20 — an invoicing
  query from the configured godfather's real number produced a generic
  deflection instead of invoking the Morning MCP tool; no
  `"Attaching Morning MCP tools"` log line appeared.
- `apps/denidin-app/tests/unit/test_message.py:96` pins `sender_id` as JID-suffixed
  (`'1234567890@c.us'`) — confirms the real format.
- `apps/denidin-app/tests/unit/test_rbac.py::test_godfather_user_flow` (before
  fix) hardcoded a bare-digit `sender_id` and additionally passed a test-only
  `user_phone=` override to `create_request()`/`get_response()` that
  `denidin.py`'s real webhook handler never passes — double-insulating the
  test from the real code path.

## Acceptance Criteria
- [x] The bug is reproducible in a test.
- [x] A failing test is added/revised to cover the scenario
      (`test_rbac.py::test_godfather_user_flow`, revised to use a realistic
      JID-suffixed sender and drop the unrealistic `user_phone=` override).
- [x] The root cause is identified and documented (this file).
- [x] The bug is fixed and the test passes.
- [x] No regression in related RBAC/media/session functionality (full unit
      suite: 497 passed).
- [x] Verified live against real WhatsApp traffic in the dev environment
      post-fix: GODFATHER role resolved correctly, Morning MCP tool attached
      and invoked (`get_financial_summary` against Morning sandbox).

## Fix
`apps/denidin-app/src/managers/user_manager.py`: added `_normalize_phone()`
(strips everything from `@` onward, then all non-digit characters) and applied
it to both the incoming `phone` and the configured `godfather_phone`/
`admin_phones`/`blocked_phones` before comparison. `WhatsAppMessage.sender_id`'s
JID format is untouched (pinned test contract).

## References
- `.github/CONSTITUTION.md` §V (integration-test philosophy — this is exactly
  the class of gap it targets: two independently-correct-for-their-own-assumptions
  test suites with no test at the seam connecting them)
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
- `specs/done/019-env-separation/` (the feature whose manual testing surfaced this bug)

## Follow-ups (not in this fix's scope, noted for future consideration)
- `AIHandler._build_morning_mcp_tools()`'s role-check rejection branch logs
  nothing, unlike its two sibling branches — consider adding a debug log there
  for consistency/debuggability.
- Consider whether other test files with the same hand-constructed
  bare-digit-`sender_id` pattern (`test_ai_handler_rbac.py`, `test_user_manager.py`)
  warrant the same reality-check treatment.
