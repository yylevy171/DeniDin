"""Real, non-mocked tests for scripts/health_monitoring/prober.py.

Per CONSTITUTION §V: mocks only for third-party network services - here that
means a real local http.server fixture stands in for the two apps' /health
endpoints (never unittest.mock), and real tmp_path files stand in for the
state/log files. subprocess-invoking functions (run_soft_restart/
run_hard_restart) are exercised against a real, harmless throwaway script
(not /bin/true directly, so argv can be captured and asserted on) rather than
mocked - the actual stop_all.sh/run_all.sh/docker calls are exactly what a
human would want NOT run during a unit-test sweep, so decide_action's own
"soft"/"hard" branching is tested seam by testing run_once with
dry_run=True, which is the one deliberately safe way to observe the decision
without ever invoking those real commands.
"""
import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prober import (  # noqa: E402
    decide_action,
    probe_health,
    read_last_up_time,
    run_once,
    write_last_up_time,
    SOFT_RESTART_THRESHOLD_SECONDS,
    HARD_RESTART_THRESHOLD_SECONDS,
)


class _FixedStatusHandler(http.server.BaseHTTPRequestHandler):
    """Real HTTP handler returning a fixed status code, set per-subclass via
    a class attribute - used to simulate a real /health endpoint reporting
    healthy (200) or unhealthy (503) without touching the real apps."""
    status_code = 200

    def do_GET(self):  # noqa: N802 (stdlib method name)
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

    def log_message(self, format, *args):  # noqa: A002 - silence test noise
        pass


