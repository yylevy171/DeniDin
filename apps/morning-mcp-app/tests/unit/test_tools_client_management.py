"""Tests for feature 026 (client management): the name-resolution helper
shared by get_client_details/update_client, and the email/phone
validation/normalization helpers used by add_client/update_client.

Uses a fake MorningClient (dependency-injected, matching the real
add_client/search_clients contracts) — this mocks a third-party API
boundary, not an internal component (CONSTITUTION.md §I/§V).
"""
import json

import pytest

from denidin_mcp_morning import tools


class _FakeMorningClient:
    """Records calls and returns pre-set responses — stands in for the
    MorningClient network boundary."""

    def __init__(
        self,
        search_clients_response=None,
        search_clients_responses=None,
        add_client_response=None,
        update_client_response=None,
    ):
        self._search_clients_response = search_clients_response or {"items": [], "total": 0}
        # Optional list of responses, one per successive search_clients call -
        # lets pagination tests return a different page each call. Takes
        # precedence over the single fixed response above when given.
        self._search_clients_responses = search_clients_responses
        self._add_client_response = add_client_response or {"id": "new-client-1", "name": "New Client"}
        self._update_client_response = update_client_response or {"id": "c-1"}
        self.search_clients_calls = []
        self.add_client_calls = []
        self.update_client_calls = []

    def search_clients(self, payload):
        self.search_clients_calls.append(payload)
        if self._search_clients_responses is not None:
            return self._search_clients_responses[len(self.search_clients_calls) - 1]
        return self._search_clients_response

    def add_client(self, payload):
        self.add_client_calls.append(payload)
        return self._add_client_response

    def update_client(self, client_id, payload):
        self.update_client_calls.append((client_id, payload))
        return self._update_client_response


def _client_record(client_id="c-1", name="Tech Solutions", phone="0527384938", tax_id="308253681"):
    """A raw Morning /clients/search item, matching the real shape confirmed
    via the Postman collection (name/phone/taxId/emails, id, etc.)."""
    return {
        "id": client_id,
        "name": name,
        "active": True,
        "taxId": tax_id,
        "phone": phone,
        "emails": [],
    }


# --- _resolve_client_by_name (REQ-CLIENT-003/007) ---


def test_resolve_client_by_name_zero_matches():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    resolved, candidates = tools._resolve_client_by_name(client, "Nonexistent Client")

    assert resolved is None
    assert candidates == []
    assert client.search_clients_calls == [{"name": "Nonexistent Client"}]


def test_resolve_client_by_name_single_match():
    record = _client_record()
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    resolved, candidates = tools._resolve_client_by_name(client, "Tech Solutions")

    assert resolved is not None
    assert resolved.name == "Tech Solutions"
    assert resolved.id == "c-1"
    assert len(candidates) == 1
    assert candidates[0].id == "c-1"


def test_resolve_client_by_name_multiple_matches():
    record_a = _client_record(client_id="c-1", name="Tech Solutions A")
    record_b = _client_record(client_id="c-2", name="Tech Solutions B")
    client = _FakeMorningClient(search_clients_response={"items": [record_a, record_b], "total": 2})

    resolved, candidates = tools._resolve_client_by_name(client, "Tech Solutions")

    assert resolved is None
    assert [c.id for c in candidates] == ["c-1", "c-2"]


def test_resolve_client_by_name_only_filters_by_name():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    tools._resolve_client_by_name(client, "Some Name")

    assert client.search_clients_calls == [{"name": "Some Name"}]


# --- _validate_email (REQ-CLIENT-015) ---


def test_validate_email_accepts_valid_address():
    assert tools._validate_email("tech@example.com") == "tech@example.com"


@pytest.mark.parametrize("bad_email", ["not-an-email", "missing-domain@", "@no-local-part.com", ""])
def test_validate_email_rejects_malformed_address(bad_email):
    with pytest.raises(ValueError):
        tools._validate_email(bad_email)


