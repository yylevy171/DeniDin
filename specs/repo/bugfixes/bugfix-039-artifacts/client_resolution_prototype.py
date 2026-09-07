"""Standalone prototype of the new client-name-resolution algorithm
(bugfix-039, round 3 - user-specified deterministic word-by-word/letter-by-
letter matching, replacing _resolve_client_by_name_words entirely).

NOT connected to the real app or real Morning API - pure in-memory model,
built to nail the algorithm down before touching apps/morning-mcp-app/.

ONE mechanism, ONE pass. A single `for word in words:` loop, in query
order. For each word, two things happen together, in the same iteration
(not two separate sweeps over the word list):

1. The running INTERSECTED pool (started unconstrained for the first
   word) is narrowed by growing this word's own prefix one letter at a
   time, stopping the moment it's unique or the word runs out of letters.
   This is what can conclude an EXACT MATCH (checking the unique
   candidate's full stored words against every query word, order-
   independent) or kill the chain (0 results - rule c) or carry an
   ambiguous pool forward to the next word (rule d).
2. Independently of that pool, this SAME word is also grown on its own,
   unconstrained, to see what it alone resolves to - because a real
   candidate can be invisible to the intersected chain (e.g. "Vavid Babu
   Zikri" never survives intersecting with "David"'s or "Abu"'s pool, and
   only "Zikri" alone would ever surface it) yet still be exactly the kind
   of client worth offering as a "did you mean this?" option. Whatever
   this word alone narrows to (one candidate, or several that never split
   apart on this word) is added to the running candidate set.

The loop keeps going through every word regardless of whether the
intersected chain already died, specifically so every word still gets its
turn at independent candidate discovery. It only stops early the moment
an exact match is confirmed (nothing left to discover after that).

Growth never needs anything beyond growth: it naturally covers "letter
added beyond stored" too, because it stops at whatever prefix length
first goes unique (e.g. "Zur", 3 letters) and never grows far enough to
overshoot into a 0-match prefix ("Zuro"/"Zuron").

Models the one relevant real Morning /clients/search behavior used
throughout: per-word/token prefix match (a query is checked against every
individual word of a stored name, matching if any of them starts with
it). Step 0 additionally needs the whole-string-from-start variant
(checked against the full stored name as one string) - kept separate
since it's a genuinely different real endpoint behavior.

STEP 0 (cheap fast path): whole-string search for the verbatim query. If
that resolves to exactly one client AND it's word-for-word identical to
the query (order-independent), that's an immediate exact match - covers
the common "already exact" case in one call, before the loop above ever
runs.

STEP FINAL: once an exact match is concluded (via Step 0 or the loop), do
one more whole-string lookup on the resolved name as a fresh-data
confirmation before treating it as final.

CANDIDATE ORDERING: the candidate list is never filtered (user decision,
2026-08-11 - independent per-word discovery surfacing an unrelated client
that only shares one common word, e.g. searching for "X דוד" also
surfacing an unrelated "דוד Y" that shares nothing else, is intentional,
not a bug - a future refinement may special-case very common Hebrew
name-part patterns like the "בן"/"כהן"/"לוי" patronymic/surname prefixes,
but that's explicitly deferred, not part of this algorithm). What IS done:
candidates are sorted by Levenshtein distance from the query (closest
first), so on a long list the most plausible read is always on top.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set


def _levenshtein(a: str, b: str) -> int:
    """Standard edit distance (insertions/deletions/substitutions, unit
    cost) - no external dependency, this project has none for it."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous_row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current_row = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            current_row.append(
                min(
                    previous_row[j] + 1,  # deletion
                    current_row[j - 1] + 1,  # insertion
                    previous_row[j - 1] + cost,  # substitution
                )
            )
        previous_row = current_row
    return previous_row[-1]


def _normalize(s: str) -> str:
    return s.strip().casefold()


def _words(name: str) -> List[str]:
    return [_normalize(w) for w in name.split() if w]


@dataclass(frozen=True)
class Client:
    id: str
    name: str


@dataclass
class Resolution:
    """Mirrors the real ClientResolution contract, extended: `candidates`
    is a small curated list gathered during the same pass, not a blunt
    "everything that matched the raw substring" dump."""

    exact: Optional[Client]
    candidates: List[Client]

    @property
    def is_exact(self) -> bool:
        return self.exact is not None

    @property
    def is_ambiguous(self) -> bool:
        return self.exact is None and len(self.candidates) > 1

    @property
    def is_not_found(self) -> bool:
        return self.exact is None and len(self.candidates) == 0

    @property
    def is_single_non_exact(self) -> bool:
        return self.exact is None and len(self.candidates) == 1


class FakeMorning:
    """In-memory stand-in for Morning's /clients/search."""

    def __init__(self, clients: List[Client]):
        self.clients = clients
        self.call_log: List[str] = []  # every search string issued, for call-count assertions

    def search_whole_string_prefix(self, query: str) -> List[Client]:
        self.call_log.append(f"whole:{query}")
        q = _normalize(query)
        return [c for c in self.clients if _normalize(c.name).startswith(q)]

    def search_word_prefix(self, prefix: str) -> List[Client]:
        self.call_log.append(f"word:{prefix}")
        p = _normalize(prefix)
        return [c for c in self.clients if any(w.startswith(p) for w in _words(c.name))]


