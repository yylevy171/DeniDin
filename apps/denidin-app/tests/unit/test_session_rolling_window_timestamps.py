"""Feature 067 (REQ-RMH-007): opt-in send-time prefix on user items of the rolling window; default unchanged."""
import re

from tests.denidin_test_support import make_session_manager
from tests.helpers.seed import seed_message

CHAT = "972522968679@c.us"


def test_default_window_is_unchanged_and_opt_in_prefixes_user_items_only(tmp_path):
    sm = make_session_manager(storage_dir=str(tmp_path / "sessions"))
    try:
        seed_message(sm, CHAT, "user", "שלום", 1)
        seed_message(sm, CHAT, "assistant", "היי", 0)
        plain = sm.get_rolling_window(CHAT)
        stamped = sm.get_rolling_window(CHAT, with_timestamps=True)
        assert [i["content"] for i in plain] == ["שלום", "היי"]
        assert re.fullmatch(r"\[\d\d:\d\d:\d\d \d\d/\d\d\] שלום", stamped[0]["content"])
        assert stamped[1]["content"] == "היי"
        assert [i["role"] for i in stamped] == [i["role"] for i in plain]
    finally:
        sm.close()
