"""Unit tests for ClientCache (Feature 072).

Pure local SQLite state - no Morning, no network, no mocking needed (this is
exactly the kind of internal component CONSTITUTION §V says tests exercise
directly, real, no test double required).

Revised 2026-09-15 (operator design review): the cache stores the FULL
client record (name/email/phone/tax_id/address), not just name+id -
`lookup_exact` now returns a `Client` directly (there is no separate
`CachedClient` type any more).
"""
import sqlite3
from pathlib import Path

import pytest

from denidin_mcp_morning.client_cache import ClientCache
from denidin_mcp_morning.models import Client


@pytest.fixture
def cache(tmp_path: Path) -> ClientCache:
    return ClientCache(tmp_path / "client_cache.db")


def _client(client_id: str, name: str, **kwargs) -> Client:
    return Client(id=client_id, name=name, **kwargs)


class TestLookupExact:
    def test_miss_on_empty_cache(self, cache: ClientCache):
        assert cache.lookup_exact("שלמה ישראלי") is None

    def test_hit_after_write_through(self, cache: ClientCache):
        cache.write_through(_client("c1", "שלמה ישראלי"))
        hit = cache.lookup_exact("שלמה ישראלי")
        assert hit is not None
        assert hit.id == "c1"
        assert hit.name == "שלמה ישראלי"

    def test_hit_returns_the_full_record(self, cache: ClientCache):
        cache.write_through(
            _client("c1", "לקוח מלא", email="full@example.com", phone="050-1234567", tax_id="123456789")
        )
        hit = cache.lookup_exact("לקוח מלא")
        assert hit is not None
        assert hit.email == "full@example.com"
        assert hit.phone == "050-1234567"
        assert hit.tax_id == "123456789"

    def test_hit_is_case_insensitive(self, cache: ClientCache):
        cache.write_through(_client("c1", "Yossi Cohen"))
        assert cache.lookup_exact("yossi cohen") is not None
        assert cache.lookup_exact("YOSSI COHEN") is not None

    def test_hit_is_word_order_independent(self, cache: ClientCache):
        cache.write_through(_client("c1", "ישראלי שלמה"))
        hit = cache.lookup_exact("שלמה ישראלי")
        assert hit is not None
        assert hit.id == "c1"
        # The stored/disclosed name is always Morning's real stored order,
        # never the query's order (REQ-CLIENT-018 / format_client_name_resolved
        # contract - resolve_client_name must return the exact stored name).
        assert hit.name == "ישראלי שלמה"

    def test_hit_normalizes_apostrophe_variants(self, cache: ClientCache):
        # ' (U+0027) vs the correct Hebrew geresh (U+05F3) - same normalization
        # tools.py's _normalize_hebrew_geresh already applies.
        cache.write_through(_client("c1", "אבי׳ בע׳מ"))
        assert cache.lookup_exact("אבי' בע'מ") is not None

    def test_partial_name_is_not_a_hit(self, cache: ClientCache):
        cache.write_through(_client("c1", "שלמה ישראלי בע׳מ"))
        assert cache.lookup_exact("שלמה ישראלי") is None


class TestWriteThrough:
    def test_write_through_twice_upserts(self, cache: ClientCache):
        cache.write_through(_client("c1", "שם ישן"))
        cache.write_through(_client("c1", "שם חדש"))
        assert cache.lookup_exact("שם ישן") is None
        hit = cache.lookup_exact("שם חדש")
        assert hit is not None and hit.id == "c1"

    def test_write_through_requires_an_id(self, cache: ClientCache):
        with pytest.raises(ValueError):
            cache.write_through(Client(id=None, name="בלי מזהה"))

    def test_write_through_twice_replaces_full_details(self, cache: ClientCache):
        cache.write_through(_client("c1", "לקוח", email="old@example.com", phone="050-1111111"))
        cache.write_through(_client("c1", "לקוח", email="new@example.com", phone="050-2222222"))
        hit = cache.lookup_exact("לקוח")
        assert hit is not None
        assert hit.email == "new@example.com"
        assert hit.phone == "050-2222222"


