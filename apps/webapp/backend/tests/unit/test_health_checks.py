"""Unit tests for webapp_backend.health_checks (Feature 068).

Each check is exercised directly against real temp files/dirs - no mocking, matching
morning-mcp-app/tests/unit/test_health_checks.py's shape.
"""
import time
from pathlib import Path

from webapp_backend.auth import hash_password
from webapp_backend.health_checks import (
    build_health_check_fns,
    check_denidin_data_readable,
    check_ledger_index,
    check_log_freshness,
    check_password_hash_readable,
)


class TestDenidinDataReadable:
    def test_true_when_root_and_events_dir_exist(self, tmp_path):
        (tmp_path / "events").mkdir()
        assert check_denidin_data_readable(str(tmp_path)) is True

    def test_false_when_root_missing(self, tmp_path):
        assert check_denidin_data_readable(str(tmp_path / "nope")) is False

    def test_false_when_events_subdir_missing(self, tmp_path):
        assert check_denidin_data_readable(str(tmp_path)) is False

    def test_false_when_root_is_a_file(self, tmp_path):
        f = tmp_path / "afile"
        f.write_text("x")
        assert check_denidin_data_readable(str(f)) is False


class TestPasswordHashReadable:
    def test_true_for_valid_64_hex(self, tmp_path):
        p = tmp_path / "password.hash"
        p.write_text(hash_password("whatever"), encoding="utf-8")
        assert check_password_hash_readable(str(p)) is True

    def test_false_when_missing(self, tmp_path):
        assert check_password_hash_readable(str(tmp_path / "password.hash")) is False

    def test_false_when_malformed(self, tmp_path):
        p = tmp_path / "password.hash"
        p.write_text("not-a-hash", encoding="utf-8")
        assert check_password_hash_readable(str(p)) is False


class TestLedgerIndex:
    def test_true_for_real_reader_over_empty_events_dir(self, tmp_path):
        from webapp_backend.ledger_reader import LedgerReader

        (tmp_path / "events").mkdir()
        assert check_ledger_index(LedgerReader(str(tmp_path))) is True

    def test_false_when_reader_raises(self):
        class Boom:
            def list_event_rows(self, _days):  # noqa: D401
                raise RuntimeError("index never built")

        assert check_ledger_index(Boom()) is False


class TestLogFreshness:
    def test_true_for_fresh_file(self, tmp_path):
        p = tmp_path / "webapp-backend.log"
        p.write_text("line\n")
        assert check_log_freshness(p, max_age_seconds=60) is True

    def test_false_for_stale_file(self, tmp_path):
        p = tmp_path / "webapp-backend.log"
        p.write_text("line\n")
        old = time.time() - 5000
        import os

        os.utime(p, (old, old))
        assert check_log_freshness(p, max_age_seconds=600) is False

    def test_false_when_missing(self, tmp_path):
        assert check_log_freshness(tmp_path / "nope.log") is False


class TestBuildHealthCheckFns:
    def test_only_supplied_deps_produce_checks(self, tmp_path):
        (tmp_path / "events").mkdir()
        fns = build_health_check_fns(denidin_data_root=str(tmp_path))
        assert set(fns) == {"denidin_data_readable"}
        assert fns["denidin_data_readable"]() is True

    def test_none_args_produce_no_checks(self):
        assert build_health_check_fns() == {}