# --- _normalize_israeli_phone (REQ-CLIENT-016) ---


@pytest.mark.parametrize(
    "raw_phone",
    [
        "+972501234567",
        "972501234567",
        "0501234567",
        "050-123-4567",
        "050 123 4567",
        "(050) 123-4567",
    ],
)
def test_normalize_israeli_phone_mobile_variants(raw_phone):
    assert tools._normalize_israeli_phone(raw_phone) == "050-1234567"


def test_normalize_israeli_phone_landline_variant():
    assert tools._normalize_israeli_phone("021234567") == "02-1234567"


@pytest.mark.parametrize(
    "raw_phone",
    ["50-822-5928", "508225928", "50 822 5928", "+972-50-822-5928"],
)
def test_normalize_israeli_phone_repairs_mobile_missing_its_leading_zero(raw_phone):
    """bugfix-032: 9 digits starting with 5 is an unambiguous mobile number."""
    assert tools._normalize_israeli_phone(raw_phone) == "050-8225928"


def test_normalize_israeli_phone_repairs_voip_missing_its_leading_zero():
    assert tools._normalize_israeli_phone("772345678") == "077-2345678"


def test_normalize_israeli_phone_repairs_landline_missing_its_leading_zero():
    assert tools._normalize_israeli_phone("3-123-4567") == "03-1234567"


@pytest.mark.parametrize(
    "ambiguous_phone",
    [
        "108225928",  # 9 digits, prefix 1 is not a mobile/VoIP prefix
        "50822592",  # 8 digits starting with 5 - not a landline prefix
        "5082259281",  # 10 digits without a leading zero
        "312345",  # too short to be a landline
    ],
)
def test_normalize_israeli_phone_still_rejects_ambiguous_missing_zero(ambiguous_phone):
    with pytest.raises(ValueError):
        tools._normalize_israeli_phone(ambiguous_phone)


@pytest.mark.parametrize(
    "bad_phone",
    [
        "12345",  # too few digits
        "05012345678901",  # too many digits
        "+1234567890",  # non-Israeli country code
        "not-a-phone",
    ],
)
def test_normalize_israeli_phone_rejects_implausible_input(bad_phone):
    with pytest.raises(ValueError):
        tools._normalize_israeli_phone(bad_phone)


# --- list_clients (US1) ---


def test_list_clients_zero_clients_returns_friendly_message():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    result = tools.list_clients(client)

    assert isinstance(result, str)
    payload = json.loads(result)
    assert payload["count"] == 0
    assert payload["clients"] == []
    assert client.search_clients_calls == [{}]


def test_list_clients_never_includes_raw_client_id():
    record = _client_record(client_id="c-should-never-appear")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    result = tools.list_clients(client)

    assert "c-should-never-appear" not in result
    assert record["name"] in result


# --- get_client_details (US2) ---


def test_get_client_details_not_resolved_refuses_without_any_lookup():
    """Client-name-resolution architecture fix (2026-08-12, user decision):
    get_client_details no longer does its own fuzzy matching - it requires
    name_resolved=True (the caller must have already called
    resolve_client_name) and refuses immediately, with zero Morning calls,
    otherwise. Follow-up (2026-08-12): this is now a real raise, not
    ordinary refusal text - two outcomes only, succeed or raise."""
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNameNotResolvedError) as exc_info:
        tools.get_client_details(client, "Nonexistent Client XYZ")

    assert "resolve_client_name" in str(exc_info.value)
    assert client.search_clients_calls == []


def test_get_client_details_not_found_raises():
    """Unification (2026-08-12, user decision): get_client_details used to
    return a friendly string here, a different mechanism from every other
    client-resolving tool for the exact same situation - now it raises the
    same ClientNotFoundError, same as create_invoice/create_transaction_account/
    create_combo_document/update_client/list_invoices. Requires
    name_resolved=True (architecture fix, same date) - the caller must have
    already gone through resolve_client_name."""
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNotFoundError) as exc_info:
        tools.get_client_details(client, "Nonexistent Client XYZ", name_resolved=True)

    assert "לא נמצא" in str(exc_info.value) or "אין" in str(exc_info.value)


