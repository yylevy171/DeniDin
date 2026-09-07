"""Unit-test-the-hell-out-of-it suite for client_resolution_prototype.py,
per explicit user instruction: no touching real app code until this
algorithm is proven against a battery of hand-picked scenarios, including
the two gotchas the user specifically raised (word-order independence /
"Vavid Babu Zikri" discoverable only via one word; "Davinci" needing the
FULL query word checked, not just however many letters got it to unique).
"""
from client_resolution_prototype import Client, FakeMorning, resolve_client


# ============================================================================
# Fixture - deliberately includes near-miss/lookalike names to stress the
# algorithm, not just the "one obviously right answer" cases.
# ============================================================================
def _clients():
    return [
        Client("1", "David Abu Zikri"),
        Client("2", "Vavid Babu Zikri"),
        Client("3", "David Cohen"),
        Client("4", "Davinci Abu Zikri"),
        Client("5", "Test Client International"),
        Client("6", "Zehavit Zur"),
        Client("7", "Carmeli Dudi"),
        Client("8", "Yaron Levy"),
        Client("9", "Tech Solutions Alpha"),
        Client("10", "Tech Solutions Beta"),
    ]


def morning():
    return FakeMorning(_clients())


# ============================================================================
# Exact matches
# ============================================================================
def test_exact_multiword_in_order_via_step0():
    m = morning()
    result = resolve_client(m, "David Abu Zikri")
    assert result.is_exact
    assert result.exact.id == "1"
    assert result.candidates == []


def test_exact_multiword_case_insensitive():
    m = morning()
    result = resolve_client(m, "david abu zikri")
    assert result.is_exact
    assert result.exact.id == "1"


def test_exact_prefix_of_longer_stored_name_is_not_exact():
    """'Test Client' is a genuine prefix of 'Test Client International' but
    is NOT the same name - must not be treated as exact."""
    m = morning()
    result = resolve_client(m, "Test Client")
    assert not result.is_exact


def test_exact_multiword_out_of_order():
    """The core word-order-independence requirement: querying with the
    query's OWN word order (not the stored order) must still resolve
    exactly, and must do so by intersecting word-by-word in QUERY order,
    not by assuming positional correspondence."""
    m = morning()
    result = resolve_client(m, "Zikri David Abu")
    assert result.is_exact
    assert result.exact.id == "1"


def test_exact_multiword_out_of_order_different_permutation():
    m = morning()
    result = resolve_client(m, "Abu Zikri David")
    assert result.is_exact
    assert result.exact.id == "1"


# ============================================================================
# Non-exact single-candidate cases (T1/T2 shapes from the real bugfix)
# ============================================================================
def test_t1_letter_added_beyond_stored_word():
    """Query word longer than the real stored word ('Zuron' vs stored
    'Zur') - Step 0 can't even find it (stored is shorter than query,
    can't be a prefix of it)."""
    m = morning()
    result = resolve_client(m, "Zehavit Zuron")
    assert not result.is_exact
    assert result.is_single_non_exact
    assert result.candidates[0].id == "6"


def test_t2_letter_removed_from_stored_word():
    """Query word shorter than the real stored word ('Dud' vs stored
    'Dudi') - Step 0 DOES find a whole-string prefix match, but it isn't
    word-for-word equal, so must not be treated as exact."""
    m = morning()
    result = resolve_client(m, "Carmeli Dud")
    assert not result.is_exact
    assert result.is_single_non_exact
    assert result.candidates[0].id == "7"


def test_davinci_gotcha_unique_early_prefix_is_not_automatically_exact():
    """A single client (id 4, 'Davinci Abu Zikri') is briefly unique at a
    SHORT shared prefix of 'David' vs 'Davinci' - must be checked against
    the FULL query word ('David'), not just whatever prefix length
    happened to make it unique. Query 'David Abu Zikri' targets id 1, but
    id 1 is removed from this fixture so only the lookalike exists."""
    clients = [c for c in _clients() if c.id != "1"]  # remove the real exact match
    m = FakeMorning(clients)
    result = resolve_client(m, "David Abu Zikri")
    assert not result.is_exact
    # id 4 ("Davinci Abu Zikri") must show up as a candidate (it's the
    # closest lookalike) but never as a false exact match.
    assert any(c.id == "4" for c in result.candidates)


# ============================================================================
# The "Vavid Babu Zikri" discoverability gotcha
# ============================================================================
def test_candidate_only_discoverable_via_one_specific_word():
    """id 2 ('Vavid Babu Zikri') shares NO prefix with query words 'David'
    or 'Abu' at all - only 'Zikri' (searched independently) can ever
    surface it. Remove id 1 so nothing resolves exactly, forcing the fallback pass (no Step 0 exact match)."""
    clients = [c for c in _clients() if c.id != "1"]
    m = FakeMorning(clients)
    result = resolve_client(m, "David Abu Zikri")
    assert not result.is_exact
    candidate_ids = {c.id for c in result.candidates}
    assert "2" in candidate_ids, f"Vavid Babu Zikri (id 2) must be discoverable via 'Zikri' alone: {candidate_ids}"
    # id 3 (David Cohen) and id 4 (Davinci Abu Zikri) should also surface -
    # each discoverable via a different single word ('David' and 'Abu'/'Zikri' respectively).
    assert "3" in candidate_ids
    assert "4" in candidate_ids


def test_candidate_word_search_returns_multiple_not_just_unique():
    """If a single query word matches MORE than one client on its own
    (e.g. both id 2 and id 4 share the exact word 'Zikri'), ALL of them
    belong in the candidate list - discovery must not require per-word
    uniqueness - only the intersected exactness chain requires that."""
    clients = [c for c in _clients() if c.id not in ("1", "3")]  # isolate the "Zikri" word ambiguity
    m = FakeMorning(clients)
    result = resolve_client(m, "David Abu Zikri")
    candidate_ids = {c.id for c in result.candidates}
    assert {"2", "4"} <= candidate_ids


