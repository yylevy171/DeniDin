# Quickstart: Verifying Morning Long List Support — Feature 038

**Purpose**: Manual/spot-check verification steps once the implementation
(Phase 3) is complete, beyond the automated test suite. Uses real,
already-existing sandbox data (research.md Decision 4) — no invoices are
seeded by this quickstart.

## Prerequisites

- `apps/morning-mcp-app` virtualenv set up (`venv/bin/python3`), with
  `config/config.test.json` populated with real sandbox `api_key_id`/
  `api_key_secret` (already present — confirmed during research.md
  Decision 1).

## 1. Confirm the complete-fetch + token-budget-truncation path (US1 + US3)

```bash
cd apps/morning-mcp-app
venv/bin/python3 - <<'PY'
import sys
sys.path.insert(0, "src")
from pathlib import Path
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import list_invoices

config = load_config(Path("config/config.test.json"))
client = MorningClient(api_key_id=config.api_key_id, api_key_secret=config.api_key_secret, base_url=config.api_url)

# Real sandbox range, 81 invoices (research.md Decision 4) - no seeding needed.
result = list_invoices(client, from_date="2026-07-19", to_date="2026-07-21")
print(result)
print("---")
print("Invoice blocks shown:", result.count("חשבונית #"))
PY
```

**Expect**: the printed reply's first line states both a "shown" count and
the real total (81) — since 81 real invoices format to far more than the
real, unmodified 2500-token budget (research.md Decision 7, confirmed
~22,695 tokens at full length), only a handful (confirmed live: ~8-9) of
`חשבונית #` blocks should appear, followed by a closing note that more
results were omitted because the reply would otherwise be too long,
asking to narrow the search.

**If this range's real total has drifted from 81** (sandbox data changed
since 2026-08-04): re-run research.md Decision 4's probe method to find a
current range with a similar (>10, ≤100) count before treating a mismatch
here as a bug.

## 2. Confirm the refusal path (US2)

```bash
cd apps/morning-mcp-app
venv/bin/python3 - <<'PY'
import sys
sys.path.insert(0, "src")
from pathlib import Path
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import list_invoices

config = load_config(Path("config/config.test.json"))
client = MorningClient(api_key_id=config.api_key_id, api_key_secret=config.api_key_secret, base_url=config.api_url)

# Real sandbox range, 103 invoices (research.md Decision 4) - just over the 100 cap.
result = list_invoices(client, from_date="2026-07-13", to_date="2026-07-15")
print(result)
PY
```

**Expect**: a Hebrew message stating "103" as the real total and asking to
narrow the search — no itemized invoice content, no token-budget
truncation note (the two are mutually exclusive).

## 3. Confirm a genuine partial-prefix truncation (US3)

```bash
cd apps/morning-mcp-app
venv/bin/python3 - <<'PY'
import sys
sys.path.insert(0, "src")
from pathlib import Path
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import list_invoices

config = load_config(Path("config/config.test.json"))
client = MorningClient(api_key_id=config.api_key_id, api_key_secret=config.api_key_secret, base_url=config.api_url)

# Real sandbox range, 13 invoices, real 2500-token default budget - no
# override (research.md Decision 4/7).
result = list_invoices(client, from_date="2026-07-21", to_date="2026-07-22")
print(result)
print("---")
print("Invoice blocks shown:", result.count("חשבונית #"))
PY
```

**Expect**: exactly 8 of 13 `חשבונית #` blocks shown (confirmed live,
robust to the exact 100-150-token reserve chosen at implementation), a
"showing 8 of 13" (or equivalent) opening line, and a closing note that
more results were omitted for length.

## 4. End-to-end (optional, requires dev environment approval)

Once `dev` is running (requires explicit human approval per CLAUDE.md's
"NEVER START AN ENVIRONMENT... WITHOUT EXPLICIT APPROVAL" rule — do not
start it as part of this quickstart without asking first), a godfather can
send a real WhatsApp message asking for invoices from `2026-07-19` to
`2026-07-21` (§1), `2026-07-13` to `2026-07-15` (§2), or `2026-07-21` to
`2026-07-22` (§3) and confirm the bot's reply matches the corresponding
section above — this also exercises the three new billed tests' scenarios
manually, one turn at a time.