def test_get_client_details_ambiguous_with_name_resolved_raises_not_found():
    """Architecture fix (2026-08-12): get_client_details no longer discloses
    ambiguous candidates itself - that's resolve_client_name's job now (see
    test_tools_resolve_client_name.py). A caller asserting name_resolved=True
    against a name that's still ambiguous is a contract violation, and
    collapses to the same ClientNotFoundError as any other non-exact
    result under exact-only mode."""
    record_a = _client_record(client_id="c-1", name="Tech Solutions A", tax_id="308253681")
    record_b = _client_record(client_id="c-2", name="Tech Solutions B", tax_id="111111111")
    client = _FakeMorningClient(search_clients_response={"items": [record_a, record_b], "total": 2})

    with pytest.raises(tools.ClientNotFoundError):
        tools.get_client_details(client, "Tech Solutions", name_resolved=True)


# --- add_client (US3) - reworked: name/email/phone all required, no address ---


def test_add_client_missing_email_is_a_type_error():
    """email has no default - omitting it entirely is a Python-level required-
    argument error, not something tools.py needs to check itself. This is the
    enforcement mechanism behind REQ-CLIENT-012 (the tool schema marks it
    required, so the model can't call the tool without it)."""
    client = _FakeMorningClient()
    with pytest.raises(TypeError):
        tools.add_client(client, name="Tech Solutions", phone="050-1234567")


def test_add_client_missing_phone_is_a_type_error():
    client = _FakeMorningClient()
    with pytest.raises(TypeError):
        tools.add_client(client, name="Tech Solutions", email="tech@example.com")


def test_add_client_rejects_malformed_email_before_network_call():
    client = _FakeMorningClient()
    with pytest.raises(ValueError):
        tools.add_client(client, name="Tech Solutions", email="not-an-email", phone="050-1234567")
    assert client.add_client_calls == []


def test_add_client_rejects_implausible_phone_before_network_call():
    client = _FakeMorningClient()
    with pytest.raises(ValueError):
        tools.add_client(client, name="Tech Solutions", email="tech@example.com", phone="123")
    assert client.add_client_calls == []


def test_add_client_normalizes_phone_before_sending():
    client = _FakeMorningClient()

    tools.add_client(client, name="Tech Solutions", email="tech@example.com", phone="+972501234567")

    assert client.add_client_calls[0]["phone"] == "050-1234567"


def test_add_client_no_longer_accepts_address():
    client = _FakeMorningClient()
    with pytest.raises(TypeError):
        tools.add_client(
            client,
            name="Tech Solutions",
            email="tech@example.com",
            phone="050-1234567",
            address="Some Street 1",
        )


def test_add_client_confirmation_never_includes_client_id():
    client = _FakeMorningClient(add_client_response={"id": "should-never-appear", "name": "Tech Solutions"})

    result = tools.add_client(client, name="Tech Solutions", email="tech@example.com", phone="050-1234567")

    assert "should-never-appear" not in result
    assert "Tech Solutions" in result


def test_add_client_tax_id_stays_optional():
    client = _FakeMorningClient()

    result = tools.add_client(client, name="Tech Solutions", email="tech@example.com", phone="050-1234567")

    assert "taxId" not in client.add_client_calls[0]
    assert isinstance(result, str)


# --- update_client (US4) ---


def test_update_client_rejects_no_fields_to_change():
    record = _client_record()
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    with pytest.raises(ValueError):
        tools.update_client(client, name="Tech Solutions")
    assert client.update_client_calls == []


