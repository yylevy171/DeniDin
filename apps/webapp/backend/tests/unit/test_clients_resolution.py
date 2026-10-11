"""Feature 092 - names-to-resolve corrections.

T017 ``Unknown-<event_id>`` naming, T018 ``mapped_aliases`` + unlinking a name mapping,
T027 "הסר מהרשימה" (hiding an unmatched name)."""
import pytest

from tests.clients_helpers import (
    agreement,
    make_reader,
    payment,
    read_json,
    recent,
    row,
)
from webapp_backend.clients_reader import MappingNotFoundError

DANA = "דנה כהן"
DAN = "דן לוי"
OFFICIAL = [DANA, DAN]


def _unmatched(report):
    return {u["raw_name"]: u for u in report["unmatched"]}


def _no_name_events():
    return [
        payment("U1", None, 500, when=recent(10)),
        payment("U2", "", 1200, when=recent(9)),
        payment("U3", "Unknown", 3000, when=recent(8)),
    ]


class TestUnknownNaming:
    """T017"""

    def test_each_no_name_event_is_its_own_unmatched_row(self, tmp_path):
        report = make_reader(tmp_path, OFFICIAL, _no_name_events()).get_report()
        unmatched = _unmatched(report)
        assert {"Unknown-U1", "Unknown-U2", "Unknown-U3"} <= set(unmatched)
        assert "Unknown" not in unmatched
        for name in ("Unknown-U1", "Unknown-U2", "Unknown-U3"):
            assert unmatched[name]["event_count"] == 1

    def test_older_late_arriving_event_does_not_rename_existing_ones(self, tmp_path):
        events = _no_name_events()
        mapping = {"Unknown-U1": DANA}
        first = make_reader(tmp_path / "a", OFFICIAL, events, mapping=mapping).get_report()
        late = events + [payment("U0", None, 999, when=recent(30))]
        second = make_reader(tmp_path / "b", OFFICIAL, late, mapping=mapping).get_report()
        assert set(_unmatched(first)) | {"Unknown-U0"} == set(_unmatched(second))
        assert row(first, DANA)["display_paid"] == row(second, DANA)["display_paid"] == 500

    def test_mapping_one_unknown_moves_exactly_that_event(self, tmp_path):
        events = _no_name_events() + [agreement("A1", DANA, 10000), agreement("A2", DAN, 10000)]
        mapping = {"Unknown-U1": DANA, "Unknown-U2": DAN}
        report = make_reader(tmp_path, OFFICIAL, events, mapping=mapping).get_report()
        assert row(report, DANA)["display_paid"] == 500
        assert row(report, DAN)["display_paid"] == 1200
        assert [e["amount"] for e in row(report, DANA)["events"] if e["type"] == "חשבונית"] == [500]
        unmatched = _unmatched(report)
        assert "Unknown-U1" not in unmatched and "Unknown-U2" not in unmatched
        assert "Unknown-U3" in unmatched

    def test_named_alias_mapped_to_unknown_keeps_its_own_name(self, tmp_path):
        events = [payment("C1", "שם מוזר", 700)]
        report = make_reader(tmp_path, OFFICIAL, events, mapping={"שם מוזר": "Unknown"}).get_report()
        assert "שם מוזר" in _unmatched(report)


class TestMappedAliasesAndUnlink:
    """T018"""

    def _events(self):
        return [
            agreement("A1", DANA, 10000),
            payment("C1", "Yisrael I", 2000),
            payment("C2", "דנה כהנ", 300),  # fuzzy match to DANA (cutoff 0.8)
        ]

    def test_mapped_aliases_lists_only_explicit_mappings(self, tmp_path):
        reader = make_reader(tmp_path, OFFICIAL, self._events(), mapping={"Yisrael I": DANA})
        r = row(reader.get_report(), DANA)
        assert "Yisrael I" in r["raw_names"] and "דנה כהנ" in r["raw_names"]
        assert r["mapped_aliases"] == ["Yisrael I"]

    def test_merge_source_is_not_unlinkable(self, tmp_path):
        events = self._events() + [agreement("A2", DAN, 100)]
        reader = make_reader(
            tmp_path, OFFICIAL, events, comments={DAN: f'לאחד עם "{DANA}"'}, mapping={"Yisrael I": DANA}
        )
        r = row(reader.get_report(), DANA)
        assert DAN in r["raw_names"]
        assert DAN not in r["mapped_aliases"]

    def test_unlink_restores_unmatched_row_with_note_and_reverts_totals(self, tmp_path):
        reader = make_reader(
            tmp_path, OFFICIAL, self._events(),
            mapping={"Yisrael I": DANA, "אחר": DAN}, notes={"Yisrael I": "שילם במזומן"},
        )
        assert row(reader.get_report(), DANA)["display_paid"] == 2300

        assert reader.unlink_mapping("Yisrael I") == {"raw_name": "Yisrael I", "unlinked_from": DANA}

        report = reader.get_report()
        assert read_json(tmp_path / "clients" / "client_mapping.json") == {"אחר": DAN}
        assert row(report, DANA)["display_paid"] == 300
        assert "Yisrael I" not in row(report, DANA)["raw_names"]
        assert _unmatched(report)["Yisrael I"]["note"] == "שילם במזומן"

    def test_unlink_unknown_name_raises(self, tmp_path):
        reader = make_reader(tmp_path, OFFICIAL, self._events())
        with pytest.raises(MappingNotFoundError):
            reader.unlink_mapping("לא קיים")

    def test_unknown_event_mapping_is_unlinkable_like_any_name(self, tmp_path):
        reader = make_reader(tmp_path, OFFICIAL, _no_name_events(), mapping={"Unknown-U1": DANA})
        assert row(reader.get_report(), DANA)["mapped_aliases"] == ["Unknown-U1"]
        reader.unlink_mapping("Unknown-U1")
        assert "Unknown-U1" in _unmatched(reader.get_report())


class TestHideUnmatched:
    """T027"""

    def test_hide_removes_name_and_persists_sorted_unique(self, tmp_path):
        events = [payment("C1", "בית", 10), payment("C2", "אלף", 20)]
        reader = make_reader(tmp_path, OFFICIAL, events)
        reader.hide_unmatched("בית")
        reader.hide_unmatched("אלף")
        assert reader.hide_unmatched("בית") == {"raw_name": "בית", "hidden": True}
        assert read_json(tmp_path / "clients" / "hidden_unmatched.json") == ["אלף", "בית"]
        unmatched = _unmatched(reader.get_report())
        assert "בית" not in unmatched and "אלף" not in unmatched

    def test_hidden_survives_a_restart(self, tmp_path):
        events = [payment("C1", "בית", 10)]
        make_reader(tmp_path, OFFICIAL, events).hide_unmatched("בית")
        assert "בית" not in _unmatched(make_reader(tmp_path, OFFICIAL, events).get_report())

    def test_existing_note_keyword_hiding_still_works(self, tmp_path):
        events = [payment("C1", "בית", 10)]
        report = make_reader(tmp_path, OFFICIAL, events, notes={"בית": "להסיר"}).get_report()
        assert "בית" not in _unmatched(report)

    def test_delete_word_in_a_note_does_not_hide(self, tmp_path):
        events = [payment("C1", "בית", 10)]
        report = make_reader(tmp_path, OFFICIAL, events, notes={"בית": "למחוק"}).get_report()
        assert "בית" in _unmatched(report)
