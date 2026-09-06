"""Real, non-mocked tests for the admin-stop/start-aware prober wiring added
2026-09-06 (bugfix-043 revision): prober_paths.sh's argument resolution,
run_prober_for_env.sh's argument construction, register_prober_schedule.sh's
real macOS LaunchAgent enable/disable (the Linux/schtasks.exe path has no
automated coverage here - see that script's own header comment for why), and
scripts/stop_env.sh + scripts/run_env.sh's call ordering.

Per CONSTITUTION SS I/V: real subprocess calls throughout, real launchd on the
Darwin-only tests, no unittest.mock. Where a real container/app isn't
available (there's no real dev/prod running during a unit-test sweep),
sibling scripts are replaced with small, real, harmless stub scripts in a
scratch tree - the same "throwaway trivial script instead of a mock" pattern
scripts/tests/conftest.py already uses for cut_release.sh/deploy_release.sh.
"""
import json
import platform
import shutil
import stat
import subprocess
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HEALTH_MONITORING_DIR = REPO_ROOT / "scripts" / "health_monitoring"
PROBER_PATHS_SCRIPT = HEALTH_MONITORING_DIR / "prober_paths.sh"
RUN_PROBER_SCRIPT = HEALTH_MONITORING_DIR / "run_prober_for_env.sh"
REGISTER_SCHEDULE_SCRIPT = HEALTH_MONITORING_DIR / "register_prober_schedule.sh"
STOP_ENV_SCRIPT = REPO_ROOT / "scripts" / "stop_env.sh"
RUN_ENV_SCRIPT = REPO_ROOT / "scripts" / "run_env.sh"


def _make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def scratch_env_repo(tmp_path):
    """A scratch repo tree with just enough of the real layout for
    prober_paths.sh / run_prober_for_env.sh to resolve real config values
    against - a fake apps/denidin-app/config/config.<env>.json and
    apps/morning-mcp-app/config/config.<env>.json with known, distinct
    ports."""
    repo = tmp_path / "scratch_env_repo"
    (repo / "apps" / "denidin-app" / "config").mkdir(parents=True)
    (repo / "apps" / "morning-mcp-app" / "config").mkdir(parents=True)
    (repo / "scripts" / "health_monitoring").mkdir(parents=True)

    for env, denidin_port, morning_port in (("dev", 8100, 8000), ("prod", 8101, 8001)):
        (repo / "apps" / "denidin-app" / "config" / f"config.{env}.json").write_text(
            json.dumps({"health_check_port": denidin_port})
        )
        (repo / "apps" / "morning-mcp-app" / "config" / f"config.{env}.json").write_text(
            json.dumps({"mcp": {"port": morning_port}})
        )

    shutil.copy(PROBER_PATHS_SCRIPT, repo / "scripts" / "health_monitoring" / "prober_paths.sh")
    shutil.copy(RUN_PROBER_SCRIPT, repo / "scripts" / "health_monitoring" / "run_prober_for_env.sh")
    _make_executable(repo / "scripts" / "health_monitoring" / "run_prober_for_env.sh")

    return repo


def test_prober_paths_resolve_ports_and_container_names(scratch_env_repo):
    script = f"""
        set -e
        REPO_ROOT="{scratch_env_repo}"
        source "{scratch_env_repo}/scripts/health_monitoring/prober_paths.sh"
        echo "denidin_url=$(prober_denidin_health_url dev)"
        echo "morning_url=$(prober_morning_health_url dev)"
        echo "denidin_container=$(prober_denidin_container prod)"
        echo "morning_container=$(prober_morning_container prod)"
        echo "state_file=$(prober_state_file dev)"
    """
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    output = result.stdout

    assert "denidin_url=http://127.0.0.1:8100/health" in output
    assert "morning_url=http://127.0.0.1:8000/health" in output
    assert "denidin_container=denidin-prod-denidin-app-prod-1" in output
    assert "morning_container=denidin-prod-morning-mcp-app-prod-1" in output
    assert f"state_file={scratch_env_repo}/logs/health_monitoring/dev/state.json" in output


