"""Stage 0.3b — finalize_migration CLI surface + fail-closed preconditions (no network)."""
import json
from pathlib import Path

import pytest

import finalize_migration as cli


def _data_root(tmp_path: Path) -> Path:
    dr = tmp_path / "data"
    (dr / "sessions").mkdir(parents=True)
    return dr


class TestParser:
    def test_required_data_root(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args([])

    def test_chat_repeatable(self):
        ns = cli._build_parser().parse_args(["--data-root", "d", "--chat", "a@c.us", "--chat", "b@g.us"])
        assert ns.chat == ["a@c.us", "b@g.us"] and ns.report_only is False and ns.now is None


class TestPreconditions:
    def _run(self, capsys, *args):
        return cli.main(list(args)), capsys.readouterr().err

    def test_missing_data_root(self, tmp_path, capsys):
        rc, err = self._run(capsys, "--data-root", str(tmp_path / "nope"))
        assert rc == 1 and "data-root" in err

    def test_no_sessions_dir(self, tmp_path, capsys):
        dr = tmp_path / "data"
        dr.mkdir()
        rc, err = self._run(capsys, "--data-root", str(dr))
        assert rc == 1 and "sessions" in err

    def test_bad_now(self, tmp_path, capsys):
        rc, err = self._run(capsys, "--data-root", str(_data_root(tmp_path)), "--now", "not-a-date")
        assert rc == 1 and "now" in err

    def test_unknown_chat(self, tmp_path, capsys):
        rc, err = self._run(capsys, "--data-root", str(_data_root(tmp_path)), "--chat", "ghost@c.us")
        assert rc == 1 and "ghost@c.us" in err

    def test_empty_data_root_is_noop(self, tmp_path, capsys):
        rc, out = cli.main(["--data-root", str(_data_root(tmp_path))]), capsys.readouterr().out
        assert rc == 0 and "No chats" in out
