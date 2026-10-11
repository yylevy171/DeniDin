"""Hebrew fixture, built from today's real production/regression data plus
real words from the app's own hebrew_first_names.txt/hebrew_family_names.txt
pool - prints, for every scenario, exactly what's stored / what's queried /
what the algorithm returns / what the scenario is actually testing.

Includes a large realistic noise pool (real random Hebrew first+family name
combinations, like the app's own _unique_client_name()) mixed into every
scenario - a tiny fixture lets single letters accidentally become "unique"
against totally unrelated words (a real thing that happened on the first
draft of this table: "לקוח" and "לוינגר" collided on the shared letter ל
alone), which a real ~hundreds-of-clients sandbox would never do. The noise
pool makes short prefixes behave the way they would for real.
"""
import random
from pathlib import Path

from client_resolution_prototype import Client, FakeMorning, resolve_client

random.seed(39)  # reproducible

# Reads the real app's own name pool directly (not a copy) so this stays in
# sync automatically - run this script from anywhere, the path is relative
# to this file's own location (specs/bugfixes/bugfix-039-artifacts/).
_DATA_DIR = Path(__file__).resolve().parents[3] / "apps" / "denidin-app" / "tests" / "billed" / "data"
FIRST_NAMES = [w.strip() for w in (_DATA_DIR / "hebrew_first_names.txt").read_text(encoding="utf-8").splitlines() if w.strip()]
FAMILY_NAMES = [w.strip() for w in (_DATA_DIR / "hebrew_family_names.txt").read_text(encoding="utf-8").splitlines() if w.strip()]

# ============================================================================
# Named clients - real names wherever real names exist (today's failures,
# today's real sandbox ground-truth clients, the original production
# incident); constructed only where a specific structural property needs it.
# ============================================================================
C_ADLER_STORED = Client("adler", "דודי אדלר")  # real: the 2026-08-10 production incident's stored name
C_ZUR = Client("zur", "זהבית צור")  # real: T1 ground-truth client, live in the sandbox today
C_CARMELI = Client("carmeli", "כרמלי דודי")  # real: T2 ground-truth client, live in the sandbox today
C_MARCEL = Client("marcel", "מרסל אלמו")  # real: today's billed-test failure - a genuinely EXACT name wrongly asked for confirmation
C_OVADIA = Client("ovadia", "עובדיה פרלמן")  # real: same failure's earlier run, also genuinely exact
C_DORIT = Client("dorit", "דורית אשכנזי")  # real: bugfix-014's permanent ground-truth client
C_WEISS = Client("weiss", "אורי וייס")
C_WEISSMAN = Client("weissman", "אורי וייסמן")  # real family-name prefix pair with C_WEISS: וייס/וייסמן
C_TECH_NORTH = Client("tech_n", "פתרונות טכנולוגיה צפון")  # constructed ambiguous business-style pair
C_TECH_SOUTH = Client("tech_s", "פתרונות טכנולוגיה דרום")
# Note: no separate "target" client for the discoverability cluster - the
# whole point is that "דוד אבו זכרי" (the name someone would actually type)
# does NOT exist as a real client; only its three lookalikes do. A clean,
# unrelated real 3-word client (C_THREEWORD) covers the "exact 3-word
# match" scenario instead, so it's never ambiguous with the cluster.
C_DAVID_DECOY_PREFIX = Client("david_decoy_prefix", "דודו אבו זכרי")  # false-early-unique-prefix trap on word 1
C_DAVID_DECOY_LASTWORD = Client("david_decoy_lastword", "רוני זמיר זכרי")  # discoverable ONLY via word 3 ("זכרי")
C_DAVID_DECOY_FIRSTWORD = Client("david_decoy_firstword", "דוד לוינגר")  # discoverable via word 1 only, exact word match
C_THREEWORD = Client("threeword", "דן אביטן שגיא")  # unrelated real-word 3-word client, for exact-match tests

NAMED = [
    C_ADLER_STORED, C_ZUR, C_CARMELI, C_MARCEL, C_OVADIA, C_DORIT,
    C_WEISS, C_WEISSMAN, C_TECH_NORTH, C_TECH_SOUTH,
    C_DAVID_DECOY_PREFIX, C_DAVID_DECOY_LASTWORD, C_DAVID_DECOY_FIRSTWORD,
    C_THREEWORD,
]

_NAMED_NAMES = {c.name for c in NAMED}
_NAMED_WORDS = {w for c in NAMED for w in c.name.split()}


def _make_noise(n: int) -> list:
    """n realistic random Hebrew clients, filtered so none of their words
    collide with any word used by the deliberately-named clients above -
    the whole point of the named clients is to test SPECIFIC structural
    relationships; noise must never accidentally interfere with them."""
    noise = []
    seen_names = set()
    while len(noise) < n:
        name = f"{random.choice(FIRST_NAMES)} {random.choice(FAMILY_NAMES)}"
        if name in seen_names or name in _NAMED_NAMES:
            continue
        if any(w in _NAMED_WORDS for w in name.split()):
            continue
        seen_names.add(name)
        noise.append(Client(f"noise_{len(noise)}", name))
    return noise


