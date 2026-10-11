"""bugfix-066: the prober surfaces a launch failure (script output incl. Docker's error) in its log."""
import json
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prober import run_once, run_soft_restart  # noqa: E402


def _script(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/bash\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _scripts_dir(tmp_path, launch_body):
    _script(tmp_path / "scripts" / "stop_all.sh", "exit 0\n")
    _script(tmp_path / "scripts" / "run_all_and_verify_healthy.sh", launch_body)
    return tmp_path


def test_soft_restart_returns_exit_code_and_output(tmp_path):
    d = _scripts_dir(tmp_path, 'echo "denidin-app-prod: state=created error=not a directory" >&2; exit 1\n')
    code, out = run_soft_restart("dev", d)
    assert code == 1
    assert "not a directory" in out


def test_soft_restart_success_returns_zero(tmp_path):
    d = _scripts_dir(tmp_path, "echo healthy; exit 0\n")
    assert run_soft_restart("dev", d)[0] == 0


def _run(tmp_path, d):
    state, log = tmp_path / "state.json", tmp_path / "health.log"
    action = run_once(
        env="dev", denidin_health_url="http://127.0.0.1:1/health", morning_health_url="http://127.0.0.1:1/health",
        state_file=state, log_file=log, scripts_dir=d,
        denidin_container="x", morning_container="y", dry_run=False, now=1000.0,
    )
    return action, [json.loads(l) for l in log.read_text().splitlines()]


def test_failed_launch_is_logged_with_docker_error(tmp_path):
    d = _scripts_dir(tmp_path, 'echo "Error response from daemon: not a directory" >&2; exit 1\n')
    action, entries = _run(tmp_path, d)
    assert action == "bootstrap"
    assert "not a directory" in entries[-1]["launch_error"]


def test_successful_launch_has_no_launch_error(tmp_path):
    d = _scripts_dir(tmp_path, "exit 0\n")
    _, entries = _run(tmp_path, d)
    assert "launch_error" not in entries[-1]
