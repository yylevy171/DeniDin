"""bugfix-066: morning_connectivity + ledger_complete health checks. Real temp dirs, no mocking
of app code (the Morning 'ping' is the injected dependency, a plain callable)."""
from types import SimpleNamespace

from webapp_backend import health_checks as hc
from webapp_backend.health_checks import (
    build_health_check_fns,
    check_ledger_complete,
    make_morning_ping_check,
)


def _reader(n):
    return SimpleNamespace(events=lambda: [{}] * n)


class TestLedgerComplete:
    def test_true_when_no_event_files_on_disk(self, tmp_path):
        (tmp_path / "events").mkdir()
        assert check_ledger_complete(_reader(0), str(tmp_path)) is True

    def test_false_when_files_on_disk_but_index_empty(self, tmp_path):
        (tmp_path / "events").mkdir()
        (tmp_path / "events" / "A1.json").write_text("{}")
        assert check_ledger_complete(_reader(0), str(tmp_path)) is False

    def test_true_when_index_lags_but_is_not_empty(self, tmp_path):
        (tmp_path / "events").mkdir()
        for i in range(3):
            (tmp_path / "events" / f"A{i}.json").write_text("{}")
        assert check_ledger_complete(_reader(1), str(tmp_path)) is True


class TestMorningPing:
    def test_true_when_ping_succeeds(self):
        assert make_morning_ping_check(lambda: None)() is True

    def test_false_when_ping_raises(self):
        def boom():
            raise RuntimeError("morning down")
        assert make_morning_ping_check(boom)() is False

    def test_result_cached_within_window(self):
        calls = []
        check = make_morning_ping_check(lambda: calls.append(1), cache_seconds=60)
        check(); check(); check()
        assert len(calls) == 1

    def test_recovers_after_cache_expires(self):
        state = {"fail": True}
        def ping():
            if state["fail"]:
                raise RuntimeError("x")
        check = make_morning_ping_check(ping, cache_seconds=0.0)
        assert check() is False
        state["fail"] = False
        assert check() is True


class TestWiring:
    def test_morning_check_present_only_when_ping_given(self):
        assert "morning_connectivity" not in build_health_check_fns()
        assert "morning_connectivity" in build_health_check_fns(morning_ping=lambda: None)

    def test_morning_is_part_of_overall_status(self):
        assert "morning_connectivity" not in hc.INFORMATIONAL_CHECKS