def _bag_equal(query: str, candidate_name: str) -> bool:
    """Word-order-independent exact match: same set of words (as a
    multiset - repeated words matter), case-insensitive."""
    return sorted(_words(query)) == sorted(_words(candidate_name))


_COMMON_WORD_DISCOVERY_CAP = 10  # user decision, 2026-08-11 - see resolve_client's loop


def _grow_word(morning: FakeMorning, word: str, pool_ids: Optional[Set[str]]) -> Dict[str, Client]:
    """THE one search mechanism: grow `word`'s own prefix one letter at a
    time (intersected with `pool_ids` if given - None means unconstrained),
    stopping the moment the result narrows to exactly 1, or once the
    word's letters run out, or immediately on 0. Returns whatever the
    final {client_id: Client} state is at the point it stopped.

    Starts at 2 letters, not 1 (a single letter always matches too broadly
    to usefully narrow anything - real sandbox observed: "D" alone -> 1479
    matches); `word` shorter than 2 letters returns {} outright.

    Every step filters against the SAME original `pool_ids` throughout -
    never against a running/self-accumulated set from this word's own
    previous letter. Against the REAL Morning API this matters a lot: it
    paginates (25 items/page observed even with a true total in the
    thousands), so an earlier letter's own returned page is an arbitrary,
    non-representative sample - filtering a later, more specific letter's
    results against that sample would silently discard real candidates
    that just weren't on that earlier page (a real bug this prototype
    itself had and never caught, because FakeMorning has no pagination -
    only surfaced testing the real implementation against the live
    sandbox, 2026-08-11). Growing the prefix is already inherently
    narrowing via real prefix-search semantics; no client-side
    re-intersection against a previous page is needed or correct.
    """
    if len(word) < 2:
        return {}
    prefix = word[:2]
    results = {c.id: c for c in morning.search_word_prefix(prefix)}
    if pool_ids is not None:
        results = {cid: c for cid, c in results.items() if cid in pool_ids}
    if len(results) <= 1:
        return results
    for ch in word[2:]:
        prefix += ch
        results = {c.id: c for c in morning.search_word_prefix(prefix)}
        if pool_ids is not None:
            results = {cid: c for cid, c in results.items() if cid in pool_ids}
        if len(results) <= 1:
            return results  # 0 -> dead end; 1 -> unique, no benefit growing further
    return results  # word's own letters exhausted, still >1


def resolve_client(morning: FakeMorning, query: str) -> Resolution:
    words = [w for w in query.split() if w]
    if not words:
        return Resolution(exact=None, candidates=[])

    # STEP 0
    step0 = morning.search_whole_string_prefix(query)
    if len(step0) == 1 and _bag_equal(query, step0[0].name):
        return _step_final(morning, step0[0])

    if len(words) < 2:
        # Single-word queries: this algorithm is a multi-word mechanism;
        # single words stay a plain word search (existing app behavior
        # elsewhere leaves these as broad partial searches, unchanged).
        candidates = list({c.id: c for c in morning.search_word_prefix(words[0])}.values())
        return Resolution(exact=None, candidates=_by_distance(query, candidates))

    # SINGLE PASS over the words - exactness tracking and candidate
    # discovery both happen per word, in the same loop.
    pool_ids: Optional[Set[str]] = None
    chain_dead = False
    candidates: Dict[str, Client] = {}

    for word in words:
        if len(word) < 2:
            continue  # a 1-letter word can never usefully narrow anything

        # Independent candidate discovery for THIS word alone, regardless
        # of what the intersected chain has done so far.
        discovered = _grow_word(morning, word, None)
        if len(discovered) <= _COMMON_WORD_DISCOVERY_CAP:
            candidates.update(discovered)
        # else: this word alone matched more than _COMMON_WORD_DISCOVERY_CAP
        # real clients even using its full length (never narrowed) - a
        # common Hebrew name-part ("בן", "כהן", "לוי", "דוד", etc.) is
        # exactly this shape, real but not a useful identifying signal on
        # its own. Only applies to discovery - the intersecting chain
        # below still uses this word normally, since a common word CAN
        # still correctly narrow to an exact match combined with another
        # word (e.g. "בן" + "גוריון").

        if chain_dead:
            continue

        intersected = _grow_word(morning, word, pool_ids)
        if len(intersected) == 0:
            chain_dead = True  # rule c - this ordering can't reach an exact match
            continue
        if len(intersected) == 1:
            (candidate,) = intersected.values()
            if _bag_equal(query, candidate.name):
                return _step_final(morning, candidate)  # rule a.3 - EXACT MATCH, done
            chain_dead = True  # proven terminal (see module docstring), not exact
            continue
        pool_ids = set(intersected.keys())  # rule d - carry the ambiguous pool to the next word

    return Resolution(exact=None, candidates=_by_distance(query, list(candidates.values())))


def _by_distance(query: str, candidates: List[Client]) -> List[Client]:
    """Closest-to-the-query first (Levenshtein, normalized) - never
    filters anything out, only orders it (see module docstring)."""
    q = _normalize(query)
    return sorted(candidates, key=lambda c: _levenshtein(q, _normalize(c.name)))


def _step_final(morning: FakeMorning, resolved: Client) -> Resolution:
    """Fresh-data re-confirmation once exactness is concluded."""
    confirm = morning.search_whole_string_prefix(resolved.name)
    final = confirm[0] if len(confirm) == 1 else resolved
    return Resolution(exact=final, candidates=[])
