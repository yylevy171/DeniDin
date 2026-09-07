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
    archive_state_file,
    decide_action,
    main,
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
    def test_no_baseline_yet_triggers_bootstrap(self):
        # 2026-09-06 revision (bugfix-043): a missing state file now means
        # "start it now via the proper channel" (bootstrap), not "do
        # nothing" - see run_env.sh/stop_env.sh, which rely on this to make
        # the prober itself the one thing that ever calls run_all.sh, on
        # every kind of start (fresh install, admin-requested, crash/reboot
        # recovery alike). stop_env.sh archives (rather than silently
        # deleting) the state file precisely so this branch is reached on
        # every deliberate start, not just a true first-ever install.
        assert decide_action(None, now=1000.0) == "bootstrap"

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


class TestArchiveStateFile:
    def test_no_existing_state_file_returns_none(self, tmp_path):
        assert archive_state_file(tmp_path / "state.json", now=1000.0) is None

    def test_archives_with_timestamp_in_filename_and_removes_original(self, tmp_path):
        state_file = tmp_path / "state.json"
        write_last_up_time(state_file, 12345.0)

        archive_path = archive_state_file(state_file, now=99999.0)

        assert archive_path is not None
        assert archive_path.name == "state_stopped_99999.json"
        assert not state_file.exists()
        archived = json.loads(archive_path.read_text())
        assert archived["last_up_time"] == 12345.0
        assert archived["stopped_at"] == 99999.0

    def test_repeated_stops_never_overwrite_each_other(self, tmp_path):
        state_file = tmp_path / "state.json"
        write_last_up_time(state_file, 1.0)
        first_archive = archive_state_file(state_file, now=100.0)

        write_last_up_time(state_file, 2.0)
        second_archive = archive_state_file(state_file, now=200.0)

        assert first_archive != second_archive
        assert first_archive.exists()
        assert second_archive.exists()

    def test_corrupt_state_file_still_archives_without_crashing(self, tmp_path):
        state_file = tmp_path / "state.json"
        state_file.write_text("not valid json{{{")

        archive_path = archive_state_file(state_file, now=500.0)

        assert archive_path is not None
        assert not state_file.exists()
        assert json.loads(archive_path.read_text())["stopped_at"] == 500.0


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

    def test_no_state_file_and_unhealthy_reports_bootstrap(self, tmp_path, health_server):
        # No seed_last_up passed at all - simulates run_env.sh's normal case
        # (stop_env.sh already archived any prior state, or this is a
        # genuinely fresh install) where the apps aren't up yet.
        url, set_status = health_server
        set_status(503)
        action, state_file, log_file = self._run(tmp_path, url, url, now=5000.0)
        assert action == "bootstrap"
        assert not state_file.exists()  # dry_run must never write a baseline on failure
        entry = json.loads(log_file.read_text().splitlines()[-1])
        assert entry["action"] == "bootstrap"


class TestMainArchiveStateCLI:
    """The --archive-state CLI mode - what stop_env.sh actually invokes."""

    def test_archive_state_flag_archives_and_exits_zero(self, tmp_path, capsys):
        state_file = tmp_path / "state.json"
        write_last_up_time(state_file, 42.0)

        exit_code = main(["--env", "dev", "--state-file", str(state_file), "--archive-state"])

        assert exit_code == 0
        assert not state_file.exists()
        archives = list(tmp_path.glob("state_stopped_*.json"))
        assert len(archives) == 1
        assert "archived=" in capsys.readouterr().out

    def test_archive_state_flag_with_no_existing_file_still_exits_zero(self, tmp_path, capsys):
        state_file = tmp_path / "state.json"
        exit_code = main(["--env", "dev", "--state-file", str(state_file), "--archive-state"])
        assert exit_code == 0
        assert "archived=none" in capsys.readouterr().out

    def test_missing_probe_args_without_archive_state_errors_out(self, tmp_path):
        state_file = tmp_path / "state.json"
        with pytest.raises(SystemExit):
            main(["--env", "dev", "--state-file", str(state_file)])
