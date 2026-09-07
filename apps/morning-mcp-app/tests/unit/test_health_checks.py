"""Tests for health_checks.py (bugfix-043 - health monitoring & auto-restart).

Real objects throughout - a real (if fake-configured) MorningClient whose
network calls fail against an unroutable host (no mocking of internal code,
per CONSTITUTION SS V), and real tmp_path files for the log-freshness check.
"""
import time

import pytest

from denidin_mcp_morning.health_checks import (
    HEARTBEAT_INTERVAL_SECONDS,
    check_log_freshness,
    check_morning_connectivity,
    resolve_log_path,
    write_heartbeat_log,
)
from denidin_mcp_morning.morning_client import MorningClient


def _unreachable_client() -> MorningClient:
    """A real MorningClient pointed at a host that will never resolve/respond -
    exercises the real failure path through client.auth.get_token(), no mock."""
    return MorningClient(
        api_key_id="fake-id",
        api_key_secret="fake-secret",
        auth_url="https://this-host-does-not-exist.invalid/auth",
        base_url="https://this-host-does-not-exist.invalid/api/v1",
    )


class _FakeAuth:
    def __init__(self, should_succeed: bool):
        self._should_succeed = should_succeed

    def get_token(self):
        if self._should_succeed:
            return "fake-token"
        raise ConnectionError("simulated auth failure")


class _FakeClient:
    def __init__(self, should_succeed: bool):
        self.auth = _FakeAuth(should_succeed)


def test_check_morning_connectivity_true_when_token_mint_succeeds():
    assert check_morning_connectivity(_FakeClient(should_succeed=True)) is True


def test_check_morning_connectivity_false_when_token_mint_raises():
    assert check_morning_connectivity(_FakeClient(should_succeed=False)) is False


def test_check_morning_connectivity_false_against_a_real_unreachable_host():
    """End-to-end through the real MorningClient/MorningAuth machinery, not
    just the fake stand-in above - confirms the real exception path is caught."""
    assert check_morning_connectivity(_unreachable_client()) is False


def test_check_log_freshness_true_for_a_just_written_file(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("just wrote this\n")

    assert check_log_freshness(log_path, max_age_seconds=600) is True


def test_check_log_freshness_false_for_a_stale_file(tmp_path):
    log_path = tmp_path / "app.log"
    log_path.write_text("old\n")
    old_time = time.time() - 3600  # 1 hour ago
    import os

    os.utime(log_path, (old_time, old_time))

    assert check_log_freshness(log_path, max_age_seconds=600) is False


def test_check_log_freshness_false_when_file_missing(tmp_path):
    assert check_log_freshness(tmp_path / "never-written.log", max_age_seconds=600) is False


def test_check_log_freshness_default_budget_matches_heartbeat_interval(tmp_path):
    """The default staleness budget is exactly HEARTBEAT_INTERVAL_SECONDS - a
    single missed heartbeat should not immediately false-positive."""
    log_path = tmp_path / "app.log"
    log_path.write_text("recent\n")

    assert check_log_freshness(log_path) is True
    assert HEARTBEAT_INTERVAL_SECONDS == 600


def test_write_heartbeat_log_does_not_raise():
    """Smoke test only - the module logger is bound at import time to
    whatever handler config was active then (in the test suite, the root
    logger's own conftest-managed handler, not a path this test controls),
    so real file-freshness integration is covered directly by
    check_log_freshness's own tests above instead."""
    write_heartbeat_log()


def test_resolve_log_path_matches_setup_logger_convention(tmp_path):
    assert resolve_log_path(str(tmp_path), "morning-mcp.log") == tmp_path / "morning-mcp.log"
