"""Real (non-mocked) tests for register_backup_schedule.sh's Darwin/"pull"
branch (Feature 078, T020/T021) - a real, uniquely-labeled, throwaway
LaunchAgent is loaded/unloaded/verified against the real launchd, same
pattern as scripts/health_monitoring/tests/test_env_scripts.py.

The Linux/schtasks.exe "run" branch has NO automated coverage here - same
documented, accepted gap as register_prober_schedule.sh's own Linux branch
(see that script's header comment) - verified manually against the real
Windows box instead.
"""
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTER_SCRIPT = REPO_ROOT / "scripts" / "backup_prod" / "register_backup_schedule.sh"


def _make_executable(path: Path):
    import stat
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@pytest.mark.skipif(shutil.os.uname().sysname != "Darwin", reason="LaunchAgent branch is Darwin-only")
class TestRegisterBackupScheduleDarwin:

    @pytest.fixture
    def scratch_schedule(self, tmp_path):
        """A scratch copy of register_backup_schedule.sh with a unique
        role/label suffix, plus a stub pull_backups.sh sibling so
        trigger-once's fallback direct-invocation path is harmless and
        observable, isolated from the real pull_backups.sh/label."""
        scratch_dir = tmp_path / "backup_prod"
        scratch_dir.mkdir()
        script_path = scratch_dir / "register_backup_schedule.sh"
        shutil.copy(REGISTER_SCRIPT, script_path)
        _make_executable(script_path)

        unique_suffix = uuid.uuid4().hex[:8]
        marker_file = tmp_path / "ran_marker.txt"
        stub_runner = scratch_dir / "pull_backups.sh"
        stub_runner.write_text(f"#!/bin/bash\necho \"ran args=$*\" >> \"{marker_file}\"\n")
        _make_executable(stub_runner)

        content = script_path.read_text()
        # Give this test its own unique label so it never collides with the
        # real com.denidin.backuppull schedule or other parallel test runs.
        content = content.replace(
            'LABEL="com.denidin.backup${ROLE}"',
            f'LABEL="com.denidin.backuptest{unique_suffix}"',
        )
        script_path.write_text(content)

        config_path = tmp_path / "config.json"
        config_path.write_text("{}")

        yield script_path, config_path, marker_file

        label = f"com.denidin.backuptest{unique_suffix}"
        plist = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        plist.unlink(missing_ok=True)

    def _label_for(self, script_path):
        content = script_path.read_text()
        for line in content.splitlines():
            if line.startswith('LABEL="com.denidin.backuptest'):
                return line.split('"')[1]
        raise AssertionError("could not find patched LABEL in scratch script")

    def _launchctl_list_has_label(self, label):
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        return label in result.stdout

    def test_enable_registers_and_loads_launch_agent(self, scratch_schedule):
        script, config, _marker = scratch_schedule
        label = self._label_for(script)

        result = subprocess.run(
            [str(script), "pull", "enable", "--config", str(config)],
            capture_output=True, text=True,
        )

        assert result.returncode == 0, result.stderr
        plist = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
        assert plist.exists()
        assert self._launchctl_list_has_label(label)
        assert str(config) in plist.read_text()

    def test_enable_is_idempotent(self, scratch_schedule):
        script, config, _marker = scratch_schedule
        first = subprocess.run([str(script), "pull", "enable", "--config", str(config)],
                                capture_output=True, text=True)
        second = subprocess.run([str(script), "pull", "enable", "--config", str(config)],
                                 capture_output=True, text=True)
        assert first.returncode == 0, first.stderr
        assert second.returncode == 0, second.stderr

    def test_disable_unloads_and_removes_plist(self, scratch_schedule):
        script, config, _marker = scratch_schedule
        label = self._label_for(script)
        subprocess.run([str(script), "pull", "enable", "--config", str(config)], check=True, capture_output=True)

        result = subprocess.run([str(script), "pull", "disable"], capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        plist = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
        assert not plist.exists()
        assert not self._launchctl_list_has_label(label)

    def test_disable_without_prior_enable_does_not_fail(self, scratch_schedule):
        script, _config, _marker = scratch_schedule
        result = subprocess.run([str(script), "pull", "disable"], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_run_role_rejected_on_darwin(self, scratch_schedule):
        script, config, _marker = scratch_schedule
        result = subprocess.run([str(script), "run", "enable", "--config", str(config)],
                                 capture_output=True, text=True)
        assert result.returncode != 0
        assert "Linux/WSL2-only" in result.stderr

    def test_missing_config_required_for_enable(self, scratch_schedule):
        script, _config, _marker = scratch_schedule
        result = subprocess.run([str(script), "pull", "enable"], capture_output=True, text=True)
        assert result.returncode != 0