# ============================================================================
# Genuinely ambiguous (no single word, in any order, ever disambiguates)
# ============================================================================
def test_ambiguous_when_both_words_shared_by_multiple_clients():
    m = morning()
    result = resolve_client(m, "Tech Solutions")
    assert not result.is_exact
    assert result.is_ambiguous
    candidate_ids = {c.id for c in result.candidates}
    assert candidate_ids == {"9", "10"}


def test_ambiguous_candidate_query_extended_still_resolves_exactly():
    """Once enough of the query is given to disambiguate, it must resolve
    exactly rather than staying stuck in the ambiguous bucket."""
    m = morning()
    result = resolve_client(m, "Tech Solutions Alpha")
    assert result.is_exact
    assert result.exact.id == "9"


# ============================================================================
# Not found
# ============================================================================
def test_not_found_zero_candidates():
    m = morning()
    result = resolve_client(m, "Nonexistent Person Entirely")
    assert not result.is_exact
    assert result.is_not_found


def test_not_found_one_real_word_one_garbage_word():
    """One query word matches real clients, the other matches nothing at
    all anywhere - the intersected chain dies on the garbage word (rule c),
    but candidate discovery is independent per word (unconstrained), so a
    garbage word contributing nothing doesn't poison a real word's
    contribution."""
    m = morning()
    result = resolve_client(m, "David Zzzznonexistentzzz")
    assert not result.is_exact
    candidate_ids = {c.id for c in result.candidates}
    assert "1" in candidate_ids or "3" in candidate_ids or "4" in candidate_ids


# ============================================================================
# Single-word queries (left as plain broad search, not this algorithm's
# main concern, per existing app policy elsewhere - just checking it
# doesn't crash and behaves sanely)
# ============================================================================
def test_single_word_query_never_claims_exact_via_this_path():
    m = morning()
    result = resolve_client(m, "David")
    assert not result.is_exact  # ambiguous prefix (id 1, 3) - correctly left alone


def test_single_word_query_unique_prefix_still_not_flagged_exact():
    """Single-word queries are explicitly out of scope for the 'exact'
    determination in this algorithm (existing app policy: a bare word is a
    partial search, not a specific full-name lookup) - even if it happens
    to be globally unique, this path doesn't call it exact."""
    m = morning()
    result = resolve_client(m, "Zehavit")
    assert not result.is_exact
    assert any(c.id == "6" for c in result.candidates)


# ============================================================================
# Step 0 short-circuit sanity: an exact match should resolve without ever
# falling through to the expensive per-letter algorithm.
# ============================================================================
def test_exact_match_short_circuits_before_expensive_phases():
    m = morning()
    resolve_client(m, "David Abu Zikri")
    # Step 0 (1 call) + Step Final (1 call) = 2 calls total, never touching
    # search_word_prefix (the single-pass loop) at all.
    assert all(call.startswith("whole:") for call in m.call_log)
    assert len(m.call_log) == 2


def test_non_exact_case_does_use_word_level_search():
    m = morning()
    resolve_client(m, "Zehavit Zuron")
    assert any(call.startswith("word:") for call in m.call_log)


# ============================================================================
# Additional stress cases
# ============================================================================
def test_ambiguous_pair_disambiguated_via_reordered_query_through_the_loop():
    """Forces the word-by-word loop specifically (not Step 0): reordered query means the
    whole-string prefix check fails immediately, so this must resolve via
    the word-by-word intersecting pass, not the fast path."""
    m = morning()
    result = resolve_client(m, "Alpha Tech Solutions")
    assert result.is_exact
    assert result.exact.id == "9"
    assert any(call.startswith("word:") for call in m.call_log), "must have gone through the word-by-word loop, not Step 0 alone"


def test_three_word_query_exact_out_of_order():
    m = morning()
    result = resolve_client(m, "Abu David Zikri")
    assert result.is_exact
    assert result.exact.id == "1"


def test_three_word_query_one_word_wrong_is_not_exact():
    m = morning()
    result = resolve_client(m, "Abu David Cohenberg")  # "Cohenberg" matches nobody
    assert not result.is_exact


def test_empty_query_is_not_found_not_a_crash():
    m = morning()
    result = resolve_client(m, "")
    assert result.is_not_found


def test_whitespace_only_query_is_not_found():
    m = morning()
    result = resolve_client(m, "   ")
    assert result.is_not_found


def test_repeated_word_in_query_bag_compare_is_honest():
    """A pathological but real possibility: querying the same word twice.
    Bag-equality must not silently collapse duplicates."""
    m = morning()
    result = resolve_client(m, "David David Cohen")
    assert not result.is_exact  # real client is "David Cohen" (2 words), not a 3-word bag


def test_candidate_list_deduped_when_multiple_words_point_to_same_client():
    """id 1 would surface via both 'David' and 'Zikri' independently if it
    were still in the fixture and query didn't resolve exactly - must not
    appear twice in the candidate list."""
    clients = [c for c in _clients() if c.id != "3"]  # remove David Cohen to keep "David" less noisy
    m = FakeMorning(clients)
    # Force non-exact by asking for a name close to, but not equal to, id 1.
    result = resolve_client(m, "David Abu Zikristan")
    candidate_ids = [c.id for c in result.candidates]
    assert len(candidate_ids) == len(set(candidate_ids)), f"duplicate candidates: {candidate_ids}"
