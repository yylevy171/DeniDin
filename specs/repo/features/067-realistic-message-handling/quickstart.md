# Quickstart: verifying Feature 067 locally

1. Unit + integration: `cd apps/denidin-app && scripts/run_unit_integration_tests.sh tests/unit/intake tests/integration/test_intake_*.py`
   (never a bare `pytest`).
2. Burst behaviour (integration): feed N webhook bodies for one chat into a producer whose
   Green API client is a local fake; assert one worker, bodies stored individually in order,
   nothing lost, deletion called per body immediately.
3. Hand-back (integration): a fake model client that returns a tool call then `send_to_user`;
   queue a message after the first call; assert the follow-up `input` contains the
   `function_call_output` **and** the timestamped user item.
4. Acceptance A1–A7 (`billed`): `scripts/run_single_test.sh <node_id>` one at a time; A8
   (`expensive`) only with fresh approval. Gate Zero probe first (plan Phase 0).
5. Player unchanged: run the Feature 043 player test; it must pass without a coordinator.
