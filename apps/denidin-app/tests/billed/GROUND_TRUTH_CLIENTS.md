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
(`_unique_client_name`/`_seed_client` in
`denidin_mcp_e2e_helpers.py`) — a shared client that keeps accumulating new
invoices on every run eventually breaks pagination-sensitive assertions in
*other* tests (this happened for real to `"יוסי שמואלי"`, see below). Only
use a permanent fixture when a test's own assertions don't care how many
documents the client accumulates over time (e.g. bugfix-039's T1/T2, which
only check that *one* `create_invoice` call succeeds against the right
client — never list/count that client's full document history).

## The random-pick pool (Feature 059 item 5) — the middle option

Between "seed a fresh client every run" (2 OpenAI calls + a `time.sleep(3)`,
every run, forever) and "one hardcoded permanent name" (this registry), there
is a third pattern for the large group of tests that just need **a** client to
exist and genuinely don't care *which* one — e.g. "create a type-320 for
someone", "list my clients and see one of them", "update a client's phone".
This is Feature 059's "Group 2".

`apps/denidin-app/tests/fixtures/morning_sandbox_clients.json` is a **committed**
snapshot of every real Morning sandbox client whose name is safe to pick
blindly (exactly two Hebrew words, no digits/Latin/brackets, first word unique
across the set so Morning's word-prefix search can't land on the wrong record,
and not on the denylist below). Group 2 tests call
`denidin_mcp_e2e_helpers.pick_existing_client()` — a plain `random.choice` over
that file, **no OpenAI call, no seeding conversation, no sleep** (the client is
already indexed, so it resolves on the very next turn).

Spreading the picks randomly over the whole pool (182 clients as of the first
pull) is deliberate: it is exactly what stops any single client from
accumulating invoices run-over-run and breaking a pagination-sensitive
assertion elsewhere — the `יוסי שמואלי` failure mode (see the Registry).

**Regenerating the snapshot** (occasionally — it's a cache, not a source of
truth; a stale row only ever costs one test one retry-worthy miss, never a
wrong pass):
```bash
cd apps/morning-mcp-app
./venv/bin/python3 scripts/pull_sandbox_clients.py
```
That script holds its own denylist (`DENYLIST_EXACT` / `DENYLIST_PREFIX`) of
names other tests make specific/counting/relational assertions about — every
permanent fixture in the Registry below, the two vCard-fixture names, the
expensive bank-deposit payer `עטיה רועי מאיר`, and the `הסתדרות כללית חדשה …`
ambiguity probes. **When you add a new permanent fixture to this registry, add
its name to that script's `DENYLIST_EXACT` too** — otherwise the next
regeneration could pull it into the random pool and a Group 2 test could create
documents against it.

Tests that DO depend on a brand-new, never-before-seen client (Feature 059's
"Group 1" — the `add_client` happy-path tests, near-duplicate-name tests,
ambiguous-prefix tests, and the client-mutation tests that need a disposable
record to change) keep using `_seed_client` (its drawn-name, `create=False`,
and specific-name variants) and are unaffected by any of the above.

## Registry

| Client name | Seeded | Used by | What breaks without it | Notes |
|---|---|---|---|---|
| `דורית אשכנזי` | 2026-07-28 | `test_denidin_morning_list_invoices_e2e.py` (bugfix-014 tests) | `test_client_all_payments_gets_the_complete_picture` and its siblings | **Not just the client** — 6 specific tax invoices (types 305/400) with hardcoded document numbers `50854`-`50859` (4 unpaid, 2 paid via a linked receipt). A reseed after a wipe gets **new** document numbers from Morning (sequential, not chooseable) — the hardcoded `_GROUND_TRUTH_*_INVOICE_NUMBERS` constants in that test file would need updating to match, not just the client re-added. |
| `רימונה כהן` | 2026-08-12 | `test_denidin_morning_invoice_lifecycle_e2e.py` (`KNOWN_INVOICE_CLIENT`) | `test_godfather_gets_invoice_details_via_whatsapp` | Also number-dependent: hardcoded invoice `52046`, amount `156.75`, status `שולם` (paid), document date `12/08/2026`. Same reseed caveat as above — the invoice number can't be chosen, only the client name is under your control. Real Morning `client_id`: `9950aa19-a21b-47ad-a6aa-4957d289f073` (traceability only, never referenced by any test). Seeded directly via `tools.add_client`/`create_invoice`/`create_receipt` (no OpenAI call), same as `זהבית צור`/`כרמלי דודי` below. |
| ~~`Test Client DENIDIN_TEST_1770474207`~~ | 2026-02-07, **retired 2026-08-12** | Nothing currently — historical only | Nothing | Replaced by `רימונה כהן` above. **The client/invoice was never deleted** (confirmed live via a direct `list_invoices(number="60006")` lookup - document #60006 and its embedded client name are both still there) — it broke for an architecture reason, not data loss: this client predates Feature 027's requirement that documents reference a real, resolvable Morning Client record, so it's a bare name+phone object with no `client.id` at all. `resolve_client_name`'s mandatory-first search (2026-08-12 architecture) searches real Client records via `search_clients` and can never find a client that was never saved as one. Kept in this table only so nobody re-investigates this as data loss. |
| `זהבית צור` | 2026-08-11 | `test_denidin_morning_invoice_creation_e2e.py::test_create_document_t1_single_letter_added_to_stored_name` | That one test, T1 | **Not** number-dependent — the test only checks that a `create_invoice` call succeeds against this client, never a specific invoice number. Safe to accumulate documents over time; safe to just re-add the client by name after a wipe. Real Morning `client_id`: `8c8b2a09-bbd6-4881-8589-bff6a3bcde2e` (recorded for traceability only — never referenced by any test, per REQ-CLIENT-018). |
| `כרמלי דודי` | 2026-08-11 | `test_denidin_morning_invoice_creation_e2e.py::test_create_document_t2_single_letter_removed_from_stored_name` | That one test, T2 | Same as above — name-only dependency, no invoice numbers to match. Real Morning `client_id`: `937d2728-2aa0-4a03-824d-762d996a2074` (traceability only, never referenced by any test). |
| `Dana Cohen` | 2026-07-30 (discovered permanent 2026-08-12) | `tests/billed/test_denidin_vcf_contact_e2e.py::test_godfather_shares_contact_card_complete_requires_approval` | That one test | **Not deliberately seeded as a permanent fixture at the time** — the name is hardcoded directly in the committed `tests/fixtures/contacts/complete_card_dana_cohen.vcf` fixture (phone `+972 50-123-4567`, email `dana.cohen.qs@example.com`), and the test itself asserts on the literal string `"Dana Cohen"`. The first successful run (2026-07-30) created a real client under this exact name; every run since is therefore a genuine exact-match duplicate, not a fresh creation — this only became visible 2026-08-12 when the "offer to update instead" exact-match behavior was removed (see runtime_constitution.md) and add_client started correctly refusing instead of silently updating. The test itself was adapted the same day to assert the real "already exists, refuses cleanly" behavior directly, rather than assuming a fresh create. Real Morning `client_id`: `2c4f7b86-07c1-44c6-b119-f8f0249958e1` (traceability only, never referenced by any test). A reseed after a wipe just needs the vCard shared once, successfully, again — no number-dependency like the invoice-linked fixtures above. |
| `גיל ברטל` | 2026-07-30 (discovered permanent 2026-08-12) | `tests/billed/test_denidin_vcf_contact_e2e.py::test_godfather_shares_contact_card_missing_email_is_asked_for` | That one test | Same situation as `Dana Cohen` immediately above — same original seeding session (created 44 seconds apart), name hardcoded in the committed real-captured `tests/fixtures/contacts/00005372-גיל ברטל .vcf` fixture (phone `050-7951824`, email `gil.bartal.qs@example.com` supplied during the test's own missing-email flow). One difference from `Dana Cohen`: the model doesn't always refuse pre-emptively here — found live 2026-08-12, it sometimes calls `add_client` anyway and Morning's own API rejects the duplicate directly (a real `mcp_tool_execution_error`). The test was adapted to accept EITHER outcome (clean pre-emptive refusal, or an attempted call Morning itself rejects) as correct, gated strictly on a genuine exact match actually being seen in the flow — any other add_client failure reason still fails the test normally. Real Morning `client_id`: `04d1c153-6d9c-467f-9eb1-a9661b4df4b6` (traceability only, never referenced by any test). Same reseed note as `Dana Cohen` — just share the vCard once, successfully, again. |
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

`רימונה` (`רימונה כהן`'s first word, seeded 2026-08-12) was verified the same
way — absent from both pool files (0 hits each) — before creating it; `כהן`
is deliberately a common real family name (doesn't need to be pool-free
itself, per the same one-word-is-enough logic above), chosen so a bare-name
resolve against an unrelated same-surname test client stays plausible-looking
rather than a giveaway.

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

## (Re)seeding `רימונה כהן`

Seeded 2026-08-12, same no-OpenAI principle as above, but via
`denidin_mcp_morning.tools` directly (`add_client`/`create_invoice`/
`create_receipt`) rather than `seed_real_client` - this fixture needs a real,
paid, numbered invoice attached, not just a bare client record. From
`apps/morning-mcp-app` (own venv activated):
```python
from pathlib import Path
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning import tools

config = load_config(Path("config/config.test.json"))
client = MorningClient(api_key_id=config.api_key_id, api_key_secret=config.api_key_secret, base_url=config.api_url)

print(tools.add_client(client, name="רימונה כהן", email="ground-truth-invoice-lifecycle@example.com", phone="050-1111111"))
# Wait a few seconds for the search index before create_invoice (name_resolved
# requires an exact search hit) - or just retry create_invoice once if it refuses.
print(tools.create_invoice(client, client_name="רימונה כהן", amount=156.75, description="Ground truth fixture invoice", name_resolved=True))
# Read the internal_morning_id out of the confirmation above, then:
print(tools.create_receipt(client, "<internal_morning_id>", payment_date="<today's date, ISO>"))
```
Record the new invoice number/amount/date from the output and update
`test_denidin_morning_invoice_lifecycle_e2e.py`'s `KNOWN_INVOICE_*` constants
and this table to match - Morning assigns the invoice number, it can't be
chosen.