def test_update_client_not_resolved_refuses_without_any_lookup():
    """Client-name-resolution architecture fix (2026-08-12, user decision):
    update_client requires name_resolved=True and refuses immediately, with
    zero Morning calls, otherwise - even before reaching the "at least one
    field to change" check, since name_resolved is checked once resolution
    is attempted (that check itself doesn't need resolution and still fires
    first regardless, see test_update_client_rejects_no_fields_to_change).
    Follow-up (2026-08-12): this is now a real raise, not ordinary refusal
    text - two outcomes only, succeed or raise."""
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNameNotResolvedError) as exc_info:
        tools.update_client(client, name="Nonexistent Client", email="new@example.com")

    assert "resolve_client_name" in str(exc_info.value)
    assert client.search_clients_calls == []
    assert client.update_client_calls == []


def test_update_client_not_found_raises():
    """bugfix-028 B4(c), applied to update_client via bugfix-039 round 2:
    a genuinely-not-found client raises ClientNotFoundError rather than
    returning a friendly string - the same silent-failure risk (an approved
    update that updates nothing, with no signal anywhere that it failed)
    applies here too. Requires name_resolved=True (architecture fix,
    2026-08-12) - the caller must have already gone through
    resolve_client_name."""
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    with pytest.raises(tools.ClientNotFoundError):
        tools.update_client(client, name="Nonexistent Client", email="new@example.com", name_resolved=True)

    assert client.update_client_calls == []


def test_update_client_ambiguous_with_name_resolved_raises_not_found():
    """Architecture fix (2026-08-12): update_client no longer discloses
    ambiguous candidates itself - that's resolve_client_name's job now. A
    caller asserting name_resolved=True against a name that's still
    ambiguous is a contract violation, and collapses to the same
    ClientNotFoundError as any other non-exact result under exact-only
    mode."""
    record_a = _client_record(client_id="c-1", name="Tech Solutions A")
    record_b = _client_record(client_id="c-2", name="Tech Solutions B")
    client = _FakeMorningClient(search_clients_response={"items": [record_a, record_b], "total": 2})

    with pytest.raises(tools.ClientNotFoundError):
        tools.update_client(client, name="Tech Solutions", email="new@example.com", name_resolved=True)

    assert client.update_client_calls == []


def test_update_client_rejects_malformed_email_before_network_call():
    record = _client_record()
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    with pytest.raises(ValueError):
        tools.update_client(client, name="Tech Solutions", email="not-an-email", name_resolved=True)
    assert client.update_client_calls == []


def test_update_client_rejects_implausible_phone_before_network_call():
    record = _client_record()
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    with pytest.raises(ValueError):
        tools.update_client(client, name="Tech Solutions", phone="123", name_resolved=True)
    assert client.update_client_calls == []


def test_update_client_normalizes_phone_before_sending():
    record = _client_record(client_id="c-1")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    tools.update_client(client, name="Tech Solutions", phone="+972501234567", name_resolved=True)

    client_id, payload = client.update_client_calls[0]
    assert client_id == "c-1"
    assert payload["phone"] == "050-1234567"


def test_update_client_builds_partial_payload_with_only_changed_fields():
    """A call updating only phone must never send name/email/taxId in the
    payload - the whole point of a partial PUT (research.md Decision 3)."""
    record = _client_record(client_id="c-1")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    tools.update_client(client, name="Tech Solutions", phone="050-1234567", name_resolved=True)

    client_id, payload = client.update_client_calls[0]
    assert client_id == "c-1"
    assert payload == {"phone": "050-1234567"}


def test_update_client_new_name_maps_to_name_field():
    """The `name` param resolves WHICH client; `new_name` is the value being
    changed - these must not be conflated in the payload."""
    record = _client_record(client_id="c-1", name="Tech Solutions")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    tools.update_client(client, name="Tech Solutions", new_name="Tech Solutions Ltd", name_resolved=True)

    client_id, payload = client.update_client_calls[0]
    assert client_id == "c-1"
    assert payload == {"name": "Tech Solutions Ltd"}


def test_update_client_tax_id_editable_like_any_other_field():
    record = _client_record(client_id="c-1")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    tools.update_client(client, name="Tech Solutions", tax_id="308253681", name_resolved=True)

    client_id, payload = client.update_client_calls[0]
    assert client_id == "c-1"
    assert payload == {"taxId": "308253681"}


