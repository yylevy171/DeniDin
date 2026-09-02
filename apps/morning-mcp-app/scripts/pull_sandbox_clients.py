#!/usr/bin/env python3
"""Feature 059 item 5/8: one-time (occasionally-refreshed) pull of the Morning
SANDBOX's current client roster.

Group 2 billed/expensive E2E tests in ``apps/denidin-app`` just need *a* valid
client to exist - client freshness buys them nothing. Historically each such
test paid 2-3 billed OpenAI turns + a ``time.sleep(3)`` to seed a throwaway
client via the conversational ``add_client`` flow. Instead, this script pulls
every client that already exists in the sandbox, filters the list down to names
that are safe to pick blindly, and writes it as a committed fixture that those
tests ``random.choice`` from - no OpenAI, no seeding, no sleep.

Run it from this app's own venv (it uses ``MorningClient`` directly - read-only,
same class of call as this app's sandbox integration tests, no OpenAI):

    cd apps/morning-mcp-app
    ./venv/bin/python3 scripts/pull_sandbox_clients.py

Output (overwritten in place):
    apps/denidin-app/tests/fixtures/morning_sandbox_clients.json

Re-run occasionally to refresh. The fixture is a cache, not a source of truth -
a slightly stale row (a client whose phone/email changed, or was deleted) only
ever costs one test one retry-worthy miss, never a wrong pass.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parents[1]
sys.path.insert(0, str(APP_ROOT / "src"))

from denidin_mcp_morning.config import load_config  # noqa: E402
from denidin_mcp_morning.morning_client import MorningClient  # noqa: E402
from denidin_mcp_morning.utils.time_utils import local_isoformat  # noqa: E402

CONFIG_PATH = APP_ROOT / "config" / "config.test.json"
OUTPUT_PATH = REPO_ROOT / "apps" / "denidin-app" / "tests" / "fixtures" / "morning_sandbox_clients.json"

# Names that other tests make specific/counting/relational assertions about, or
# that carry a deliberately-ambiguous shared prefix. A Group 2 test that picked
# one of these and created a document against it would break those other tests
# (this is exactly what happened for real to "יוסי שמואלי" - see
# apps/denidin-app/tests/billed/GROUND_TRUTH_CLIENTS.md). The random pool must
# only contain clients that nobody asserts anything specific about.
DENYLIST_EXACT = {
    "דורית אשכנזי",      # bugfix-014 list_invoices - exact invoice #50854-50859 counts
    "רימונה כהן",         # invoice lifecycle - KNOWN_INVOICE #52046
    "זהבית צור",          # invoice creation T1 - stored-name-correction premise
    "כרמלי דודי",         # invoice creation T2 - stored-name-correction premise
    "Dana Cohen",         # vcf contact fixture (complete_card_dana_cohen.vcf)
    "גיל ברטל",           # vcf contact fixture (00005372-גיל ברטל .vcf)
    "עטיה רועי מאיר",     # expensive bank-deposit image payer (name dictated by fixture image)
    "יוסי שמואלי",        # retired permanent fixture - documented pagination casualty
}
# Any client whose name starts with one of these word-prefixes is dropped: the
# sandbox holds several "הסתדרות כללית חדשה ..." records on purpose (bugfix-028
# B4 ambiguity probe), and Morning's search is a word-aligned prefix match, so
# a blind pick there sends the model into "which one did you mean?".
DENYLIST_PREFIX = (
    "הסתדרות",
    "DENIDIN",
    "Test Client",
)

# A token made entirely of Hebrew-block code points (U+0590-U+05FF covers the
# letters plus geresh U+05F3 / gershayim U+05F4), optionally with an internal
# hyphen. No Latin letters, no digits, no parentheses.
_HEBREW_TOKEN_RE = re.compile(r"^[֐-׿]+(?:-[֐-׿]+)*$")


def _is_clean_pickable_name(name: str) -> bool:
    """A name safe to type verbatim into a Hebrew conversation and have the
    model resolve as a clean exact match: exactly two Hebrew words, no digits,
    no Latin letters, no bracketed qualifiers."""
    name = name.strip()
    if name in DENYLIST_EXACT:
        return False
    if any(name.startswith(p) for p in DENYLIST_PREFIX):
        return False
    tokens = name.split()
    if len(tokens) != 2:
        return False
    return all(_HEBREW_TOKEN_RE.match(tok) for tok in tokens)


def _fetch_all_clients(client: MorningClient) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        resp = client.search_clients({"page": page})
        batch = resp.get("items") or []
        items.extend(batch)
        total = resp.get("total", len(items)) or 0
        pages = resp.get("pages", 1) or 1
        print(f"  page {page}/{pages}: +{len(batch)} (total so far {len(items)}/{total})")
        if page >= pages or not batch or len(items) >= total:
            break
        page += 1
    return items


def main() -> int:
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        print("ERROR: config.test.json has no api_key_id/api_key_secret", file=sys.stderr)
        return 1

    client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )

    print(f"Pulling every client from {config.api_url} ...")
    raw = _fetch_all_clients(client)
    print(f"Fetched {len(raw)} raw client records.")

    kept: list[dict] = []
    seen_first_token: dict[str, int] = {}
    for item in raw:
        name = (item.get("name") or "").strip()
        if not _is_clean_pickable_name(name):
            continue
        first = name.split()[0]
        seen_first_token[first] = seen_first_token.get(first, 0) + 1
        emails = item.get("emails") or []
        kept.append(
            {
                "name": name,
                "id": item.get("id"),
                "email": (emails[0] if emails else None),
                "phone": item.get("phone") or None,
                "tax_id": item.get("taxId") or None,
            }
        )

    # Unambiguous only: a first name-word that appears more than once across the
    # kept set can send Morning's word-prefix search to the wrong record.
    unambiguous = [c for c in kept if seen_first_token[c["name"].split()[0]] == 1]
    unambiguous.sort(key=lambda c: c["name"])

    dropped_ambiguous = len(kept) - len(unambiguous)
    print(
        f"Kept {len(unambiguous)} clean unambiguous names "
        f"(dropped {len(raw) - len(kept)} unclean, {dropped_ambiguous} ambiguous-first-word)."
    )

    payload = {
        "pulled_at": local_isoformat(),
        "source": config.api_url,
        "note": (
            "Feature 059: real Morning sandbox clients, filtered to names safe to "
            "pick blindly. Group 2 billed/expensive tests random.choice from this "
            "instead of seeding a throwaway client. Regenerate with "
            "apps/morning-mcp-app/scripts/pull_sandbox_clients.py"
        ),
        "clients": unambiguous,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} ({len(unambiguous)} clients).")

    with_email = sum(1 for c in unambiguous if c["email"])
    with_phone = sum(1 for c in unambiguous if c["phone"])
    print(f"  with email: {with_email}   with phone: {with_phone}")
    if len(unambiguous) < 30:
        print("WARNING: fewer than 30 usable names - Group 2 random spread will be thin.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