NOISE = _make_noise(300)

# ONE permanent, unified client universe - every scenario below queries
# this SAME fixture, exactly like every query against the real Morning
# sandbox hits the same one account. No per-test curation: if two of the
# clients happen to genuinely share a word, every query sees both, all
# the time - which is the honest, realistic condition to test against.
ALL_CLIENTS = NAMED + NOISE

# ============================================================================
# (label, stored clients, relevant-names-to-display, query, what this tests)
# Every scenario queries the SAME ALL_CLIENTS fixture - one unified
# database, like the real Morning account. "relevant" is just which named
# client(s) each row's docstring is actually about, for the printout below;
# it does NOT mean those are the only clients present.
# ============================================================================
SCENARIOS = [
    (
        "today's real bug: exact name wrongly asked for confirmation",
        ALL_CLIENTS, [C_OVADIA], "עובדיה פרלמן",
        "REAL 2026-08-11 billed-test failure: list_invoices got stuck asking "
        "'did you mean עובדיה פרלמן?' about a client already named exactly "
        "that - must resolve immediately via Step 0.",
    ),
    (
        "today's real bug, second client",
        ALL_CLIENTS, [C_MARCEL], "מרסל אלמו",
        "Same real failure, the other client name it happened with in the "
        "same test run.",
    ),
    (
        "messy whitespace still resolves exactly",
        ALL_CLIENTS, [C_OVADIA], "  עובדיה   פרלמן ",
        "Real user messages have inconsistent spacing - must not break "
        "the exact-match fast path.",
    ),
    (
        "prefix of a real client is not exact",
        ALL_CLIENTS, [C_CARMELI], "כרמלי דוד",
        "T2 ground-truth shape: 'כרמלי דוד' IS a genuine whole-string prefix "
        "of 'כרמלי דודי' - Step 0 must not mistake a prefix for equality.",
    ),
    (
        "word-order independence, real client",
        ALL_CLIENTS, [C_OVADIA], "פרלמן עובדיה",
        "A real client's name, reordered - must still resolve exactly via "
        "the word-by-word loop (Step 0's whole-string check fails on "
        "reordered input by construction).",
    ),
    (
        "T1 - letter added beyond stored word (real ground-truth pair)",
        ALL_CLIENTS, [C_ZUR], "זהבית צורן",
        "The actual T1 regression case (bugfix-039) - stored 'צור', typed "
        "'צורן', one letter added at the end.",
    ),
    (
        "T2 - letter removed from stored word (real ground-truth pair)",
        ALL_CLIENTS, [C_CARMELI], "כרמלי דוד",
        "The actual T2 regression case (bugfix-039) - stored 'דודי', typed "
        "'דוד', one letter removed.",
    ),
    (
        "the ORIGINAL 2026-08-10 production incident, reproduced literally",
        ALL_CLIENTS, [C_ADLER_STORED], "דוד אדלר",
        "The exact real query/stored-name pair from the live production "
        "incident that started bugfix-039 - admin asked about 'דוד אדלר', "
        "real invoice was under 'דודי אדלר'.",
    ),
    (
        "false-unique-early-prefix trap, real prefix pair",
        ALL_CLIENTS, [C_OVADIA], "עובד פרלמן",
        "'עובד' is a genuine prefix of 'עובדיה' (both real words in the "
        "app's own name pool) - briefly unique on a short prefix, must "
        "still fail the FULL-word check against 'עובדיה'.",
    ),
    (
        "candidate discoverable via only one of three words",
        ALL_CLIENTS,
        [C_DAVID_DECOY_PREFIX, C_DAVID_DECOY_LASTWORD, C_DAVID_DECOY_FIRSTWORD],
        "דוד אבו זכרי",
        "Constructed 3-word cluster (target itself absent): "
        "'רוני זמיר זכרי' shares nothing with 'דוד'/'אבו' at all - only "
        "'זכרי' (searched independently) can ever surface it. Also proves "
        "'דודו אבו זכרי' (false-prefix trap) and 'דוד לוינגר' "
        "(shares only word 1) both surface too.",
    ),
    (
        "one word's search returns multiple candidates, not just unique",
        ALL_CLIENTS,
        [C_DAVID_DECOY_PREFIX, C_DAVID_DECOY_LASTWORD],
        "דוד אבו זכרי",
        "'זכרי' alone matches BOTH remaining decoys - discovery must not "
        "require per-word uniqueness, only the exactness chain does.",
    ),
    (
        "genuinely ambiguous - two clients share every query word",
        ALL_CLIENTS, [C_TECH_NORTH, C_TECH_SOUTH], "פתרונות טכנולוגיה",
        "Neither word, however far grown, ever disambiguates between the "
        "north/south pair - real ambiguity, not a bug.",
    ),
    (
        "adding the disambiguating word resolves exactly",
        ALL_CLIENTS, [C_TECH_NORTH], "פתרונות טכנולוגיה צפון",
        "Same ambiguous pair (both still present), one more word given - "
        "must resolve fully, not stay stuck ambiguous.",
    ),
    (
        "not found at all",
        ALL_CLIENTS, [], "קשקשתטויותאבגדהוזח בלאסתטויותשבגק",
        "No word matches anything, anywhere - the honest 'not found' case "
        "(two pieces of pure gibberish, guaranteed not to collide with "
        "300 real random names by construction).",
    ),
    (
        "real word plus pure gibberish word",
        ALL_CLIENTS, [C_OVADIA], "עובדיה קשקשתטויותאבגדהוזח",
        "One query word is real, the other matches nothing in the entire "
        "directory - the real word's candidates must still surface, not "
        "get poisoned by the garbage word.",
    ),
    (
        "single-word query stays a broad partial search",
        ALL_CLIENTS,
        [C_DAVID_DECOY_PREFIX, C_DAVID_DECOY_FIRSTWORD],
        "דוד",
        "A bare single word is existing app policy: broad partial search, "
        "never flagged exact by this algorithm even if it matches only one "
        "or two clients.",
    ),
    (
        "single-word query, globally unique prefix, still not exact",
        ALL_CLIENTS, [C_ZUR], "זהבית",
        "Even when a single word happens to be globally unique, this "
        "algorithm still doesn't call it exact (single words are out of "
        "scope for exactness here, by existing design elsewhere in the app).",
    ),
    (
        "reordered 2-word real pair forces the loop, not Step 0",
        ALL_CLIENTS, [C_WEISS, C_WEISSMAN], "וייסמן אורי",
        "Reordering means Step 0's whole-string check can't fire - proves "
        "the word-by-word loop itself resolves it, not just the fast path. "
        "Both real 'אורי X' clients present, for real disambiguation "
        "pressure on the shared first name.",
    ),
    (
        "three-word exact match, fully reordered",
        ALL_CLIENTS, [C_THREEWORD], "אביטן שגיא דן",
        "The real 3-word target client, queried in a totally different "
        "word order - still resolves exactly.",
    ),
    (
        "three-word query, one word is garbled",
        ALL_CLIENTS, [C_THREEWORD], "אביטן דן שגיאסטן",
        "Two of three words match the real target exactly; the third is "
        "close but wrong - must not be treated as exact.",
    ),
    (
        "empty query",
        ALL_CLIENTS, [], "",
        "Degenerate input - must not crash, must resolve to 'not found'.",
    ),
    (
        "whitespace-only query",
        ALL_CLIENTS, [], "   ",
        "Same as empty after trimming - must not crash.",
    ),
    (
        "repeated word in query",
        ALL_CLIENTS, [C_OVADIA], "עובדיה עובדיה פרלמן",
        "Querying the same word twice must not silently collapse to the "
        "2-word exact match - bag-of-words equality, not set equality.",
    ),
    (
        "candidate deduped when discoverable via two different words",
        ALL_CLIENTS,
        [C_DAVID_DECOY_PREFIX, C_DAVID_DECOY_LASTWORD],
        "דוד אבו זכריה",
        "'דודו אבו זכרי' is discoverable via BOTH 'דוד' and 'אבו' "
        "independently - must appear once in the candidate list, not twice.",
    ),
]

print(f"ONE fixture for every scenario below: {len(NAMED)} named clients + {len(NOISE)} "
      f"realistic random-noise clients (e.g. {NOISE[0].name!r}, {NOISE[1].name!r}, "
      f"{NOISE[2].name!r}, ...) = {len(ALL_CLIENTS)} total, always all present together. "
      f"'stored (relevant)' below shows only which named client(s) each row is actually "
      f"about - not the full 314-client list.\n")

for label, clients, relevant, query, purpose in SCENARIOS:
    m = FakeMorning(clients)
    result = resolve_client(m, query)
    relevant_str = ", ".join(f'"{c.name}"' for c in relevant) if relevant else "(none - pure noise pool)"
    if result.is_exact:
        outcome = f'EXACT -> "{result.exact.name}"'
    elif result.candidates:
        names = ", ".join(f'"{c.name}"' for c in result.candidates)
        outcome = f"CANDIDATES ({len(result.candidates)}) -> [{names}]"
    else:
        outcome = "NOTHING (not found)"
    print(f"### {label}")
    print(f"  tests:            {purpose}")
    print(f"  stored (relevant): {relevant_str}")
    print(f'  query:             "{query}"')
    print(f"  result:            {outcome}")
    print()