def test_update_client_confirmation_never_includes_client_id():
    record = _client_record(client_id="should-never-appear")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    result = tools.update_client(client, name="Tech Solutions", phone="050-1234567", name_resolved=True)

    assert "should-never-appear" not in result


# --- _is_exact_name_match ---


def test_is_exact_name_match_identical():
    assert tools._is_exact_name_match("Tech Solutions", "Tech Solutions") is True


def test_is_exact_name_match_case_insensitive():
    assert tools._is_exact_name_match("Tech Solutions", "tech solutions") is True


def test_is_exact_name_match_whitespace_trimmed():
    assert tools._is_exact_name_match("Tech Solutions", "  Tech Solutions  ") is True


def test_is_exact_name_match_partial_reference_is_not_exact():
    assert tools._is_exact_name_match("Tech Solutions Ltd", "Tech Solutions") is False


# --- get_client_details requires an exact match once resolved (architecture fix, 2026-08-12) ---


def test_get_client_details_exact_match_uses_standard_phrasing():
    record = _client_record(name="Tech Solutions")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    payload = json.loads(tools.get_client_details(client, "Tech Solutions", name_resolved=True))

    assert payload["client"]["name"] == "Tech Solutions"
    assert payload["exact_match"] is True


def test_get_client_details_non_exact_match_with_name_resolved_raises_not_found():
    """Architecture fix (2026-08-12): get_client_details used to disclose
    which client it found on a non-exact match (research.md Decision, since
    it's read-only). That disclosure now happens in resolve_client_name
    instead (see test_resolve_client_name_non_exact_single_match_asks_for_
    confirmation) - get_client_details itself only ever accepts an exact
    match once name_resolved=True is asserted."""
    record = _client_record(name="Tech Solutions International")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    with pytest.raises(tools.ClientNotFoundError):
        tools.get_client_details(client, "Tech Solutions", name_resolved=True)


# --- update_client requires an exact match once resolved (architecture fix, 2026-08-12) ---


def test_update_client_exact_match_uses_standard_phrasing():
    record = _client_record(name="Tech Solutions")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    payload = json.loads(tools.update_client(client, name="Tech Solutions", phone="050-1234567", name_resolved=True))

    assert payload["status"] == "updated"
    assert payload["client"]["name"] == "Tech Solutions"


def test_update_client_non_exact_match_with_name_resolved_raises_not_found_and_updates_nothing():
    """Architecture fix (2026-08-12): update_client used to refuse with its
    own closed yes/no confirmation question on a non-exact single match
    (bugfix-039 round 2). That disclosure now happens in resolve_client_name
    instead - update_client itself only ever accepts an exact match once
    name_resolved=True is asserted, and a still-non-exact name under that
    assertion is a contract violation, not a normal disambiguation moment."""
    record = _client_record(name="Tech Solutions International")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    with pytest.raises(tools.ClientNotFoundError):
        tools.update_client(client, name="Tech Solutions", phone="050-1234567", name_resolved=True)

    assert client.update_client_calls == []


# --- list_clients: name filter + real pagination (REQ-CLIENT-001 fix) ---


def test_list_clients_passes_name_filter_to_search():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    tools.list_clients(client, name="Tech")

    assert client.search_clients_calls == [{"name": "Tech"}]


def test_list_clients_no_filter_sends_empty_payload():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    tools.list_clients(client)

    assert client.search_clients_calls == [{}]


