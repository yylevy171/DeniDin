"""Unit tests for webapp_backend.ledger_reader (Story 2A) — real event JSON files, no mocking."""
import json
from datetime import timedelta
from pathlib import Path

import pytest

from utils.time_utils import now_local
from webapp_backend.ledger_reader import LedgerReader


def _write_event(events_dir: Path, event_id: str, **fields) -> None:
    record = {
        "event_id": event_id,
        "source_type": "הסכם",
        "event_subtype": "יצירה",
        "client_name": "ישראל ישראלי",
        "amount": 1000,
        "description": "desc",
        "event_datetime": fields.pop("event_datetime", "01/01/2020 10:00"),
        "txn_date": None,
    }
    record.update(fields)
    (events_dir / f"{event_id}.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8"
    )


@pytest.fixture
def data_root(tmp_path) -> Path:
    (tmp_path / "events").mkdir()
    return tmp_path


def _ddmmyyyy(days_ago: int) -> str:
    return (now_local().date() - timedelta(days=days_ago)).strftime("%d/%m/%Y")


class TestListEventRows:
    def test_empty_when_no_events(self, data_root):
        out = LedgerReader(str(data_root)).list_event_rows(7)
        assert out == {"events": [], "days_back": 7, "count": 0}

    def test_default_window_excludes_older_than_days_back(self, data_root):
        _write_event(data_root / "events", "A1", event_datetime=f"{_ddmmyyyy(2)} 09:00")
        _write_event(data_root / "events", "A2", event_datetime=f"{_ddmmyyyy(8)} 09:00")
        out = LedgerReader(str(data_root)).list_event_rows(7)
        assert [r["event_id"] for r in out["events"]] == ["A1"]
        assert out["count"] == 1

    def test_boundary_day_is_inclusive(self, data_root):
        _write_event(data_root / "events", "A1", event_datetime=f"{_ddmmyyyy(7)} 09:00")
        out = LedgerReader(str(data_root)).list_event_rows(7)
        assert [r["event_id"] for r in out["events"]] == ["A1"]

    def test_txn_date_wins_over_event_datetime_for_window(self, data_root):
        # event_datetime is old, but txn_date is recent → included
        recent_iso = (now_local().date() - timedelta(days=1)).isoformat()
        _write_event(
            data_root / "events", "A1",
            event_datetime="01/01/2019 09:00", txn_date=recent_iso,
        )
        out = LedgerReader(str(data_root)).list_event_rows(7)
        assert [r["event_id"] for r in out["events"]] == ["A1"]
        assert out["events"][0]["date"] == (now_local().date() - timedelta(days=1)).strftime("%d/%m/%Y")

    def test_txn_date_accepts_dd_mm_yyyy_not_only_iso(self, data_root):
        recent = now_local().date() - timedelta(days=1)
        _write_event(data_root / "events", "B1", txn_date=recent.strftime("%d/%m/%Y"))
        out = LedgerReader(str(data_root)).list_event_rows(7)
        assert [r["event_id"] for r in out["events"]] == ["B1"]

    def test_old_schema_event_date_field_is_recognised(self, data_root):
        # pre-Phase-11 הסכם/בנק events: no event_datetime, only event_date (DD/MM/YYYY)
        recent = (now_local().date() - timedelta(days=2)).strftime("%d/%m/%Y")
        p = data_root / "events" / "A9.json"
        p.write_text(json.dumps({
            "event_id": "A9", "source_type": "הסכם", "event_subtype": "יצירה",
            "client_name": "פלוני", "amount": 5000, "description": "d",
            "event_date": recent, "event_time": "14:06",
        }, ensure_ascii=False), encoding="utf-8")
        out = LedgerReader(str(data_root)).list_event_rows(7)
        assert [r["event_id"] for r in out["events"]] == ["A9"]
        assert out["events"][0]["date"] == recent

    def test_newest_first_with_event_id_desc_tiebreaker(self, data_root):
        same_day = f"{_ddmmyyyy(1)} 09:00"
        _write_event(data_root / "events", "A1", event_datetime=same_day)
        _write_event(data_root / "events", "A3", event_datetime=same_day)
        _write_event(data_root / "events", "A2", event_datetime=f"{_ddmmyyyy(3)} 09:00")
        rows = LedgerReader(str(data_root)).list_event_rows(7)["events"]
        assert [r["event_id"] for r in rows] == ["A3", "A1", "A2"]

    def test_row_shape_is_the_six_display_fields_plus_id_and_search_blob(self, data_root):
        _write_event(data_root / "events", "A1", event_datetime=f"{_ddmmyyyy(1)} 09:00")
        row = LedgerReader(str(data_root)).list_event_rows(7)["events"][0]
        assert set(row) == {
            "event_id", "date", "source_type", "event_subtype",
            "client_name", "amount", "description", "search_blob",
        }
        assert row["date"] == _ddmmyyyy(1)

    def test_search_blob_includes_text_from_nested_non_column_fields(self, data_root):
        _write_event(
            data_root / "events", "A1",
            event_datetime=f"{_ddmmyyyy(1)} 09:00",
            description="שכר טרחה",
            components=[{"component_label": "ייעוץ שוטף", "percent": 10}],
        )
        row = LedgerReader(str(data_root)).list_event_rows(7)["events"][0]
        assert "ייעוץ שוטף" in row["search_blob"]
        assert "שכר טרחה" in row["search_blob"]
        assert row["search_blob"] == row["search_blob"].lower()

    def test_negative_days_back_falls_back_to_default(self, data_root):
        _write_event(data_root / "events", "A1", event_datetime=f"{_ddmmyyyy(3)} 09:00")
        out = LedgerReader(str(data_root)).list_event_rows(-5)
        assert out["days_back"] == 7
        assert out["count"] == 1

    def test_unparseable_event_file_is_skipped_not_fatal(self, data_root):
        _write_event(data_root / "events", "A1", event_datetime=f"{_ddmmyyyy(1)} 09:00")
        (data_root / "events" / "broken.json").write_text("{ not json", encoding="utf-8")
        out = LedgerReader(str(data_root)).list_event_rows(7)
        assert out["count"] == 1


