"""User messages that arrived while the model was working, as model input (Feature 067).

At every hand-back the backbone merges (A) the model's own output (its tool results) and (B)
the user messages read since into the model's next input (REQ-RMH-001). Each pending
message becomes one user input item that carries its send time and whether it was sent
before or after the model's last output (REQ-RMH-007/008), so the model can read the
timeline itself. A media message is only *mentioned*: it is analyzed on its own after the
current work (REQ-RMH-019).
"""
from datetime import datetime
from typing import Any, Dict, List

from src.intake.intake_coordinator import MEDIA_TYPES, Drained, PendingItem
from src.utils.time_utils import local_from_timestamp, now_local, sane_source_epoch

BEFORE_LAST_OUTPUT = "נשלחה לפני הפלט האחרון שלך"
AFTER_LAST_OUTPUT = "נשלחה אחרי הפלט האחרון שלך"
MEDIA_SENT_BEFORE = "נשלח לפני הפלט האחרון שלך"
MEDIA_SENT_AFTER = "נשלח אחרי הפלט האחרון שלך"
MEDIA_HANDLED_SEPARATELY = "(הקובץ ינותח בנפרד אחרי שתסיים עם הבקשה הנוכחית)"


def message_sent_at(message: Any) -> datetime:
    """When the user sent the message (Israel local): the WhatsApp timestamp, else the
    time the app received it."""
    epoch = sane_source_epoch(getattr(message, "timestamp", None))
    if epoch is not None:
        return local_from_timestamp(epoch)
    return getattr(message, "received_timestamp", None) or now_local()


def _clock_label(moment: datetime) -> str:
    return moment.strftime("%H:%M:%S %d/%m")


def _format_item(item: PendingItem, last_output_at: datetime) -> Dict[str, str]:
    message = item.message
    sent_at = message_sent_at(message)
    before = sent_at < last_output_at
    stamp = _clock_label(sent_at)
    if item.type_message in MEDIA_TYPES:
        file_data = item.notification.event.get("messageData", {}).get("fileMessageData", {})
        header = (f"[קובץ התקבל · {stamp} · {MEDIA_SENT_BEFORE if before else MEDIA_SENT_AFTER}"
                  f" · {file_data.get('fileName', '')}]")
        caption = file_data.get("caption", "")
        body = f"{header} {caption}".rstrip() + f"\n{MEDIA_HANDLED_SEPARATELY}"
        return {"role": "user", "content": body}
    assert message is not None  # text/contact items are always stored on receipt
    text = message.text_content
    if getattr(message, "is_group", False) and getattr(message, "sender_display_name", ""):
        text = f"[{message.sender_display_name}] {text}"
    header = f"[הודעה מהמשתמש · {stamp} · {BEFORE_LAST_OUTPUT if before else AFTER_LAST_OUTPUT}]"
    return {"role": "user", "content": f"{header}\n{text}"}


def format_pending_items(drained: Drained, last_output_at: datetime) -> List[Dict[str, str]]:
    """One user input item per drained message (arrival order), to follow the model's tool
    results in its next input."""
    return [_format_item(item, last_output_at) for item in drained.ordered]