def test_list_clients_under_cap_fetches_all_pages_internally():
    """total (25) is under the display cap (30) but spans 2 pages - the
    tool must fetch page 2 itself and return the complete list, never a
    partial page-1-only slice."""
    page_1_items = [_client_record(client_id=f"c-{i}", name=f"Client {i}") for i in range(20)]
    page_2_items = [_client_record(client_id=f"c-{i}", name=f"Client {i}") for i in range(20, 25)]
    client = _FakeMorningClient(
        search_clients_responses=[
            {"items": page_1_items, "total": 25, "page": 1, "pages": 2},
            {"items": page_2_items, "total": 25, "page": 2, "pages": 2},
        ]
    )

    result = tools.list_clients(client)

    assert len(client.search_clients_calls) == 2
    assert client.search_clients_calls[1] == {"page": 2}
    for i in range(25):
        assert f"Client {i}" in result


def test_list_clients_over_cap_reports_total_without_fetching_further_pages():
    client = _FakeMorningClient(
        search_clients_response={"items": [_client_record()] * 25, "total": 278, "page": 1, "pages": 12}
    )

    payload = json.loads(tools.list_clients(client))

    assert len(client.search_clients_calls) == 1  # never fetched page 2+
    assert payload["status"] == "too_many"
    assert payload["total"] == 278


# --- Quote-character spellings (bugfix-027) ---
#
# Morning stores a client's name exactly as typed - both the ASCII apostrophe
# ("מג'די", U+0027) and the Hebrew geresh ("מג׳די", U+05F3) occur in real data
# (likewise `"` U+0022 vs gershayim U+05F4) - and its search is sensitive to
# the exact character. Nothing rewrites a name any more: it is sent and stored
# as given, and a client SEARCH runs once per spelling and merges the hits.

_APOSTROPHE_NAME = "סידורוביץ'"  # ASCII apostrophe (U+0027)
_GERESH_NAME = "סידורוביץ׳"  # Hebrew geresh (U+05F3)
_QUOTE_NAME = 'בע"מ'  # ASCII double quote (U+0022)
_GERSHAYIM_NAME = "בע״מ"  # gershayim (U+05F4)


class _SpellingAwareClient(_FakeMorningClient):
    """Like Morning's real search: a query only finds records whose stored
    name starts with exactly the queried characters."""

    def __init__(self, records):
        super().__init__()
        self._records = records

    def search_clients(self, payload):
        self.search_clients_calls.append(payload)
        query = payload.get("name", "")
        items = [r for r in self._records if r["name"].startswith(query)]
        return {"items": items, "total": len(items), "page": 1, "pages": 1}


def test_name_spellings_flips_each_quote_pair():
    assert tools._name_spellings(_APOSTROPHE_NAME) == [_APOSTROPHE_NAME, _GERESH_NAME]
    assert tools._name_spellings(_GERESH_NAME) == [_GERESH_NAME, _APOSTROPHE_NAME]
    assert tools._name_spellings(_QUOTE_NAME) == [_QUOTE_NAME, _GERSHAYIM_NAME]
    assert tools._name_spellings(_GERSHAYIM_NAME) == [_GERSHAYIM_NAME, _QUOTE_NAME]


def test_name_spellings_without_quote_characters_is_just_the_text():
    assert tools._name_spellings("Test Client") == ["Test Client"]


def test_name_spellings_leaves_other_characters_alone():
    typographic = "סידורוביץ’"  # U+2019 is treated like any other character
    assert tools._name_spellings(typographic) == [typographic]


def test_resolve_client_by_name_without_quotes_searches_once():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    tools._resolve_client_by_name(client, "Test Client")

    assert client.search_clients_calls == [{"name": "Test Client"}]


def test_resolve_client_by_name_finds_geresh_stored_client_from_apostrophe_query():
    record = _client_record(client_id="c-1", name=_GERESH_NAME)
    client = _SpellingAwareClient([record])

    resolved, candidates = tools._resolve_client_by_name(client, _APOSTROPHE_NAME)

    assert resolved is not None and resolved.id == "c-1"
    assert client.search_clients_calls == [{"name": _APOSTROPHE_NAME}, {"name": _GERESH_NAME}]


def test_resolve_client_by_name_finds_apostrophe_stored_client_from_geresh_query():
    record = _client_record(client_id="c-1", name=_APOSTROPHE_NAME)
    client = _SpellingAwareClient([record])

    resolved, _ = tools._resolve_client_by_name(client, _GERESH_NAME)

    assert resolved is not None and resolved.id == "c-1"


