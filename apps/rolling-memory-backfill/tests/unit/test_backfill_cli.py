"""T040a — backfill CLI contract & preconditions (non-billed, no network).

Every precondition branch fails closed with ``⚠️`` to stderr and ``return 1``
*before* any real component is constructed. Also covers the argparse surface,
``--until`` defaulting, and the date-range helper.
"""
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import backfill_daily_summaries as cli


def _good_config(tmp_path: Path) -> Path:
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "ai_api_key": "sk-fake",
        "ai_embedding_model": "text-embedding-3-large",
        "ai_model": "gpt-5.6-luna",
        "memory": {"session": {"window_days": 14}, "roll": {"hour": 2}},
    }), encoding="utf-8")
    return p


def _good_data_root(tmp_path: Path) -> Path:
    dr = tmp_path / "data"
    (dr / "sessions").mkdir(parents=True)
    return dr


class TestParser:
    def test_required_flags(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args([])

    def test_chat_is_repeatable(self):
        ns = cli._build_parser().parse_args(
            ["--data-root", "d", "--config", "c", "--since", "2026-01-01",
             "--chat", "a@c.us", "--chat", "b@g.us"]
        )
        assert ns.chat == ["a@c.us", "b@g.us"]
        assert ns.until is None and ns.yes is False


class TestDateRange:
    def test_inclusive_both_ends(self):
        r = cli._daterange(date(2026, 1, 1), date(2026, 1, 3))
        assert r == [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]

    def test_single_day(self):
        assert cli._daterange(date(2026, 1, 5), date(2026, 1, 5)) == [date(2026, 1, 5)]


class TestPreconditionsFailClosed:
    def _run(self, capsys, *args):
        rc = cli.main(list(args))
        return rc, capsys.readouterr().err

    def test_missing_data_root(self, tmp_path, capsys):
        rc, err = self._run(capsys, "--data-root", str(tmp_path / "nope"),
                            "--config", str(_good_config(tmp_path)), "--since", "2026-01-01")
        assert rc == 1 and "⚠️" in err and "data-root" in err

    def test_data_root_without_sessions(self, tmp_path, capsys):
        dr = tmp_path / "data"
        dr.mkdir()
        rc, err = self._run(capsys, "--data-root", str(dr),
                            "--config", str(_good_config(tmp_path)), "--since", "2026-01-01")
        assert rc == 1 and "sessions/" in err

    def test_missing_config_file(self, tmp_path, capsys):
        rc, err = self._run(capsys, "--data-root", str(_good_data_root(tmp_path)),
                            "--config", str(tmp_path / "no.json"), "--since", "2026-01-01")
        assert rc == 1 and "config" in err

    @pytest.mark.parametrize("drop", ["ai_api_key", "ai_embedding_model", "memory", "ai_model"])
    def test_config_missing_key(self, tmp_path, capsys, drop):
        cfg = json.loads(_good_config(tmp_path).read_text())
        del cfg[drop]
        p = tmp_path / "c.json"
        p.write_text(json.dumps(cfg), encoding="utf-8")
        rc, err = self._run(capsys, "--data-root", str(_good_data_root(tmp_path)),
                            "--config", str(p), "--since", "2026-01-01")
        assert rc == 1 and drop in err

    def test_bad_since_date(self, tmp_path, capsys):
        rc, err = self._run(capsys, "--data-root", str(_good_data_root(tmp_path)),
                            "--config", str(_good_config(tmp_path)), "--since", "not-a-date")
        assert rc == 1 and "since" in err

    def test_since_after_until(self, tmp_path, capsys):
        rc, err = self._run(capsys, "--data-root", str(_good_data_root(tmp_path)),
                            "--config", str(_good_config(tmp_path)),
                            "--since", "2026-01-10", "--until", "2026-01-05")
        assert rc == 1 and "after --until" in err

    def test_until_inside_live_window_is_refused(self, tmp_path, capsys):
        today = date.today()
        rc, err = self._run(capsys, "--data-root", str(_good_data_root(tmp_path)),
                            "--config", str(_good_config(tmp_path)),
                            "--since", (today - timedelta(days=30)).isoformat(),
                            "--until", today.isoformat())
        assert rc == 1 and "live" in err.lower()

    def test_no_chats_is_clean_exit(self, tmp_path, capsys):
        rc = cli.main(["--data-root", str(_good_data_root(tmp_path)),
                       "--config", str(_good_config(tmp_path)),
                       "--since", "2026-01-01", "--until", "2026-01-02", "--yes"])
        assert rc == 0
        assert "No chats" in capsys.readouterr().out