class TestGetEventDetail:
    def test_missing_returns_none(self, data_root):
        assert LedgerReader(str(data_root)).get_event_detail("nope") is None

    def test_returns_curated_labelled_fields_not_raw_record(self, data_root):
        _write_event(
            data_root / "events", "A1",
            source_type="הסכם", event_subtype="יצירה",
            reference="X-99", session_id="s-1", captured_at="whenever",
            raw_message_excerpt="lots of text", notes="internal note",
        )
        detail = LedgerReader(str(data_root)).get_event_detail("A1")
        assert detail["event_id"] == "A1"
        assert detail["source_type"] == "הסכם"
        keys = {f["key"] for f in detail["fields"]}
        # internal / non-manifest fields never leak
        assert keys.isdisjoint({"session_id", "captured_at", "raw_message_excerpt", "notes",
                                "event_id", "message_id"})
        # every field carries a Hebrew label
        for f in detail["fields"]:
            assert f["label"] and any("֐" <= ch <= "ת" for ch in f["label"])

    def test_common_fields_always_present_even_when_null(self, data_root):
        p = data_root / "events" / "A2.json"
        p.write_text(json.dumps({
            "event_id": "A2", "source_type": "הסכם", "event_subtype": "יצירה",
            "event_date": "01/01/2026", "event_time": "10:00",
        }, ensure_ascii=False), encoding="utf-8")
        detail = LedgerReader(str(data_root)).get_event_detail("A2")
        by_key = {f["key"]: f for f in detail["fields"]}
        for k in ("event_datetime", "source_type", "event_subtype", "client_name",
                  "description", "amount", "txn_date"):
            assert k in by_key
        assert by_key["txn_date"]["value"] is None
        # old-schema event_date/event_time synthesised into the event_datetime row
        assert by_key["event_datetime"]["value"] == "01/01/2026 10:00"

    def test_if_exists_field_dropped_when_empty(self, data_root):
        _write_event(data_root / "events", "A3", source_type="הסכם", event_subtype="יצירה")
        detail = LedgerReader(str(data_root)).get_event_detail("A3")
        keys = {f["key"] for f in detail["fields"]}
        assert "component_label" not in keys  # IF-EXISTS, no value

    def test_unknown_source_type_is_flagged_not_rendered(self, data_root):
        p = data_root / "events" / "Z1.json"
        p.write_text(json.dumps({
            "event_id": "Z1", "source_type": "משהו", "event_subtype": "?",
            "event_datetime": "01/01/2026 10:00",
        }, ensure_ascii=False), encoding="utf-8")
        detail = LedgerReader(str(data_root)).get_event_detail("Z1")
        assert detail["unsupported"] is True
        assert "fields" not in detail

    def test_raw_event_still_exposes_internal_fields(self, data_root):
        _write_event(data_root / "events", "A4", session_id="s-9")
        raw = LedgerReader(str(data_root)).raw_event("A4")
        assert raw["session_id"] == "s-9"


class TestSearchClientNames:
    def test_prefix_match_case_insensitive_deduped_sorted(self, data_root):
        _write_event(data_root / "events", "A1", client_name="Dana Cohen")
        _write_event(data_root / "events", "A2", client_name="Dan Levi")
        _write_event(data_root / "events", "A3", client_name="dana cohen")
        _write_event(data_root / "events", "A4", client_name="Yossi")
        out = LedgerReader(str(data_root)).search_client_names("da")
        assert out == ["Dan Levi", "Dana Cohen"]

    def test_under_two_chars_returns_empty(self, data_root):
        _write_event(data_root / "events", "A1", client_name="Dana")
        assert LedgerReader(str(data_root)).search_client_names("d") == []