class TestEviction:
    def test_evict_removes_row(self, cache: ClientCache):
        cache.write_through(_client("c1", "לקוח למחיקה"))
        cache.evict("c1")
        assert cache.lookup_exact("לקוח למחיקה") is None

    def test_evict_missing_id_is_a_noop(self, cache: ClientCache):
        cache.evict("no-such-id")  # must not raise

    def test_evict_by_name_removes_matching_row(self, cache: ClientCache):
        cache.write_through(_client("c1", "לקוח ישן"))
        cache.evict_by_name("לקוח ישן")
        assert cache.lookup_exact("לקוח ישן") is None

    def test_evict_by_name_missing_is_a_noop(self, cache: ClientCache):
        cache.evict_by_name("לא קיים")  # must not raise


class TestReconcile:
    def test_reconcile_inserts_new_rows(self, cache: ClientCache):
        cache.reconcile([_client("c1", "לקוח א"), _client("c2", "לקוח ב")])
        assert cache.lookup_exact("לקוח א") is not None
        assert cache.lookup_exact("לקוח ב") is not None

    def test_reconcile_updates_a_renamed_row(self, cache: ClientCache):
        cache.write_through(_client("c1", "שם ישן"))
        cache.reconcile([_client("c1", "שם חדש מונינג")])
        assert cache.lookup_exact("שם ישן") is None
        assert cache.lookup_exact("שם חדש מונינג") is not None

    def test_reconcile_deletes_a_row_no_longer_present(self, cache: ClientCache):
        cache.write_through(_client("c1", "לקוח קיים"))
        cache.write_through(_client("c2", "לקוח שנמחק"))
        cache.reconcile([_client("c1", "לקוח קיים")])
        assert cache.lookup_exact("לקוח קיים") is not None
        assert cache.lookup_exact("לקוח שנמחק") is None

    def test_reconcile_with_empty_list_evicts_everything(self, cache: ClientCache):
        cache.write_through(_client("c1", "לקוח א"))
        cache.write_through(_client("c2", "לקוח ב"))
        cache.reconcile([])
        assert cache.lookup_exact("לקוח א") is None
        assert cache.lookup_exact("לקוח ב") is None

    def test_reconcile_syncs_full_details(self, cache: ClientCache):
        cache.write_through(_client("c1", "לקוח", email="old@example.com"))
        cache.reconcile([_client("c1", "לקוח", email="new@example.com", tax_id="987654321")])
        hit = cache.lookup_exact("לקוח")
        assert hit is not None
        assert hit.email == "new@example.com"
        assert hit.tax_id == "987654321"


class TestDuplicateNames:
    """Morning does not enforce unique client names (found live, 2026-09-15,
    against the real sandbox's accumulated test data) - two different real
    client_ids can legitimately share the same stored name."""

    def test_two_clients_with_the_same_name_is_not_a_cache_hit(self, cache: ClientCache):
        cache.write_through(_client("c1", "לקוח כפול"))
        cache.write_through(_client("c2", "לקוח כפול"))
        assert cache.lookup_exact("לקוח כפול") is None

    def test_reconcile_accepts_duplicate_names_without_error(self, cache: ClientCache):
        # Must not raise (this is exactly the real-sandbox shape that broke
        # a naive UNIQUE(name_normalized) index).
        cache.reconcile([_client("c1", "לקוח כפול"), _client("c2", "לקוח כפול")])
        assert cache.lookup_exact("לקוח כפול") is None

    def test_evicting_one_of_two_duplicates_restores_the_hit_for_the_other(self, cache: ClientCache):
        cache.write_through(_client("c1", "לקוח כפול"))
        cache.write_through(_client("c2", "לקוח כפול"))
        cache.evict("c1")
        hit = cache.lookup_exact("לקוח כפול")
        assert hit is not None and hit.id == "c2"


class TestPersistence:
    def test_survives_reopening_the_same_db_file(self, tmp_path: Path):
        db_path = tmp_path / "client_cache.db"
        ClientCache(db_path).write_through(_client("c1", "לקוח קבוע"))
        reopened = ClientCache(db_path)
        hit = reopened.lookup_exact("לקוח קבוע")
        assert hit is not None and hit.id == "c1"

    def test_creates_parent_directories(self, tmp_path: Path):
        nested = tmp_path / "nested" / "dir" / "client_cache.db"
        ClientCache(nested).write_through(_client("c1", "x"))
        assert nested.exists()

    def test_index_on_name_normalized_exists(self, tmp_path: Path):
        db_path = tmp_path / "client_cache.db"
        ClientCache(db_path)
        with sqlite3.connect(db_path) as conn:
            names = {row[1] for row in conn.execute("PRAGMA index_list(clients)")}
        assert "idx_clients_name_normalized" in names