def test_resolve_client_by_name_finds_gershayim_stored_client_from_double_quote_query():
    record = _client_record(client_id="c-1", name=_GERSHAYIM_NAME)
    client = _SpellingAwareClient([record])

    resolved, _ = tools._resolve_client_by_name(client, _QUOTE_NAME)

    assert resolved is not None and resolved.id == "c-1"


def test_search_clients_by_name_merges_hits_by_client_id():
    both = _client_record(client_id="c-1", name=_APOSTROPHE_NAME)
    client = _FakeMorningClient(search_clients_response={"items": [both], "total": 1})

    merged = tools._search_clients_by_name(client, _APOSTROPHE_NAME)

    assert list(merged) == ["c-1"]  # same client returned by both spellings, kept once


def test_resolve_client_name_asks_confirmation_when_only_the_quote_spelling_differs():
    """The user typed an apostrophe (all an iPhone keyboard has), Morning
    stores a geresh: not an exact match, so the user is asked to confirm the
    stored name - never to retype it."""
    record = _client_record(client_id="c-1", name=_GERESH_NAME)
    client = _SpellingAwareClient([record])

    result = tools.resolve_client_name(client, _APOSTROPHE_NAME)

    assert _GERESH_NAME in result
    assert "status" in result  # a structured reply naming the candidate
    assert json.loads(result).get("status") != "resolved"


def test_add_client_sends_and_confirms_name_exactly_as_typed():
    client = _FakeMorningClient()

    result = tools.add_client(client, name=_APOSTROPHE_NAME, email="tech@example.com", phone="050-1234567")

    assert client.add_client_calls[0]["name"] == _APOSTROPHE_NAME
    assert _APOSTROPHE_NAME in result


def test_update_client_looks_up_the_stored_spelling_verbatim():
    record = _client_record(client_id="c-1", name=_APOSTROPHE_NAME)
    client = _SpellingAwareClient([record])

    tools.update_client(client, name=_APOSTROPHE_NAME, email="new@example.com", name_resolved=True)

    assert client.search_clients_calls[0] == {"name": _APOSTROPHE_NAME}
    assert client.update_client_calls[0][0] == "c-1"


def test_update_client_sends_new_name_exactly_as_typed():
    record = _client_record(client_id="c-1", name="Old Name")
    client = _FakeMorningClient(search_clients_response={"items": [record], "total": 1})

    result = tools.update_client(client, name="Old Name", new_name=_APOSTROPHE_NAME, name_resolved=True)

    assert client.update_client_calls[0][1]["name"] == _APOSTROPHE_NAME
    assert _APOSTROPHE_NAME in result


def test_list_clients_searches_both_spellings_of_the_name_filter():
    client = _FakeMorningClient(search_clients_response={"items": [], "total": 0})

    tools.list_clients(client, name=_APOSTROPHE_NAME)

    assert client.search_clients_calls == [{"name": _APOSTROPHE_NAME}, {"name": _GERESH_NAME}]


def test_list_clients_merges_hits_from_both_spellings():
    apostrophe = _client_record(client_id="c-1", name=_APOSTROPHE_NAME)
    geresh = _client_record(client_id="c-2", name=_GERESH_NAME)
    client = _SpellingAwareClient([apostrophe, geresh])

    result = tools.list_clients(client, name=_APOSTROPHE_NAME)

    assert _APOSTROPHE_NAME in result and _GERESH_NAME in result


def test_is_exact_name_match_does_not_treat_apostrophe_and_geresh_as_equal():
    """A quote-spelling difference makes it a "did you mean" the user confirms."""
    assert not tools._is_exact_name_match(_GERESH_NAME, _APOSTROPHE_NAME)
    assert tools._is_exact_name_match(_APOSTROPHE_NAME, _APOSTROPHE_NAME)


