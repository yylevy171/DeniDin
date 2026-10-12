"""Feature 067 (REQ-RMH-007/008/019): how waiting user messages are shown to the model."""
from datetime import timedelta
from types import SimpleNamespace

from src.backbone.pending_messages import (
    AFTER_LAST_OUTPUT, BEFORE_LAST_OUTPUT, MEDIA_HANDLED_SEPARATELY, MEDIA_SENT_AFTER, format_pending_items,
)
from src.intake.intake_coordinator import Drained, PendingItem
from src.utils.time_utils import local_from_timestamp, now_local


def _item(type_message, epoch, text="", is_group=False, sender="Dana", file_data=None):
    event = {"messageData": {"typeMessage": type_message, **({"fileMessageData": file_data} if file_data else {})}}
    message = SimpleNamespace(timestamp=epoch, text_content=text, is_group=is_group, sender_display_name=sender,
                              received_timestamp=None)
    return PendingItem(notification=SimpleNamespace(event=event), type_message=type_message, chat_id="c",
                       id_message="i", message=message)


def _drained(*items):
    return Drained(attachable=[], media=[], ordered=list(items))


def test_no_messages_no_items():
    assert format_pending_items(_drained(), now_local()) == []


def test_text_item_carries_clock_and_after_marker():
    last = now_local()
    sent = last + timedelta(seconds=30)
    items = format_pending_items(_drained(_item("textMessage", int(sent.timestamp()), "על 500 שקל")), last)
    assert len(items) == 1 and items[0]["role"] == "user"
    stamp = local_from_timestamp(int(sent.timestamp())).strftime("%H:%M:%S %d/%m")
    assert items[0]["content"] == f"[הודעה מהמשתמש · {stamp} · {AFTER_LAST_OUTPUT}]\nעל 500 שקל"


def test_message_sent_before_the_last_output_is_marked_before():
    last = now_local()
    sent = last - timedelta(seconds=30)
    content = format_pending_items(_drained(_item("textMessage", int(sent.timestamp()), "x")), last)[0]["content"]
    assert BEFORE_LAST_OUTPUT in content and AFTER_LAST_OUTPUT not in content


def test_arrival_order_is_kept():
    last = now_local()
    base = int(last.timestamp()) + 5
    contents = [i["content"] for i in format_pending_items(
        _drained(*[_item("textMessage", base + n, f"m{n}") for n in range(3)]), last)]
    assert [c.splitlines()[1] for c in contents] == ["m0", "m1", "m2"]


def test_group_message_keeps_the_sender_prefix():
    last = now_local()
    content = format_pending_items(
        _drained(_item("textMessage", int(last.timestamp()) + 1, "היי", is_group=True, sender="Yossi")), last)[0]["content"]
    assert content.endswith("[Yossi] היי")


def test_media_is_only_mentioned_and_handled_separately():
    last = now_local()
    media = _item("imageMessage", int(last.timestamp()) + 1,
                  file_data={"fileName": "slip.jpg", "caption": "העברה"})
    content = format_pending_items(_drained(media), last)[0]["content"]
    assert content.startswith("[קובץ התקבל · ") and MEDIA_SENT_AFTER in content and "slip.jpg" in content
    assert "העברה" in content and content.endswith(MEDIA_HANDLED_SEPARATELY)


def test_missing_timestamp_falls_back_to_received_time():
    last = now_local()
    item = _item("textMessage", None, "x")
    item.message.received_timestamp = last + timedelta(seconds=5)
    assert AFTER_LAST_OUTPUT in format_pending_items(_drained(item), last)[0]["content"]
