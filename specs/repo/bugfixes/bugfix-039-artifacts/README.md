# bugfix-039 round 3 — client-resolution algorithm prototype

Standalone, in-memory prototype of `resolve_client_by_name` (the real implementation lives in
`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`), built and unit-tested *before* touching
real code, per explicit user instruction. Not part of any app, not imported by anything — kept here
purely as the reference the real implementation was checked against, and as a fast (no real API
calls) way to explore the algorithm's behavior on a new scenario before trying it live.

Full story: see "Session Handoff (2026-08-11, round 3)" in
`specs/done/v0.4.1/bugfix-039-list-invoices-skips-client-resolution.md`.

## Files

- `client_resolution_prototype.py` — the algorithm: `Client`, `FakeMorning`, `resolve_client`.
- `test_client_resolution_prototype.py` — 25 adversarial test cases.
- `show_test_table.py` — prints a full Hebrew scenario table (real production/regression names +
  300 realistic random-noise clients drawn from the app's own `hebrew_first_names.txt`/
  `hebrew_family_names.txt` pool) showing stored clients / query / result / what each row tests.

## Running

Any Python 3 with pytest works (e.g. `apps/morning-mcp-app`'s own venv — no dependency beyond the
stdlib and pytest):

```bash
cd apps/morning-mcp-app && source venv/bin/activate
cd ../../specs/done/v0.4.1/bugfix-039-artifacts
python3 -m pytest test_client_resolution_prototype.py -v
python3 show_test_table.py
```

## Keeping this in sync with the real implementation

If `_grow_word`/`resolve_client_by_name` change in `tools.py`, mirror the change here too (or at
least re-verify this prototype still models the same behavior) — this file existing and passing is
not itself proof the real code is correct; it's proof the *design* is sound. The real code is only
proven by the real sandbox integration tests in `apps/morning-mcp-app/tests/integration/`.
