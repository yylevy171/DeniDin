"""
Unit tests for AIHandler._build_instructions's today_timestamp parameter
(Feature 043, tasks.md T006a).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md SS VI).

research.md R4 (the "player timestamp audit") found this is the ONE real
correctness bug for replaying historical messages: _build_instructions
injects wall-clock datetime.now(timezone.utc) as "THE CURRENT DATE IS
{today}", used by the model to resolve relative dates ("היום"/"אתמול") into
ledger fields like txn_date. For a replayed historical message this must
reflect the message's own date, not real wall-clock "today".

Fix: an additive `today_timestamp: Optional[int] = None` parameter
(epoch int, matching AIRequest.timestamp's existing type exactly - no new
field needed there). `None` (the default, omitted by every pre-043 call
site) must preserve current behavior byte-for-byte.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration


def _make_handler(tmp_path):
    config = AppConfiguration(
        green_api_instance_id="test",
        green_api_token="test",
        ai_api_key="test-key",
        ai_model="gpt-4o-mini",
        ai_reply_max_tokens=1000,
        log_level="INFO",
        data_root=str(tmp_path),
        constitution_config={"file": "runtime_constitution.md", "base_dir": str(tmp_path)},
    )
    (tmp_path / "runtime_constitution.md").write_text("# Constitution\nBe helpful.", encoding="utf-8")
    return AIHandler(MagicMock(), config)


class TestBuildInstructionsReferenceTimestamp:
    def test_omitted_today_timestamp_uses_wall_clock_today(self, tmp_path):
        handler = _make_handler(tmp_path)
        before = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        instructions = handler._build_instructions("Be helpful.")

        after = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert (f"THE CURRENT DATE IS {before} (UTC)" in instructions
                or f"THE CURRENT DATE IS {after} (UTC)" in instructions)

    def test_none_today_timestamp_uses_wall_clock_today(self, tmp_path):
        """Explicit None must behave identically to omitting the parameter -
        this is what every pre-043 call site continues to do."""
        handler = _make_handler(tmp_path)
        before = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        instructions = handler._build_instructions("Be helpful.", today_timestamp=None)

        after = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert (f"THE CURRENT DATE IS {before} (UTC)" in instructions
                or f"THE CURRENT DATE IS {after} (UTC)" in instructions)

    def test_supplied_today_timestamp_overrides_wall_clock(self, tmp_path):
        handler = _make_handler(tmp_path)
        # A fixed historical epoch, unambiguous UTC date: 2024-01-30 09:53:54 UTC.
        historical_epoch = int(datetime(2024, 1, 30, 9, 53, 54, tzinfo=timezone.utc).timestamp())

        instructions = handler._build_instructions("Be helpful.", today_timestamp=historical_epoch)

        assert "THE CURRENT DATE IS 2024-01-30 (UTC)" in instructions
        # Real wall-clock "today" must NOT appear at all - the whole point of
        # the fix is that this doesn't leak through.
        real_today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if real_today != "2024-01-30":
            assert f"THE CURRENT DATE IS {real_today} (UTC)" not in instructions

    def test_constitution_text_and_version_still_present_with_override(self, tmp_path):
        """The override must only change the date - everything else about
        the instructions string (constitution content, app version line)
        stays exactly as before."""
        handler = _make_handler(tmp_path)
        historical_epoch = int(datetime(2024, 1, 30, tzinfo=timezone.utc).timestamp())

        instructions = handler._build_instructions("Be helpful.", today_timestamp=historical_epoch)

        assert "Be helpful." in instructions
        assert f"YOUR CURRENT VERSION IS {handler._app_version}" in instructions