def test_run_prober_for_env_constructs_correct_prober_invocation(scratch_env_repo):
    """Replaces prober.py itself with a stub that just prints its own argv,
    so this proves run_prober_for_env.sh wires prober_paths.sh's resolved
    values into the real command line - not that prober.py's own logic
    works (that's test_prober.py's job)."""
    stub_prober = scratch_env_repo / "scripts" / "health_monitoring" / "prober.py"
    stub_prober.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('ARGV:' + '|'.join(sys.argv[1:]))\n"
    )
    _make_executable(stub_prober)

    result = subprocess.run(
        [str(scratch_env_repo / "scripts" / "health_monitoring" / "run_prober_for_env.sh"), "dev", "--dry-run"],
        capture_output=True, text=True, check=True,
    )

    argv_line = next(line for line in result.stdout.splitlines() if line.startswith("ARGV:"))
    argv = argv_line[len("ARGV:"):].split("|")
    assert "--env" in argv and argv[argv.index("--env") + 1] == "dev"
    assert argv[argv.index("--denidin-health-url") + 1] == "http://127.0.0.1:8100/health"
    assert argv[argv.index("--morning-health-url") + 1] == "http://127.0.0.1:8000/health"
    assert argv[argv.index("--denidin-container") + 1] == "denidin-dev-denidin-app-dev-1"
    assert argv[argv.index("--morning-container") + 1] == "denidin-dev-morning-mcp-app-dev-1"
    assert "--dry-run" in argv