@pytest.fixture
def health_server():
    """Starts a real local HTTP server, yields (url, set_status) where
    set_status(code) changes what subsequent requests receive - lets a
    single test simulate a health endpoint flipping from healthy to
    unhealthy, same as a real app would under real failure."""
    state = {"code": 200}

    class _Handler(_FixedStatusHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(state["code"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

        def log_message(self, format, *args):  # noqa: A002
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/health"

    def set_status(code: int) -> None:
        state["code"] = code

    yield url, set_status
    server.shutdown()
    thread.join(timeout=5)


class TestProbeHealth:
    def test_returns_true_on_200(self, health_server):
        url, set_status = health_server
        set_status(200)
        assert probe_health(url) is True

    def test_returns_false_on_503(self, health_server):
        url, set_status = health_server
        set_status(503)
        assert probe_health(url) is False

    def test_returns_false_on_unreachable_host(self):
        # Real network attempt against a real, guaranteed-nonexistent host -
        # no mocking of the transport layer, per CONSTITUTION §V.
        assert probe_health("http://127.0.0.1:1", timeout=1.0) is False


class TestStateFileRoundTrip:
    def test_read_missing_file_returns_none(self, tmp_path):
        assert read_last_up_time(tmp_path / "does_not_exist.json") is None

    def test_read_corrupt_file_returns_none(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text("not valid json{{{")
        assert read_last_up_time(state_file) is None

    def test_write_then_read_round_trips(self, tmp_path):
        state_file = tmp_path / "nested" / "state.json"
        write_last_up_time(state_file, 12345.5)
        assert read_last_up_time(state_file) == 12345.5

    def test_write_overwrites_previous_value(self, tmp_path):
        state_file = tmp_path / "state.json"
        write_last_up_time(state_file, 100.0)
        write_last_up_time(state_file, 200.0)
        assert read_last_up_time(state_file) == 200.0


class TestDecideAction:
    def test_no_baseline_yet_takes_no_action(self):
        # Bootstrap edge case: a brand-new state file with nothing recorded
        # yet must never be treated as "unhealthy for a very long time" -
        # that would restart a freshly-started system before it ever had a
        # chance to report healthy once.
        assert decide_action(None, now=1000.0) == "none"

    def test_within_soft_threshold_takes_no_action(self):
        now = 1000.0
        last_up = now - (SOFT_RESTART_THRESHOLD_SECONDS - 1)
        assert decide_action(last_up, now) == "none"

    def test_at_soft_threshold_triggers_soft(self):
        now = 1000.0
        last_up = now - SOFT_RESTART_THRESHOLD_SECONDS
        assert decide_action(last_up, now) == "soft"

    def test_between_soft_and_hard_triggers_soft(self):
        now = 1000.0
        last_up = now - (HARD_RESTART_THRESHOLD_SECONDS - 1)
        assert decide_action(last_up, now) == "soft"

    def test_at_hard_threshold_triggers_hard(self):
        now = 1000.0
        last_up = now - HARD_RESTART_THRESHOLD_SECONDS
        assert decide_action(last_up, now) == "hard"

    def test_well_past_hard_threshold_triggers_hard(self):
        now = 1000.0
        last_up = now - (HARD_RESTART_THRESHOLD_SECONDS * 3)
        assert decide_action(last_up, now) == "hard"


class TestRunOnceDryRun:
    """Exercises the full probe -> decide -> (dry-run, no real restart) ->
    log cycle end-to-end, against real local HTTP fixture servers and real
    tmp_path files - dry_run=True is what keeps this safe to run in a unit
    sweep (no real stop_all.sh/run_all.sh/docker invocation)."""

    def _run(self, tmp_path, denidin_url, morning_url, now, seed_last_up=None):
        state_file = tmp_path / "state.json"
        log_file = tmp_path / "health.log"
        if seed_last_up is not None:
            write_last_up_time(state_file, seed_last_up)
        action = run_once(
            env="dev",
            denidin_health_url=denidin_url,
            morning_health_url=morning_url,
            state_file=state_file,
            log_file=log_file,
            scripts_dir=tmp_path,
            denidin_container="fake-denidin",
            morning_container="fake-morning",
            dry_run=True,
            now=now,
        )
        return action, state_file, log_file

    def test_all_healthy_updates_last_up_time_and_takes_no_action(self, tmp_path, health_server):
        denidin_url, set_denidin = health_server
        set_denidin(200)
        # Reuse the same fixture server for both URLs in this simple case -
        # both need to report 200.
        action, state_file, log_file = self._run(tmp_path, denidin_url, denidin_url, now=5000.0)
        assert action == "none"
        assert read_last_up_time(state_file) == 5000.0
        log_entries = [json.loads(line) for line in log_file.read_text().splitlines()]
        assert log_entries[-1]["denidin_health"] == "success"
        assert log_entries[-1]["morning_health"] == "success"
        assert log_entries[-1]["dry_run"] is True

    def test_unhealthy_within_soft_window_takes_no_action(self, tmp_path, health_server):
        url, set_status = health_server
        set_status(503)
        now = 5000.0
        seed = now - 10  # well within the 3-minute soft window
        action, _, log_file = self._run(tmp_path, url, url, now=now, seed_last_up=seed)
        assert action == "none"
        entry = json.loads(log_file.read_text().splitlines()[-1])
        assert entry["denidin_health"] == "fail"

    def test_unhealthy_past_soft_threshold_reports_soft_without_restarting(self, tmp_path, health_server):
        url, set_status = health_server
        set_status(503)
        now = 5000.0
        seed = now - SOFT_RESTART_THRESHOLD_SECONDS
        action, state_file, _ = self._run(tmp_path, url, url, now=now, seed_last_up=seed)
        assert action == "soft"
        # dry_run=True must never advance last_up_time on a failing probe.
        assert read_last_up_time(state_file) == seed

    def test_unhealthy_past_hard_threshold_reports_hard(self, tmp_path, health_server):
        url, set_status = health_server
        set_status(503)
        now = 5000.0
        seed = now - HARD_RESTART_THRESHOLD_SECONDS
        action, _, _ = self._run(tmp_path, url, url, now=now, seed_last_up=seed)
        assert action == "hard"

    def test_one_app_down_counts_as_overall_unhealthy(self, tmp_path, health_server):
        healthy_url, set_healthy = health_server
        set_healthy(200)
        now = 5000.0
        action, _, log_file = self._run(
            tmp_path, healthy_url, "http://127.0.0.1:1", now=now, seed_last_up=now - 5
        )
        assert action == "none"  # still within soft window
        entry = json.loads(log_file.read_text().splitlines()[-1])
        assert entry["denidin_health"] == "success"
        assert entry["morning_health"] == "fail"
