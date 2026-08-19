"""
Unit tests for AIHandler._build_instructions's today_timestamp parameter
(Feature 043, tasks.md T006a).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md SS VI).

research.md R4 (the "player timestamp audit") found this is the ONE real
correctness bug for replaying historical messages: _build_instructions
injects wall-clock "today", used by the model to resolve relative dates
("היום"/"אתמול") into ledger fields like txn_date. For a replayed historical
message this must reflect the message's own date, not real wall-clock
"today".

Fix: an additive `today_timestamp: Optional[int] = None` parameter
(epoch int, matching AIRequest.timestamp's existing type exactly - no new
field needed there). `None` (the default, omitted by every pre-043 call
site) must preserve current behavior byte-for-byte.

Wording note (2026-08-19, post-merge with feature/054-reminders-functionality-mgmt):
this test file was originally written against a "THE CURRENT DATE IS {date}
(UTC)" wording that predates bugfix-037 (2026-08-10, Israel-local-time
everywhere - see CLAUDE.md) actually being applied to this specific method.
The merge surfaced that gap - _build_instructions now emits Israel-local
date+time ("THE CURRENT DATE AND TIME IS {date} {time} (Asia/Jerusalem,
Israel local time)"), and these assertions are updated to match the
now-compliant wording rather than reverting it.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.utils.time_utils import now_local, local_from_timestamp


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
        before = now_local().strftime("%Y-%m-%d")

        instructions = handler._build_instructions("Be helpful.")

        after = now_local().strftime("%Y-%m-%d")
        assert (f"THE CURRENT DATE AND TIME IS {before} " in instructions
                or f"THE CURRENT DATE AND TIME IS {after} " in instructions)
        assert "(Asia/Jerusalem, Israel local time)" in instructions

    def test_none_today_timestamp_uses_wall_clock_today(self, tmp_path):
        """Explicit None must behave identically to omitting the parameter -
        this is what every pre-043 call site continues to do."""
        handler = _make_handler(tmp_path)
        before = now_local().strftime("%Y-%m-%d")

        instructions = handler._build_instructions("Be helpful.", today_timestamp=None)

        after = now_local().strftime("%Y-%m-%d")
        assert (f"THE CURRENT DATE AND TIME IS {before} " in instructions
                or f"THE CURRENT DATE AND TIME IS {after} " in instructions)
        assert "(Asia/Jerusalem, Israel local time)" in instructions

    def test_supplied_today_timestamp_overrides_wall_clock(self, tmp_path):
        handler = _make_handler(tmp_path)
        # A fixed historical epoch, unambiguous UTC date: 2024-01-30 09:53:54 UTC.
        historical_epoch = int(datetime(2024, 1, 30, 9, 53, 54, tzinfo=timezone.utc).timestamp())
        expected_local = local_from_timestamp(historical_epoch)
        expected_date = expected_local.strftime("%Y-%m-%d")
        expected_time = expected_local.strftime("%H:%M")

        instructions = handler._build_instructions("Be helpful.", today_timestamp=historical_epoch)

        assert f"THE CURRENT DATE AND TIME IS {expected_date} {expected_time} " in instructions
        # Real wall-clock "today" must NOT appear at all - the whole point of
        # the fix is that this doesn't leak through.
        real_today = now_local().strftime("%Y-%m-%d")
        if real_today != expected_date:
            assert f"THE CURRENT DATE AND TIME IS {real_today} " not in instructions

    def test_constitution_text_and_version_still_present_with_override(self, tmp_path):
        """The override must only change the date - everything else about
        the instructions string (constitution content, app version line)
        stays exactly as before."""
        handler = _make_handler(tmp_path)
        historical_epoch = int(datetime(2024, 1, 30, tzinfo=timezone.utc).timestamp())

        instructions = handler._build_instructions("Be helpful.", today_timestamp=historical_epoch)

        assert "Be helpful." in instructions
        assert f"YOUR CURRENT VERSION IS {handler._app_version}" in instructions
