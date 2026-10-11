"""Real (non-mocked) tests for lib/load_config.sh (Feature 078).

Per CONSTITUTION SS I/V: real subprocess calls against the real script, real
scratch config.json fixtures on disk - no unittest.mock.
"""
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LOAD_CONFIG_SCRIPT = REPO_ROOT / "scripts" / "backup_prod" / "lib" / "load_config.sh"


def _run(config_path, keys):
    """Sources load_config.sh, calls load_backup_config, then echoes each
    resulting uppercased var so the test can assert on stdout."""
    key_args = " ".join(f'"{k}"' for k in keys)
    echo_lines = "\n".join(f'echo "{k.upper()}=${{{k.upper()}}}"' for k in keys)
    script = f"""
set -e
source "{LOAD_CONFIG_SCRIPT}"
load_backup_config "{config_path}" {key_args}
{echo_lines}
"""
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_load_config_success(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"data_dir": "/tmp/data", "daily_backup_dir": "/tmp/backups"}))

    result = _run(config, ["data_dir", "daily_backup_dir"])

    assert result.returncode == 0, result.stderr
    assert "DATA_DIR=/tmp/data" in result.stdout
    assert "DAILY_BACKUP_DIR=/tmp/backups" in result.stdout


def test_load_config_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.json"

    result = _run(missing, ["data_dir"])

    assert result.returncode != 0
    assert "not found" in result.stderr


def test_load_config_malformed_json(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{not valid json")

    result = _run(config, ["data_dir"])

    assert result.returncode != 0
    assert "not valid JSON" in result.stderr


def test_load_config_missing_required_key(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"data_dir": "/tmp/data"}))

    result = _run(config, ["data_dir", "daily_backup_dir"])

    assert result.returncode != 0
    assert "daily_backup_dir" in result.stderr
    assert "missing or empty" in result.stderr


def test_load_config_empty_string_value_treated_as_missing(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"data_dir": ""}))

    result = _run(config, ["data_dir"])

    assert result.returncode != 0
    assert "missing or empty" in result.stderr
