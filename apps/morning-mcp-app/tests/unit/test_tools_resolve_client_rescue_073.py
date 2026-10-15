"""bugfix-073: Levenshtein rescue hatch in `resolve_client_by_name`.

Production incident ("מור פלומבו" -> stored "מור פלימבו", distance 1): the
first word "מור" matched 15 clients, over `_COMMON_WORD_DISCOVERY_CAP`, so all
15 (the real client included) were discarded; the intersected chain then died
at "פלו" because of the typo. Result: zero candidates for a distance-1 match.

A candidate whose full name is within the strict distance of the full query
must survive both of those discards. Candidates that are far from the query
keep being discarded as before (the common-word cap stays).

Fake MorningClient = third-party API boundary (CONSTITUTION §I/§V). The fake
matches a prefix of ANY word in the stored name, like Morning's own search.
"""
from denidin_mcp_morning import tools


class _WordPrefixFakeClient:
    def __init__(self, names):
        self._records = [
            {"id": f"c-{i}", "name": name, "active": True, "taxId": "308253681", "phone": "0527384938", "emails": []}
            for i, name in enumerate(names)
        ]
        self.search_clients_calls = []

    def search_clients(self, payload):
        self.search_clients_calls.append(payload)
        query = payload.get("name", "")
        items = [r for r in self._records if any(w.startswith(query) for w in r["name"].split())]
        return {"items": items, "total": len(items), "page": 1, "pages": 1}


_TARGET = "מור פלימבו"
_FILLERS = [f"מור לוי{chr(0x5d0 + i)}" for i in range(14)]  # 14 more "מור ..." -> "מור" matches 15
_PEL_OTHERS = ["דנה פלד", "יוסי פלג"]  # "פל" matches several clients; "פלו" then matches none


def test_distance_one_match_survives_the_common_word_cap_and_chain_death():
    client = _WordPrefixFakeClient(_FILLERS + _PEL_OTHERS + [_TARGET])

    exact, candidates = tools.resolve_client_by_name(client, "מור פלומבו")

    assert exact is None
    names = [c.name for c in candidates]
    assert _TARGET in names
    assert names[0] == _TARGET  # closest first


def test_far_candidates_of_a_common_word_are_still_discarded():
    client = _WordPrefixFakeClient(_FILLERS + _PEL_OTHERS + [_TARGET])

    _, candidates = tools.resolve_client_by_name(client, "מור פלומבו")

    names = [c.name for c in candidates]
    assert not any(name in names for name in _FILLERS)


def test_rescue_does_not_turn_a_near_miss_into_an_exact_match():
    client = _WordPrefixFakeClient(_FILLERS + _PEL_OTHERS + [_TARGET])

    exact, _ = tools.resolve_client_by_name(client, "מור פלומבו")

    assert exact is None  # the operator must still confirm a typo'd name
