# Permanent ground-truth Morning sandbox clients

This is the full registry of real Morning **sandbox** clients that this
test suite depends on existing **permanently** — created once, referenced
by hardcoded exact name forever after, never re-seeded per test run. If the
Morning sandbox is ever wiped/reset, every test listed below will start
failing on a genuine "client not found" (not a regression) until these are
recreated exactly as described here.

This registry exists per explicit user request (2026-08-11, bugfix-039):
before wiping the sandbox, read this file and know what to recreate
afterward.

## Why permanent fixtures exist at all

Seeding a client fresh (via a real `add_client` conversation) costs 2 real
OpenAI calls per test, every single run, forever. For tests whose whole
premise is "a client that already exists, with a specific real spelling,"
that's a repeated, avoidable cost — so a small number of tests instead
depend on a client seeded once, out of band, and never re-created.

**This is NOT the default pattern for this suite.** Most tests
(`test_godfather_creates_invoice_via_whatsapp` and friends) deliberately use
a *fresh*, randomly-generated client every run
(`_unique_client_name`/`_seed_client_via_conversation` in
`denidin_mcp_e2e_helpers.py`) — a shared client that keeps accumulating new
invoices on every run eventually breaks pagination-sensitive assertions in
*other* tests (this happened for real to `"יוסי שמואלי"`, see below). Only
use a permanent fixture when a test's own assertions don't care how many
documents the client accumulates over time (e.g. bugfix-039's T1/T2, which
only check that *one* `create_invoice` call succeeds against the right
client — never list/count that client's full document history).

## Registry

| Client name | Seeded | Used by | What breaks without it | Notes |
|---|---|---|---|---|
| `דורית אשכנזי` | 2026-07-28 | `test_denidin_morning_list_invoices_e2e.py` (bugfix-014 tests) | `test_client_all_payments_gets_the_complete_picture` and its siblings | **Not just the client** — 6 specific tax invoices (types 305/400) with hardcoded document numbers `50854`-`50859` (4 unpaid, 2 paid via a linked receipt). A reseed after a wipe gets **new** document numbers from Morning (sequential, not chooseable) — the hardcoded `_GROUND_TRUTH_*_INVOICE_NUMBERS` constants in that test file would need updating to match, not just the client re-added. |
| `Test Client DENIDIN_TEST_1770474207` | 2026-02-07 | `test_denidin_morning_invoice_lifecycle_e2e.py` (`KNOWN_INVOICE_CLIENT`) | `test_godfather_gets_invoice_details_via_whatsapp` | Also number-dependent: hardcoded invoice `60006`, amount `123.45`, status `שולם` (paid). Same reseed caveat as above — the invoice number can't be chosen, only the client name is under your control. |
| `זהבית צור` | 2026-08-11 | `test_denidin_morning_invoice_creation_e2e.py::test_create_document_t1_single_letter_added_to_stored_name` | That one test, T1 | **Not** number-dependent — the test only checks that a `create_invoice` call succeeds against this client, never a specific invoice number. Safe to accumulate documents over time; safe to just re-add the client by name after a wipe. Real Morning `client_id`: `8c8b2a09-bbd6-4881-8589-bff6a3bcde2e` (recorded for traceability only — never referenced by any test, per REQ-CLIENT-018). |
| `כרמלי דודי` | 2026-08-11 | `test_denidin_morning_invoice_creation_e2e.py::test_create_document_t2_single_letter_removed_from_stored_name` | That one test, T2 | Same as above — name-only dependency, no invoice numbers to match. Real Morning `client_id`: `937d2728-2aa0-4a03-824d-762d996a2074` (traceability only, never referenced by any test). |
| ~~`יוסי שמואלי`~~ | 2026-07-21, **retired** | Nothing currently — historical only | Nothing | Originally bugfix-014's ground truth; retired 2026-07-28 after `test_godfather_creates_invoice_via_whatsapp` (which back then also used this same fixed name) made it grow from 6 to 14 real documents and broke pagination assumptions in the bugfix-014 tests. Replaced by `דורית אשכנזי` above. Kept in this table only so nobody re-seeds it expecting it to matter. |

## Collision safety (why these exact words were chosen)

`_unique_client_name()` (`denidin_mcp_e2e_helpers.py`) draws random
first+family name pairs from `data/hebrew_first_names.txt` /
`data/hebrew_family_names.txt` for every *other* test's fresh clients. A
permanent fixture that shares a word with that pool risks a false
"ambiguous match" against some unrelated randomly-named test client years
later (per-word intersection search, bugfix-039's
`resolve_client_by_name`) — matching BOTH words is what makes a
false match possible, so a name is safe as long as AT LEAST ONE of its two
words can never be drawn by `_unique_client_name()` at all, regardless of
the other word.

`זהבית` (T1's first word) and `כרמלי` (T2's first word) are each verified
absent from **both** pool files (2026-08-11, `grep -xc` against
`hebrew_first_names.txt`/`hebrew_family_names.txt` — 0 hits each). That
alone is enough to guarantee neither fixture can ever intersect-match a
random test client, even though the *other* word in each pair deliberately
IS a real pool word (`צור` is a real family name; `דוד`/`דודי` are a real
first name) — T1/T2 need that word to be a genuine, real Hebrew word for
the single-letter-edit relationship to mean anything; only the pool-free
word needs to carry the collision guarantee, and it does. Before adding any
new permanent fixture, verify the same way:
```bash
cd apps/denidin-app/tests/billed/data
grep -xc "<word>" hebrew_first_names.txt hebrew_family_names.txt
```

## (Re)seeding `זהבית צור` and `כרמלי דודי`

Seeded 2026-08-11, directly against the real Morning sandbox via
`MorningClient` (config.test.json credentials — same sandbox account/API
key as `config.dev.json`, verified by matching `api_url`/`api_key_id`) —
**no OpenAI call involved**, per explicit user instruction ("seed them
directly in morning, you dont need openai"). Used
`tests/integration/_seed_helpers.seed_real_client` (the same helper
`apps/morning-mcp-app`'s own sandbox integration tests use), from a
throwaway one-off script — not from a committed test, so it can never
accidentally re-run and isn't part of the normal suite.

To re-seed after a sandbox wipe, run the equivalent from
`apps/morning-mcp-app` (own venv activated):
```python
from pathlib import Path
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from tests.integration._seed_helpers import seed_real_client

config = load_config(Path("config/config.test.json"))
client = MorningClient(api_key_id=config.api_key_id, api_key_secret=config.api_key_secret, base_url=config.api_url)
seed_real_client(client, "GT_T1", name="זהבית צור")
seed_real_client(client, "GT_T2", name="כרמלי דודי")
```
(`seed_real_client` is idempotent-adjacent — it doesn't check for an
existing exact match itself, so check via `client.search_clients` first if
unsure whether a fixture already exists, to avoid creating a duplicate.)
