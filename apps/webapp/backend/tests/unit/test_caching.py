"""Caching behaviour: the conversation cache, the ledger reload, and the clients report cache
serve repeat requests from memory and only hit disk / Morning again on an explicit refresh."""
import json
from pathlib import Path

from webapp_backend.clients_reader import ClientsReader
from webapp_backend.context_reader import ContextReader
from webapp_backend.ledger_reader import LedgerReader


def _session(root: Path, sid: str) -> Path:
    sdir = root / "sessions" / sid
    (sdir / "messages").mkdir(parents=True)
    (sdir / "session.json").write_text(json.dumps({"session_id": sid}), encoding="utf-8")
    return sdir


def _msg(sdir: Path, mid: str, ts: str) -> None:
    (sdir / "messages" / f"{mid}.json").write_text(
        json.dumps({"message_id": mid, "role": "user", "content": mid, "timestamp": ts}),
        encoding="utf-8",
    )


def _event(events_dir: Path, event_id: str) -> None:
    (events_dir / f"{event_id}.json").write_text(
        json.dumps({
            "event_id": event_id, "source_type": "הסכם", "event_subtype": "יצירה",
            "client_name": "דנה", "amount": 100, "event_datetime": "01/01/2026 10:00",
        }, ensure_ascii=False),
        encoding="utf-8",
    )


class TestContextCache:
    def test_repeat_lookup_does_not_reread_message_files(self, tmp_path):
        sdir = _session(tmp_path, "s1")
        _msg(sdir, "m1", "2026-08-03T19:20:00+00:00")
        reader = ContextReader(str(tmp_path))
        assert len(reader.build_context("s1", "m1", 10)["messages"]) == 1

        # Deleting the file proves the second answer comes from memory, not disk.
        (sdir / "messages" / "m1.json").unlink()
        assert len(reader.build_context("s1", "m1", 10)["messages"]) == 1

    def test_reset_forgets_cached_messages(self, tmp_path):
        sdir = _session(tmp_path, "s1")
        _msg(sdir, "m1", "2026-08-03T19:20:00+00:00")
        reader = ContextReader(str(tmp_path))
        reader.build_context("s1", "m1", 10)

        (sdir / "messages" / "m1.json").unlink()
        reader.reset()
        assert reader.build_context("s1", "m1", 10)["error"] == "context_unavailable"


class TestLedgerReload:
    def test_new_event_visible_only_after_reload(self, tmp_path):
        events = tmp_path / "events"
        events.mkdir()
        _event(events, "A1")
        reader = LedgerReader(str(tmp_path))
        assert reader.raw_event("A1") is not None

        _event(events, "A2")
        assert reader.raw_event("A2") is None
        generation = reader.generation
        reader.reload()
        assert reader.raw_event("A2") is not None
        assert reader.generation == generation + 1


class TestClientsReportCache:
    def _reader(self, tmp_path, calls):
        events = tmp_path / "events"
        events.mkdir()
        (tmp_path / "clients").mkdir()

        def official():
            calls.append(1)
            return ["דנה"]

        ledger = LedgerReader(str(tmp_path))
        reader = ClientsReader(
            str(tmp_path), str(tmp_path / "clients"), official,
            events_fn=ledger.events, generation_fn=lambda: ledger.generation,
        )
        return reader, ledger

    def test_report_and_morning_list_computed_once_until_refresh(self, tmp_path):
        calls: list = []
        reader, _ = self._reader(tmp_path, calls)
        reader.get_report()
        reader.get_report()
        assert len(calls) == 1
        reader.get_report(refresh=True)
        assert len(calls) == 2

    def test_save_recomputes_report_without_refetching_morning(self, tmp_path):
        calls: list = []
        reader, _ = self._reader(tmp_path, calls)
        reader.get_report()
        reader.save_comment("דנה", "הערה")
        report = reader.get_report()
        assert len(calls) == 1
        assert next(c for c in report["clients"] if c["official_name"] == "דנה")["comment"] == "הערה"

    def test_ledger_reload_invalidates_report(self, tmp_path):
        calls: list = []
        reader, ledger = self._reader(tmp_path, calls)
        first = reader.get_report()
        _event(tmp_path / "events", "A1")
        ledger.reload()
        second = reader.get_report()
        assert second is not first
        assert len(calls) == 1


class TestOrdering:
    def test_order_num_beats_timestamp_ties_and_stamp_inversions(self, tmp_path):
        sdir = _session(tmp_path, "s1")
        same = "2026-09-14T13:32:42+03:00"
        rows = [  # (mid, order_num, timestamp): 3 is stamped later than 4 despite coming first
            ("q", 1, same), ("a", 2, same), ("late", 3, "2026-09-14T13:32:56+03:00"), ("next", 4, same),
        ]
        for mid, num, ts in rows:
            (sdir / "messages" / f"{mid}.json").write_text(json.dumps({
                "message_id": mid, "role": "user", "content": mid, "timestamp": ts, "order_num": num,
            }), encoding="utf-8")
        out = ContextReader(str(tmp_path)).build_context("s1", "q", 10)
        assert [m["message_id"] for m in out["messages"]] == ["q", "a", "late", "next"]

    def test_messages_without_order_num_fall_back_to_timestamp_and_come_first(self, tmp_path):
        sdir = _session(tmp_path, "s1")
        for mid, ts, num in (("new", "2026-09-14T13:00:00+03:00", 5),
                             ("old2", "2026-09-14T12:59:30+03:00", None),
                             ("old1", "2026-09-14T12:59:00+03:00", None)):
            rec = {"message_id": mid, "role": "user", "content": mid, "timestamp": ts}
            if num is not None:
                rec["order_num"] = num
            (sdir / "messages" / f"{mid}.json").write_text(json.dumps(rec), encoding="utf-8")
        out = ContextReader(str(tmp_path)).build_context("s1", "new", 10)
        assert [m["message_id"] for m in out["messages"]] == ["old1", "old2", "new"]
