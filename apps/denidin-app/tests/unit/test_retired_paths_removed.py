"""Feature 070 — retired paths are DELETED, not dormant (T013a), SC-011.

Static source scan: the 24h-expiry / hourly-cleanup / write-time-prune / session
-transfer machinery leaves zero references in src/. Also negative constraints:
the feature's changed modules add no CURRENT_SCHEMA_VERSION / ledger_event_manager
coupling (REQ-MEM-043) and introduce no feature_flags key for Feature 070
(REQ-MEM-060).
"""
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
APP = Path(__file__).resolve().parents[2]

RETIRED_SYMBOLS = [
    "SessionCleanupThread",
    "run_startup_cleanup",
    "cleanup_service",
    "_prune_until_under_limit",
    "prune_to_limit",
    "add_message_with_token_limit",
    "clear_session",
    "remove_from_index",
    "is_session_expired",
    "find_expired_active_sessions",
    "find_untransferred_archived_sessions",
    "get_sessions_needing_cleanup",
    "get_expired_sessions",
    "find_orphaned_sessions",
    "recover_orphaned_sessions",
    "transfer_session_to_long_term_memory",
    "session_timeout_hours",
    "cleanup_interval_seconds",
]


def _py_files(root):
    return [p for p in root.rglob("*.py")]


def _code_only(text: str) -> str:
    """Strip full-line and inline ``#`` comments and triple-quoted string
    bodies, leaving only executable code — a historical mention in a comment or
    docstring is not a live reference."""
    import re

    text = re.sub(r'"""[\s\S]*?"""', "", text)
    text = re.sub(r"'''[\s\S]*?'''", "", text)
    out = []
    for line in text.splitlines():
        hash_idx = line.find("#")
        if hash_idx != -1 and '"' not in line[:hash_idx] and "'" not in line[:hash_idx]:
            line = line[:hash_idx]
        out.append(line)
    return "\n".join(out)


@pytest.mark.parametrize("symbol", RETIRED_SYMBOLS)
def test_no_source_reference_to_retired_symbol(symbol):
    hits = []
    for p in _py_files(SRC) + [APP / "denidin.py"]:
        if _code_only(p.read_text(encoding="utf-8")).find(symbol) != -1:
            hits.append(str(p.relative_to(APP)))
    assert not hits, f"retired symbol {symbol!r} still referenced in code in: {hits}"


def test_no_message_or_session_deletion_in_feature_modules():
    feature_modules = [
        SRC / "managers" / "session_manager.py",
        SRC / "services" / "daily_summary_roll_service.py",
        SRC / "managers" / "memory_collections.py",
        SRC / "managers" / "roll_marker_store.py",
        SRC / "handlers" / "summarizer.py",
    ]
    banned = [".unlink(", "os.remove(", "shutil.rmtree("]
    for m in feature_modules:
        text = m.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{token} found in {m.name} - archiving must never delete"


def test_feature_modules_do_not_couple_to_ledger_schema_version():
    for name in ["session_manager.py", "roll_marker_store.py"]:
        text = (SRC / "managers" / name).read_text(encoding="utf-8")
        assert "CURRENT_SCHEMA_VERSION" not in text
        assert "ledger_event_manager" not in text
    roll = (SRC / "services" / "daily_summary_roll_service.py").read_text(encoding="utf-8")
    assert "CURRENT_SCHEMA_VERSION" not in roll


def test_no_feature_070_feature_flag_in_any_config():
    cfg_dir = APP / "config"
    for cfg in cfg_dir.glob("config*.json"):
        text = cfg.read_text(encoding="utf-8")
        # the memory-model cutover is deliberately flag-free (spec Clarifications)
        for flag_name in ["rolling_memory", "daily_roll", "window_days_flag", "enable_rolling_window"]:
            assert flag_name not in text, f"unexpected Feature 070 flag {flag_name!r} in {cfg.name}"
