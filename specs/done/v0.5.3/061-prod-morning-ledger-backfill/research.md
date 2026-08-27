# Phase 0 Research: Prod Morning Ledger Backfill

**Feature**: 061-prod-morning-ledger-backfill
**Purpose**: Resolve every technical unknown needed to design the five-phase backfill pipeline
before Phase 1 of design work (`data-model.md`/`contracts/`/`quickstart.md`) — no unverified
assumptions, per CONSTITUTION.md's "no unverified third-party assumptions" discipline.

**Note on "Phase" naming**: this document's own `R1`, `R2`, ... labels are research-finding
numbers, unrelated to the pipeline's own `Phase 1`-`Phase 4` numbering (`spec.md`'s Terminology
Glossary) — e.g. `R3` discusses `Phase 1`, not "phase 3."

**Revised 2026-08-25 (round 4)** — grounded in a fresh, real, line-numbered read of
`apps/morning-mcp-app`'s actual source; terminology updated from the original "Pass 1/2/3"
numbering to the current `spec.md`/`user-stories.md` "Phase 1 → 2 → 3 → 3.5 → 4" numbering
(Phase 2 — the method-selection experiment — and Phase 3.5 — validation — didn't exist as
distinct phases in the original pass; see round 3 and round 4 of `spec.md`'s Clarifications).

---

## R1: `MorningClient` — real constructor and the raw methods Phase 1 needs

**Finding**: `apps/morning-mcp-app/src/denidin_mcp_morning/morning_client.py`:

```python
class MorningClient:
    def __init__(self, api_key_id: str, api_key_secret: str, auth_url: str,
                 base_url: str = "https://api.greeninvoice.co.il/api/v1",
                 refresh_before_seconds: int = 300, retries: int = 3):
```

Internally constructs a `MorningAuth(api_key_id, api_key_secret, auth_url, ...)` for token
management, plus a `requests.Session` with urllib3 `Retry` wired to `retries`. Relevant raw
methods for Phase 1:

- **`list_invoices(self, params: dict = None) -> List[dict]`** — `POST /documents/search` against
  `base_url`. Returns Morning's raw response (a dict with `items`/`data` and pagination fields
  `total`/`page`/`pages` — see R3 below — or, for some param shapes, a bare list).
- **`get_invoice(self, invoice_id: str) -> dict`** — `GET /documents/{id}`, full raw document.

Both are plain, un-decorated HTTP calls — no result cap, no truncation, no token-budget logic of
any kind. This is the surface Phase 1 uses directly.

## R2: `MorningAuth` — real OAuth2 contract, and why `auth_url` cannot be derived

**Finding**: `apps/morning-mcp-app/src/denidin_mcp_morning/auth.py` — `MorningAuth.__init__
(api_key_id, api_key_secret, auth_url, ...)`. Token acquisition:
`POST {auth_url}/idp/v1/oauth/token` with body `{"grant_type": "client_credentials", "client_id":
api_key_id, "client_secret": api_key_secret}`; response shape `{"accessToken": ..., "tokenType":
"Bearer", "expiresAt": <unix ts>}`. Tokens are cached and refreshed `refresh_before_seconds`
(default 300s) before expiry.

`auth_url` is a genuinely different host than `base_url` (confirmed against
`apps/morning-mcp-app/config/config.example.json`: production auth is
`https://api.greeninvoice.co.il`, while sandbox uses `https://api.sandbox.morning.dev` for both
auth and API) — it cannot be guessed or derived from `base_url`, so both must be present in
whatever credentials file Phase 1 loads (see R6/`contracts/backfill-creds-file.md`).

## R3: Why Phase 1 must NOT use `tools.py`'s `list_invoices` wrapper

**Finding**: `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`:

- `_LIST_INVOICES_MAX_ITEMS = 100` (line 60) — inside the wrapper `list_invoices(client,
  status=None, from_date=None, to_date=None, client_name=None, document_display_number=None,
  token_budget=_LIST_INVOICES_TOKEN_BUDGET, name_resolved=False, output_format="text",
  include_full_details=False) -> str` (line 883): if the real total exceeds 100, the function
  returns `format_too_many_invoices_message(total)` — a **refusal string**, not any documents at
  all.