@pytest.mark.skipif(platform.system() != "Darwin", reason="LaunchAgent path is macOS-only")
class TestRegisterProberScheduleDarwin:
    """Exercises the real launchd - a throwaway, uniquely-labeled LaunchAgent
    per test (never the real com.denidin.healthprobe.<env> label), always
    unloaded/removed in a finally block so nothing survives a test failure."""

    @pytest.fixture
    def scratch_schedule_script(self, tmp_path):
        """A scratch copy of register_prober_schedule.sh + a stub sibling
        run_prober_for_env.sh (so trigger-once's fallback direct-invocation
        path is harmless), with a unique label so tests never collide with
        the real schedule or each other."""
        scratch_dir = tmp_path / "health_monitoring"
        scratch_dir.mkdir()
        shutil.copy(REGISTER_SCHEDULE_SCRIPT, scratch_dir / "register_prober_schedule.sh")
        _make_executable(scratch_dir / "register_prober_schedule.sh")

        marker_file = tmp_path / "ran_marker.txt"
        stub_runner = scratch_dir / "run_prober_for_env.sh"
        stub_runner.write_text(f"#!/bin/bash\necho \"ran env=$1\" >> \"{marker_file}\"\n")
        _make_executable(stub_runner)

        unique_env = f"test{uuid.uuid4().hex[:8]}"
        # register_prober_schedule.sh only accepts dev|prod - patch a scratch copy
        # to accept this test's unique pseudo-env instead, so labels/plists never
        # collide across parallel test runs or with the real dev/prod schedules.
        content = (scratch_dir / "register_prober_schedule.sh").read_text()
        content = content.replace(
            'if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then',
            f'if [ "$ENV" != "{unique_env}" ]; then',
        )
        (scratch_dir / "register_prober_schedule.sh").write_text(content)

        yield scratch_dir / "register_prober_schedule.sh", unique_env, marker_file

        # Teardown: make sure the real launchd has nothing left for this label.
        label = f"com.denidin.healthprobe.{unique_env}"
        subprocess.run(["launchctl", "unload",
                        str(Path.home() / "Library/LaunchAgents" / f"{label}.plist")],
                        capture_output=True)
        (Path.home() / "Library/LaunchAgents" / f"{label}.plist").unlink(missing_ok=True)

    def _launchctl_list_has_label(self, label):
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        return label in result.stdout

    def test_enable_registers_and_loads_launch_agent(self, scratch_schedule_script):
        script, env, _marker = scratch_schedule_script
        label = f"com.denidin.healthprobe.{env}"

        result = subprocess.run([str(script), env, "enable"], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert (Path.home() / "Library/LaunchAgents" / f"{label}.plist").exists()
        assert self._launchctl_list_has_label(label)

    def test_enable_is_idempotent(self, scratch_schedule_script):
        script, env, _marker = scratch_schedule_script
        first = subprocess.run([str(script), env, "enable"], capture_output=True, text=True)
        second = subprocess.run([str(script), env, "enable"], capture_output=True, text=True)
        assert first.returncode == 0
        assert second.returncode == 0

    def test_disable_unloads_and_removes_plist(self, scratch_schedule_script):
        script, env, _marker = scratch_schedule_script
        label = f"com.denidin.healthprobe.{env}"
        subprocess.run([str(script), env, "enable"], check=True, capture_output=True)

        result = subprocess.run([str(script), env, "disable"], capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert not (Path.home() / "Library/LaunchAgents" / f"{label}.plist").exists()
        assert not self._launchctl_list_has_label(label)

    def test_disable_without_prior_enable_does_not_fail(self, scratch_schedule_script):
        script, env, _marker = scratch_schedule_script
        result = subprocess.run([str(script), env, "disable"], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_trigger_once_without_enable_runs_directly(self, scratch_schedule_script):
        """trigger-once's fallback path (schedule not registered) must still
        actually run the probe, not silently no-op."""
        script, env, marker = scratch_schedule_script
        result = subprocess.run([str(script), env, "trigger-once"], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert marker.exists()
        assert f"ran env={env}" in marker.read_text()

    def test_trigger_once_after_enable_eventually_runs_via_launchd(self, scratch_schedule_script):
        script, env, marker = scratch_schedule_script
        subprocess.run([str(script), env, "enable"], check=True, capture_output=True)

        result = subprocess.run([str(script), env, "trigger-once"], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

        # launchd's `launchctl start` is asynchronous - poll briefly rather
        # than asserting immediately.
        deadline = time.time() + 10
        while time.time() < deadline and not marker.exists():
            time.sleep(0.2)
        assert marker.exists(), "launchd never ran the LaunchAgent after `launchctl start`"
        assert f"ran env={env}" in marker.read_text()


class TestStopEnvRunEnvOrdering:
    """Verifies stop_env.sh/run_env.sh call their sub-steps in the required
    order, using real (but stubbed, harmless) sibling scripts in a scratch
    tree - never real launchd/docker/prober.py."""

    @pytest.fixture
    def scratch_ops_repo(self, tmp_path):
        repo = tmp_path / "scratch_ops_repo"
        (repo / "scripts" / "health_monitoring").mkdir(parents=True)
        shutil.copy(STOP_ENV_SCRIPT, repo / "scripts" / "stop_env.sh")
        shutil.copy(RUN_ENV_SCRIPT, repo / "scripts" / "run_env.sh")
        shutil.copy(PROBER_PATHS_SCRIPT, repo / "scripts" / "health_monitoring" / "prober_paths.sh")
        for f in ("stop_env.sh", "run_env.sh"):
            _make_executable(repo / "scripts" / f)

        call_log = repo / "call_log.txt"

        def _stub_bash(name):
            path = repo / "scripts" / name if name == "stop_all.sh" else repo / "scripts" / "health_monitoring" / name
            path.write_text(f"#!/bin/bash\necho \"{name} $*\" >> \"{call_log}\"\n")
            _make_executable(path)

        _stub_bash("stop_all.sh")
        _stub_bash("register_prober_schedule.sh")

        # prober.py is invoked as `python3 .../prober.py --archive-state ...` by
        # stop_env.sh - the stub must be valid Python, not a bash echo one-liner.
        prober_stub = repo / "scripts" / "health_monitoring" / "prober.py"
        prober_stub.write_text(
            "import sys\n"
            f"with open({str(call_log)!r}, 'a') as f:\n"
            "    f.write('prober.py ' + ' '.join(sys.argv[1:]) + chr(10))\n"
        )
        _make_executable(prober_stub)

        return repo, call_log

    def test_stop_env_disables_prober_before_stopping_apps(self, scratch_ops_repo):
        repo, call_log = scratch_ops_repo
        result = subprocess.run([str(repo / "scripts" / "stop_env.sh"), "dev"],
                                 capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

        calls = call_log.read_text().splitlines()
        disable_idx = next(i for i, c in enumerate(calls) if "register_prober_schedule.sh dev disable" in c)
        stop_all_idx = next(i for i, c in enumerate(calls) if c.startswith("stop_all.sh dev"))
        assert disable_idx < stop_all_idx, f"expected disable before stop_all, got: {calls}"

    def test_stop_env_rejects_bad_env(self, scratch_ops_repo):
        repo, _call_log = scratch_ops_repo
        result = subprocess.run([str(repo / "scripts" / "stop_env.sh"), "staging"],
                                 capture_output=True, text=True)
        assert result.returncode != 0

    def test_run_env_enables_then_triggers(self, scratch_ops_repo):
        repo, call_log = scratch_ops_repo
        result = subprocess.run([str(repo / "scripts" / "run_env.sh"), "dev"],
                                 capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

        calls = call_log.read_text().splitlines()
        enable_idx = next(i for i, c in enumerate(calls) if "register_prober_schedule.sh dev enable" in c)
        trigger_idx = next(i for i, c in enumerate(calls) if "register_prober_schedule.sh dev trigger-once" in c)
        assert enable_idx < trigger_idx, f"expected enable before trigger-once, got: {calls}"

    def test_run_env_rejects_bad_env(self, scratch_ops_repo):
        repo, _call_log = scratch_ops_repo
        result = subprocess.run([str(repo / "scripts" / "run_env.sh"), "staging"],
                                 capture_output=True, text=True)
        assert result.returncode != 0
