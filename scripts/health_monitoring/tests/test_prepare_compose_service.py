"""bugfix-066: prepare_compose_service.sh bind-source guard, run against a stand-in `docker` on PATH
that answers only `compose config --format json` / `compose ps` (no daemon, no environment touched)."""
import json
import os
import stat
import subprocess
from pathlib import Path

LIB = Path(__file__).resolve().parents[2] / "lib" / "prepare_compose_service.sh"


def _run(tmp_path, volumes):
    cfg = {"services": {"svc": {"volumes": [{"type": "bind", "source": s, "target": t} for s, t in volumes]}}}
    (tmp_path / "cfg.json").write_text(json.dumps(cfg))
    bindir = tmp_path / "bin"
    bindir.mkdir()
    docker = bindir / "docker"
    docker.write_text(
        '#!/bin/bash\n'
        'case "$*" in\n'
        f'  *"config --format json"*) cat {tmp_path}/cfg.json;;\n'
        '  *) ;;\n'
        'esac\n'
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    r = subprocess.run(
        ["bash", "-c", f'source "{LIB}"; prepare_compose_service svc -f x.yml'],
        env={**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}, capture_output=True, text=True,
    )
    return r.returncode, r.stderr


def test_valid_layout_passes(tmp_path):
    c = tmp_path / "config"
    (c / "tpl").mkdir(parents=True)
    (c / "tpl" / "a.docx").write_text("x")
    (c / "prompt.md").write_text("x")
    assert _run(tmp_path, [(str(c / "prompt.md"), "/a/p.md"), (str(c / "tpl"), "/a/tpl")])[0] == 0


def test_missing_config_file_rejected(tmp_path):
    (tmp_path / "config").mkdir()
    rc, err = _run(tmp_path, [(str(tmp_path / "config" / "prompt.md"), "/a/p.md")])
    assert rc == 1 and "does not exist" in err


def test_file_mount_that_is_a_directory_rejected(tmp_path):
    (tmp_path / "config" / "prompt.md").mkdir(parents=True)
    rc, err = _run(tmp_path, [(str(tmp_path / "config" / "prompt.md"), "/a/p.md")])
    assert rc == 1 and "DIRECTORY" in err


def test_empty_directory_mount_rejected(tmp_path):
    (tmp_path / "config" / "tpl").mkdir(parents=True)
    rc, err = _run(tmp_path, [(str(tmp_path / "config" / "tpl"), "/a/tpl")])
    assert rc == 1 and "EMPTY" in err


def test_non_config_data_dir_not_required(tmp_path):
    assert _run(tmp_path, [(str(tmp_path / "data_not_yet"), "/app/data")])[0] == 0