- Even with `output_format="json"` (which bypasses the token-budget *truncation*, per Feature
  025's Phase 9a — "a reconciliation consumer needs every match"), the 100-item **total cap**
  still applies and still produces a refusal above that count.
- Both limits exist specifically to keep a bounded conversational WhatsApp reply short — neither
  is appropriate for a historical backfill, which routinely needs to enumerate far more than 100
  documents across a wide date range.

**Conclusion (confirms `user-stories.md` Phase 1 and `spec.md` REQ-BACKFILL-002)**: Phase 1 must
call `MorningClient.list_invoices`/`get_invoice` directly and implement its **own** pagination loop
— following Morning's own `page`/`pages`/`total` fields off the raw `/documents/search` response
(see `tools.py`'s `_extract_items`, line ~800, for the exact response-shape handling: a dict with
`items`/`data` keys, or a bare list) — with no artificial upper bound on total document count.

## R4: `_map_list_invoices_filters` — reusable as a reference for building `list_invoices` params

**Finding**: `tools.py`'s `_map_list_invoices_filters(from_date, to_date, client_name,
document_display_number)` maps friendly filter names onto Morning's real `/documents/search`
params (`fromDate`/`toDate`/`clientName`/`number`), confirmed correct against the sandbox by
`apps/morning-mcp-app`'s existing integration test suite. Phase 1 does not call this function
directly (it's private to `tools.py`, and Phase 1 deliberately avoids that module's higher-level
wrappers per R3) but reimplements the equivalent minimal param construction (`fromDate` only, no
client/number filter — Phase 1 wants *everything* from the start date forward) directly against
`MorningClient.list_invoices`, using this as a confirmed-correct reference for the param names.

## R5: `LedgerEventManager` reuse for Phase 3's output — still valid, still not "live"

**Finding** (re-confirmed here since it remains load-bearing for the corrected design):
`LedgerEventManager.__init__(self, storage_dir: str)`
(`apps/denidin-app/src/managers/ledger_event_manager.py:385`) takes a plain string path, fully
decoupled from `AppConfiguration`, `AIHandler`, or any running service. Its dedup cache
(`_ensure_accounting_document_cache` → `scan_accounting_documents`, lines 438-495) is built by
scanning `storage_dir` for `source_type="חשבונית"` files, lazily, once per process — pure local
file-based library code. `add_ledger_event(...)` (line 576) and `add_ledger_events_from_call(
session_id, call_arguments, message_id, message_timestamp)` (line 932) are the two write paths;
the latter accepts a `capture_ledger_event`-shaped `call_arguments` dict, matching what Method B
(if selected) would produce.

**This reuse is compatible with "don't reuse anything live"**: importing and constructing
`LedgerEventManager` directly, pointed at a local `storage_dir`, does not start, call, or depend on
any running container/service — it is ordinary library code, the same way importing `pathlib` is.
Phase 3 reuses it for output persistence and dedup only.

**Also load-bearing for Phase 3.5**: `add_ledger_event`'s existing tri-state (new/duplicate/
anomaly) return is exactly what Phase 3.5's "surface every anomaly `LedgerEventManager` flagged
during Phase 3" requirement (REQ-BACKFILL-010) reads — Phase 3.5 needs no new anomaly-detection
logic of its own, only a report step that collects what Phase 3's own run already classified.

## R6: Credentials Phase 1 actually needs (raw Green Invoice, not an MCP token)

**Finding**: since Phase 1 talks to Morning directly via `MorningClient`, the credentials it needs
are exactly `MorningClient.__init__`'s own required arguments — `api_key_id`, `api_key_secret`,
`auth_url`, and `base_url` (real prod values; `base_url` defaults sensibly but is still supplied
explicitly for clarity/auditability) — matching `apps/morning-mcp-app`'s own
`config.prod.json` shape (`api_key_id`/`api_key_secret`/`api_url`/`auth_url` — confirmed against
`apps/morning-mcp-app/config/config.example.json`), never an MCP bearer token (that field secures
denidin-app's HTTP call *to* `morning-mcp-app`, which Phase 1 never makes). This corrects both the
spec's original round-2 guess and an earlier (also wrong) "correction" in this planning pass's own
history to an MCP-token shape — see `contracts/backfill-creds-file.md`.

## R7: The Phase 2 method-selection experiment — design

**Finding/design**: no code currently implements either candidate method; both are new.

- **Method A (deterministic)**: **corrected during implementation (2026-08-25)** — an earlier
  draft of this section described a hand-rolled field mapping using field names
  (`accounting_document_type`/`accounting_document_client_name`/`accounting_document_creation_timestamp`)
  that turned out not to exist anywhere in the real `LedgerEvent` schema (confirmed by reading
  `apps/denidin-app/src/managers/ledger_event_manager.py`'s `_expand_accounting_document_json`
  directly — zero grep matches for any of those three names). No hand-rolled mapping is written at
  all: Morning's raw document JSON (from Phase 1's local files) is parsed via
  `denidin_mcp_morning.models.Invoice.model_validate()` (apps/morning-mcp-app), passed through
  `denidin_mcp_morning.formatters.format_invoice_json()` to build the same machine-readable JSON
  Feature 025's live pipeline already produces, then piped directly into
  `ledger_event_manager._expand_accounting_document_json()` (apps/denidin-app, reached via
  `_ledger_event_manager_loader.py` — see R5) — the exact same code-derived field expansion
  `LedgerEventManager.add_ledger_event` itself already depends on. The REAL field list this
  produces: `event_subtype` (Morning's own Hebrew type label, e.g. "חשבונית מס" — carries the
  document-type info that a separate `accounting_document_type` field does not exist to hold),
  `accounting_document_display_number`, `accounting_document_status`/`_status_code`/`_status_label`,
  `accounting_document_creation_date` (not `_creation_timestamp`), `accounting_document_payment_method`,
  `client_name` (not `accounting_document_client_name`), `description`, `amount`, `txn_date`,
  `bank_number`/`_branch`/`_account`, `vat_status`. Plain Python, no network call beyond what Phase
  1 already made, and no new mapping logic — just glue between two apps' existing, already-tested
  code.
**REDESIGNED (2026-08-26, direct user direction) — comparison level and mechanism both changed**:

The original design (immediately above/superseded) compared Method A vs Method B at the FINAL
`LedgerEvent` level (Stage 3 included), field-by-field, recomputed live inside the comparison
step. Two problems, per the user directly: (1) comparing at the Stage-3 level conflates two
separate questions — "does Stage1+2's canonical JSON survive a live AI relay intact?" vs "does
Stage 3's own derivation logic work?" — user's framing: *"The goal is to compare the raw inputs
(assuming AI doesn't botch the passthrough, which is also sort of tested in this setup)."*
(2) recomputing both methods' output live, inside the comparison tool itself, isn't how a real
"run" should work — user's framing: *"no computing on the fly during the run — a run... creates
the data and computes the hash for each json string and stores it. The validation just compares
total no of items and then the individual hashes."*

- **Method A (unchanged fetch, narrowed scope)**: `method_a.compute_canonical_json(raw_document)`
  — Stage 1+2 ONLY (`Invoice.model_validate` + `format_invoice_json`), stopping short of Stage 3.
  `generate_method_a_manifest(input_dir, output_dir)` runs this over every raw document file in
  `input_dir` (Phase 1's own sandbox output), writes each canonical JSON to `output_dir`, and
  records its sha256 in `output_dir/manifest.json`. Pure local code — no live server, no AI,
  runnable now.
- **Method B (redefined — a REAL live-MCP relay, not a local AI simulation)**: the original design
  had our OWN code compute the canonical JSON (via `format_invoice_json`) and merely ASKED an AI
  to relay it verbatim through a local, fake `type: "function"` tool — no live server was ever
  involved. The user's redesign requires a genuinely live round trip: a real OpenAI Responses API
  call with a REAL remote `type: "mcp"` tool attached (the actual running `morning-mcp-app`
  dev/sandbox server, over its real ngrok tunnel), asking the model to fetch a specific document
  via the real MCP protocol (`get_invoice_details`/`list_invoices`, `output_format="json"`) and
  store whatever canonical JSON the tool call actually returns — this is what "assuming AI doesn't
  botch the passthrough, which is also sort of tested in this setup" is checking: does the model
  relay the server's own JSON faithfully across a REAL round trip, not a simulated one.
  `select_method.generate_method_b_manifest(...)` is the corresponding function — **fully
  implemented 2026-08-26**: discovers the live server URL by independently reimplementing (no
  import) `MorningMcpLocator`'s shared-status-file-reading pattern
  (`select_method._discover_mcp_server_url`, reading a NEW, separate, gitignored
  `config/backfill_mcp_creds.local.json` — `contracts/backfill-mcp-creds-file.md`); attaches a
  real `type: "mcp"` tool independently reimplementing (no import) `ai_handler.py`'s tool shape,
  scoped to `get_invoice_details` only in the "never-approval" bucket
  (`select_method._build_mcp_tool`); asks the model to fetch the document and relay the exact
  canonical JSON string it got back via a local `relay_canonical_json` function-tool call (not by
  reading the MCP call's own output directly — that would skip testing whether the model itself
  botches the passthrough, the actual point of this experiment). Fails closed with
  `MethodBUnavailableError` before any OpenAI call if the creds/status-file prerequisites aren't
  met. Actually **running** it for real still needs the dev/sandbox `morning-mcp-app` server
  actually up — its own environment-start decision requiring explicit approval every time (root
  CLAUDE.md), separate from and later than writing this code. Unit tests inject a fake OpenAI
  client + a fixture status file (`tests/unit/test_select_method_manifest.py`), so no real network
  call happens in the suite.
- **Comparison mechanism — hashes, not field diffing, and pre-computed, not live**: each method's
  "run" computes a sha256 per document exactly once (as part of generating its own manifest) and
  stores it. `select_method.compare_manifests(manifest_a, manifest_b)` does nothing but diff two
  already-computed manifests — no hashing, no re-fetching, no transformation of any kind happens
  in the comparison step itself. Keyed on the raw document's own `id` (both methods iterate the
  SAME document ids directly — no `LedgerEvent`/`accounting_document_display_number` involved
  anywhere in this comparison, unlike Phase 3.5's join key).
- **Selection procedure (mechanically unchanged)**: download ~20 known documents from the Morning
  **sandbox** (reusing this repo's existing sandbox credentials — the same ones
  `apps/morning-mcp-app/config/config.test.json` and its integration/billed test suite already
  use; no new sandbox credentials needed) via Phase 1's own script pointed at sandbox instead of
  prod. Generate both methods' manifests over those same ~20 documents, then compare. Identical on
  every document → adopt Method A for Phase 3's real implementation (no OpenAI dependency, no
  per-document API cost, deterministic). Any hash differs → adopt Method B (or investigate the
  specific document the mismatch names, per the user's framing: *"If a mismatch is encountered -
  an anomaly is reported, and we investigate"*).
- **This experiment never touches prod** — entirely a sandbox-only, one-time design decision, not
  a per-run gate. Once Phase 3 is built using the selected method, later real prod runs (Phase 1
  into Phase 3) don't re-run this comparison. `diff_ledger_events`/`format_verdict` (the original
  Stage-3-level comparison helpers) are UNCHANGED and NOT part of this redesign — they're still
  relied on directly by Phase 3.5's `validate.py` (a different, already-approved check: does the
  real persisted `LedgerEvent` match what Method A alone would independently derive from the same
  raw document — nothing to do with Method B or a live MCP relay at all).

**Fidelity trace against the REAL live server code (2026-08-26, prompted by direct user scrutiny —
"how do you GUARANTEE data in the mcp flow is identical to raw+your manipulations?")**: read
`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`'s actual `get_invoice_details` and
`list_invoices(include_full_details=True)` bodies line by line (not assumed). Confirmed:
- `get_invoice_details`: `response = client.get_invoice(id); invoice = Invoice.model_validate(response);
  return format_invoice_json(invoice)` — the exact same two function calls, same order, same
  module, that `method_a.build_capture_envelope()` makes. Not "equivalent code" — literally the
  same imported functions.
- `list_invoices(include_full_details=True)` (confirmed via `accounting_reconciliation_service.py`'s
  real prompt text to be what the live sweep actually calls, not `get_invoice_details`): its
  per-document fan-out is `Invoice.model_validate(client.get_invoice(inv.id))` — identical call.
  `format_invoice_list_json` wraps `format_invoice_json(inv)` per document unchanged — no
  per-document reshaping at the list level either.
- **Real gap found by this trace, unrelated to JSON-shaping**: production's fan-out silently falls
  back to shallower search-page data on a `get_invoice()` failure and keeps going
  ("a failure on one document falls back to its search entry rather than losing the sweep" —
  tools.py's own comment); `download.py`'s `download_all_documents()` had no error handling at all
  for this (a single failure would crash the whole Phase 1 run). Fixed same day, human decision:
  fail loudly instead (`DocumentDownloadError`, naming the failed document) rather than mirror
  production's silent degradation — a backfill's whole point is fidelity, so persisting a document
  with less data than a full fetch would have given, silently, is worse than stopping; re-running
  is safe via the existing overwrite-by-id dedup.
- Minor, unverified, low-risk: `download.py`'s first search-page call explicitly sends `page=1`;
  production's first call omits the `page` key entirely (relies on Morning's own default).
  Presumed harmless but not empirically confirmed against the live API — noted, not yet a decided
  action.

**REAL VERDICT (2026-08-26, T031, real sandbox run against 18 real documents from 2026-08-20) —
Method A adopted, Method B rejected. Decided.**

Ran `generate_method_a_manifest`/`generate_method_b_manifest` for real against all 18 documents in
`output/sandbox_20aug_bounded` (via `--until`, R-above). Method A: all 18 succeeded, pure local
code, no incident. Method B (`_METHOD_B_MODEL = "gpt-5.6-luna"`, the already-fixed model + the
`_response_actually_called_mcp_tool` safety net + `_canonicalize_for_hashing`, per the two prior
fix rounds documented above) hit real problems on the full run, none hypothetical:

- **1 of 18 crashed the run outright**: the model's relayed JSON string for one document came back
  truncated by exactly one character (997 expected, 996 delivered) — `generate_method_b_manifest`'s
  loop has no per-document try/except, so this aborted the whole run with `manifest.json` never
  written (individual per-document files for the 13 already-processed documents were still on disk,
  since those are written inside the loop before the crash). A single diagnostic re-fetch of just
  that one document (one extra real call) came back complete and byte-identical to Method A —
  consistent with a one-off transient clip, not a reproducible defect in the prompt/tool setup.
- **2 of the 13 documents that DID complete had real content corruption**, discovered by a plain
  local diff of Method A's vs Method B's output files (no new calls needed) — not formatting or
  escaping differences, genuine character-level transcription errors, despite the prompt explicitly
  demanding character-for-character verbatim relay:
  - `519ad9f5-7a44-47b9-a049-ec55a170bd19` — `client_name`: Method A `אחזיה נח׳לה` vs Method B
    `אחזיה נחלה` — the model **dropped the geresh character** (`׳`, U+05F3, Hebrew punctuation),
    shifting the rest of the string.
  - `72b9b07c-adb0-4bcf-9069-7dd3486f0253` — `description` (and the matching
    `line_items[0].description`): Method A `ייעוץ` (ayin, `ע`) vs Method B `ייץוץ` (final-tsadi,
    `ץ`) — the model **substituted a visually-similar Hebrew letter** for the correct one.
- Net: of 13 documents that completed, 11 were byte-identical and 2 were silently corrupted; plus 1
  outright failure that would have needed a retry. A ~15%+ per-document fidelity error rate on
  Hebrew text, on top of an outright truncation failure, despite every mechanical safeguard already
  in place (real model matching production, a real anti-fabrication check, transport-escaping
  normalized away before comparison) — this is the LLM relay step itself being unreliable at a
  simple verbatim copy, not a fixable configuration gap.
- The remaining 4 of 18 documents were never attempted (the run aborted before reaching them in
  sorted order) — the finding above was already decisive enough that finishing the full 18 for
  completeness was explicitly declined by the user ("I'm fine with method A, we can ditch method
  B").
- **Decision (human, 2026-08-26): Method A is adopted for Phase 3's real implementation. Method B
  is rejected and not pursued further** — no per-document API cost, no live server dependency, no
  AI-relay fidelity risk, and it already produces byte-identical output to what a live MCP relay
  is supposed to deliver (when it doesn't corrupt or truncate the data). `transform.py`'s existing
  default (`_DEFAULT_BUILD_ENVELOPE_FN = method_a.build_capture_envelope`) needed no code change —
  it was already wired to Method A pending exactly this verdict (T016). `method_b.py`/
  `select_method.py`'s Method B code is left in place as-is (already implemented, tested, and now
  a documented real finding) — not deleted; simply not used by the real pipeline.

## R8: Cross-run dedup — still free, via `LedgerEventManager`'s existing guard

**Finding**: as long as Phase 3's local output directory is a stable, persistent path reused across
separate invocations (not a fresh directory each run), `LedgerEventManager`'s existing tri-state
guard, keyed on `accounting_document_display_number` + creation timestamp, rejects already-captured
documents on a second run with zero new code. Phase 1's own re-run safety (not double-downloading a
document already present as a local raw file) is new, simple logic Phase 1 must implement itself
(e.g. overwrite-if-present keyed on the document's own id as the local filename) —
`LedgerEventManager` has no bearing on Phase 1's half of this.

## R9: New app location — `apps/prod-ledger-backfill/`, importing `apps/morning-mcp-app` directly

**Finding/decision**: root `CLAUDE.md`'s "no cross-app import" rule is scoped specifically to
`denidin-app` ↔ `morning-mcp-app` never importing each other's code (they communicate only over
the real MCP HTTP tunnel). A **new**, third, standalone app depending on `morning-mcp-app`'s
`denidin_mcp_morning` package is not the relationship that rule forbids — `morning-mcp-app`
already exposes `MorningClient`/`MorningAuth` as an importable library (`from
denidin_mcp_morning.morning_client import MorningClient`, confirmed as the existing import idiom
its own `conftest.py`/tests already use). Putting the pipeline's phases in a new
`apps/prod-ledger-backfill/` app, with its own `requirements.txt` pinning `apps/morning-mcp-app` as
a local path dependency, keeps `denidin-app` and `morning-mcp-app` completely untouched by this
feature — no changes to either app's own source, matching `spec.md`'s Out of Scope.

## R10: Phase 4 (load-to-prod) — deliberately left open at this planning stage

**Finding**: per Feature 035, prod's real data (`{data_root}/events/`) lives on the Windows
always-on box, reachable read-only from the Mac via the persistent sshfs mount
(`~/denidin-winprod-data`) — there is no existing sanctioned *write* path from the Mac into prod's
real data directory today. Two plausible mechanisms exist (write via a temporary elevated mount, or
run Phase 4 directly on the Windows box over the `denidin-winprod` SSH alias) — deliberately not
decided here, per the user's own framing ("the writing to prod data eventually," i.e. a later
implementation phase of this same feature). This will get its own short research pass when Phase 4
is actually implemented, after Phase 3.5's validation gate exists and has been exercised.

## Summary of design decisions this research settles

| Decision | Resolution |
|---|---|
| How Phase 1 talks to Morning | `MorningClient` constructed directly, real prod creds — R1/R2. |
| Why not `tools.list_invoices` | 100-item cap + refusal-on-overflow, conversational-UX-only — R3. |
| Phase 1 pagination | Own loop against raw `/documents/search`, no cap — R3/R4. |
| Phase 3 output/dedup, Phase 3.5 anomaly source | `LedgerEventManager`, pure local reuse, not "live" — R5/R8. |
| Credentials shape | Raw Green Invoice (`api_key_id`/`api_key_secret`/`auth_url`/`base_url`) — R6. |
| Phase 2 method selection | ~20-document sandbox experiment, Method A vs Method B, diff-driven — R7. |
| New app location | `apps/prod-ledger-backfill/`, imports `morning-mcp-app`'s package — R9. |
| Phase 4 mechanism | Deliberately open, decided at implementation time — R10. |
