# Contract: Backfill Pipeline Scripts CLI

**Feature**: 061-prod-morning-ledger-backfill
**App location**: `apps/prod-ledger-backfill/` (NEW standalone app, own `requirements.txt`
depending on `apps/morning-mcp-app`'s `denidin_mcp_morning` package as a local path dependency —
see `research.md` R9). Run via `python3` locally, never as a Docker container.

Five separate entry points, one per phase, kept as separate scripts rather than subcommands of one
mega-script — each phase has a genuinely different risk profile (Phase 1/Phase 4 touch real prod;
Phase 2, Phase 3, and Phase 3.5 never do), and separate scripts make that boundary visible at the
shell level, not just in a `--mode` flag.

## `download.py` (Phase 1)

```bash
cd apps/prod-ledger-backfill
python3 download.py --since 2025-01-01 --output-dir ./output/prod_2025_full --creds-file config/backfill_prod_creds.local.json
```

| Flag | Required | Description |
|---|---|---|
| `--since` | Yes (REQ-BACKFILL-001) | ISO date (`YYYY-MM-DD`), Israel-local. No default anywhere in code. |
| `--until` | No (added 2026-08-26, user directive) | ISO date (`YYYY-MM-DD`), Israel-local, inclusive stop date. Omit for the default unbounded-forward sweep (REQ-BACKFILL-001/002's whole point for a real prod run) — exists so a bounded sandbox/experiment pull (e.g. Phase 2's ~20-doc comparison) can be scoped server-side via Morning's own `toDate` search param, instead of over-fetching and filtering locally after the fact (this session's first real Method A run needed exactly that: `--since` alone pulled 97 documents spanning a week when only one day's ~18 were wanted). |
| `--output-dir` | Yes | Local directory for raw downloaded document files. Reused across runs for the same backfill effort (dedup, `research.md` R8) — operator's responsibility to keep stable. |
| `--creds-file` | No | Overrides the default `config/backfill_prod_creds.local.json` path — pointed at `config/backfill_sandbox_creds.local.json` (same four-field shape, `contracts/backfill-creds-file.md`) for Phase 2's experiment instead of prod's real creds. Only one shape is ever parsed — no environment-specific branching in the creds loader. |

**Preconditions checked before any real Morning API call**: `--since` parses as a valid date;
`--until`, if given, also parses as a valid date and is not earlier than `--since` (equal is
allowed — a legitimate single-day window); `--output-dir` exists or can be created and is
writable; the creds file exists and has all four required fields
(`contracts/backfill-creds-file.md`) — script exits non-zero with a clear error otherwise, never
falling back to another credential source.

**Behavior**: constructs `MorningClient` directly from the creds file; paginates
`list_invoices`/`get_invoice` with no artificial cap (`research.md` R3), passing `toDate` (a real,
confirmed-live Morning search param — same key `denidin_mcp_morning/tools.py`'s own
`_map_list_invoices_filters` uses) only when `--until` is given, so the default unbounded-forward
behavior is unchanged byte-for-byte when it's omitted; writes one raw JSON file per document,
keyed on the document's own Morning id (`data-model.md` entity 1), overwriting byte-identically
for a document already present locally (cross-cutting re-run-safety requirement).

## `select_method.py` (Phase 2 — one-time sandbox experiment, not part of the real pipeline)

**REDESIGNED 2026-08-26** (see `research.md` R7): compares Method A vs Method B at the CANONICAL
JSON level (Stage 1+2 only), via sha256 hashes computed once per "run" and stored in a manifest —
never recomputed during comparison. Two sub-commands, on two separate parsers (same pattern as
`validate.py`'s `--approve` dispatch):

```bash
cd apps/prod-ledger-backfill
# Method A's run — pure local code, no live server, runnable now:
python3 select_method.py --generate-a --input-dir ./output/sandbox_sample --output-dir ./method2_a
# Method B's run — needs a real running morning-mcp-app server (its own approval); not yet implemented:
python3 select_method.py --generate-b --input-dir ./output/sandbox_sample --output-dir ./method2_b
# Compare the two already-generated manifests — no recomputation of any kind:
python3 select_method.py --compare --manifest-a ./method2_a/manifest.json --manifest-b ./method2_b/manifest.json --report-out ./method_selection_report.json
```

| Flag | Required | Description |
|---|---|---|
| `--generate-a` / `--generate-b` | One of these two, mutually exclusive | Which method's manifest to generate. |
| `--compare` | For compare mode | Triggers compare mode instead of generate mode. |
| `--input-dir` | For generate mode | ~20 sandbox document files (from a `download.py` run pointed at sandbox creds). |
| `--output-dir` | For generate mode | Where to write canonical JSON files + `manifest.json`. |
| `--manifest-a` / `--manifest-b` | For compare mode | Paths to each method's already-generated `manifest.json`. |
| `--report-out` | For compare mode | Path for the manifest-comparison report (`data-model.md` entity 3). |

**Behavior**: `--generate-a` writes each document's canonical JSON (`format_invoice_json`'s
output, Stage 1+2 only — NOT the final `LedgerEvent`) plus a `manifest.json` mapping the raw
document's own `id` to its sha256 hash. `--generate-b` does the same via a real OpenAI Responses
API call per document, with a real remote `type: "mcp"` tool attached to the live dev/sandbox
`morning-mcp-app` server — **fully implemented (2026-08-26)**: the model is asked to call
`get_invoice_details(output_format="json")` over the real MCP protocol, then relay the exact
canonical JSON string it got back verbatim via a local `relay_canonical_json` function-tool call
(so this actually exercises "does the model botch the passthrough", not just "does the server
return the right bytes"). Needs a new, separate credentials file,
`config/backfill_mcp_creds.local.json` (`contracts/backfill-mcp-creds-file.md`) — fails closed
with `MethodBUnavailableError` (before any OpenAI call) if that file, or the live status file it
points at, isn't present/running. **Actually running it for real still needs a live dev/sandbox
`morning-mcp-app` server up** — its own environment-start approval (root `CLAUDE.md`), separate
from and later than this code existing; the unit tests inject a fake OpenAI client + a fixture
status file, so no real network call happens in the test suite. `--compare` reads two
already-generated manifests and diffs them — no hashing, no re-fetching, no transformation of any
kind happens in this step (`compare_manifests`); writes the report and prints a one-line verdict
(`"IDENTICAL — adopt Method A"` / `"DIFFERS on: <doc ids> — adopt Method B"`). This script is run
once, by a human, to decide how `transform.py` is implemented — it is never invoked by the real
pipeline scripts themselves and never touches prod.

`diff_ledger_events`/`format_verdict` (the ORIGINAL Stage-3-level comparison helpers, comparing
full `LedgerEvent` dicts field-by-field) are UNCHANGED and remain in `select_method.py` — they are
NOT part of this redesign, and are still relied on directly by `validate.py`'s Phase 3.5 sampled
field comparison (a different, already-approved check with nothing to do with Method B or a live
MCP relay).

Both candidate methods live in their own dedicated modules — `apps/prod-ledger-backfill/method_a.py`
(deterministic field mapping, `research.md` R7; `compute_canonical_json()` is Stage 1+2 only, used
by this script's `--generate-a`) and `apps/prod-ledger-backfill/method_b.py` (AI-mediated mapping,
same section — its existing `transform()`/`build_capture_envelope()` are a DIFFERENT, local-only
simulation predating this redesign, not what `--generate-b` will use once implemented) — imported
by both `select_method.py` and `transform.py` (which imports only whichever one the experiment
selected, per `plan.md`'s Project Structure). Neither is a standalone CLI entry point in its own
right.

## `transform.py` (Phase 3)

```bash
cd apps/prod-ledger-backfill
python3 transform.py --input-dir ./output/prod_2025_full --output-dir ./ledger_events/prod_2025_full
```

| Flag | Required | Description |
|---|---|---|
| `--input-dir` | Yes | A directory previously populated by `download.py` — raw document files. |
| `--output-dir` | Yes | Local directory for output `LedgerEvent` files (passed straight through to `LedgerEventManager(storage_dir=...)`). Reused across runs for dedup (cross-cutting requirement / R8). |

**Behavior**: reads every raw document file in `--input-dir` (no live Morning API call — REQ-BACKFILL-003);
maps each into a `LedgerEvent` using whichever method (`research.md` R7) Phase 2 selected; persists
via `LedgerEventManager.add_ledger_event`/`add_ledger_events_from_call`, pointed at `--output-dir` —
dedup and anomaly detection come for free from that existing mechanism, and every anomaly outcome is
retained (not just logged and dropped) so `validate.py` can surface it.

## `validate.py` (Phase 3.5 — required gate before Phase 4, every window)

```bash
cd apps/prod-ledger-backfill
python3 validate.py --raw-dir ./output/prod_2025_full --ledger-dir ./ledger_events/prod_2025_full --report-out ./validation_reports/prod_2025_full.json
```

| Flag | Required | Description |
|---|---|---|
| `--raw-dir` | Yes | The same `--output-dir` used for this window's `download.py` run. |
| `--ledger-dir` | Yes | The same `--output-dir` used for this window's `transform.py` run. |
| `--report-out` | Yes | Path for this window's validation report (`data-model.md` entity 4). Fresh per window/run — never overwrites a prior window's report. |
| `--sample-size` | No | How many documents to include in the field-level spot-check (default: a small fixed number, e.g. 10-20% of the window or a flat count — exact default decided at implementation time). |

**Behavior** (REQ-BACKFILL-010): reads `--raw-dir` and `--ledger-dir` only (no live Morning API
call — same discipline as `transform.py`); computes the document-count reconciliation; collects
every anomaly `transform.py`'s run flagged; samples documents for a field-level raw-vs-transformed
comparison; writes the report with an empty/unsigned sign-off field. **Never writes or modifies any
`LedgerEvent` file** — strictly read-only, a report generator.

Sign-off itself (marking the report as reviewed and approved) is a separate, explicit human action
— editing the report file, or a small `python3 validate.py --approve --report-in <path>` mode,
decided at implementation time — never automatic, never inferred from the report simply existing.

## `load.py` (Phase 4) — CLI surface TBD

Deliberately not specified yet (`research.md` R10) — designed once Phases 1-3.5 are proven correct
against real prod output. Will follow the same "own script, real prod is its own approval gate
every run" shape as `download.py`, PLUS a hard check that Phase 3.5's report for the exact window
being loaded exists and is signed off (REQ-BACKFILL-010) before writing anything.

## Console output (REQ-BACKFILL-008 — no WhatsApp side effects, ever, from any script)

Each script prints a per-document/per-file progress line and a final summary (counts: seen, newly
written, skipped-as-duplicate, anomalies) — mirroring this project's existing audit-log discipline
(`utils/whatsapp_audit_log.py`, `apps/morning-mcp-app/audit.py`) even though these are standalone
scripts, not running services.

## Exit codes

Following CONSTITUTION.md's exit-code convention: `0` on a completed run (even with zero new
documents — a valid, successful outcome), non-zero on any precondition failure or unrecoverable
error during the run. `load.py` additionally exits non-zero without writing anything if Phase 3.5's
sign-off for the target window is missing or absent.
