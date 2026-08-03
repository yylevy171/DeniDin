"""
Corrected GreenAPIBot subclass (bugfix-020).

whatsapp_chatbot_python.Bot._delete_notifications_at_startup and Bot.run_forever both assume
Response.data is always a dict once the HTTP status is 200. Green API's own docs state an empty
notification queue can end in a genuinely empty HTTP body (not the JSON literal `null`), and
whatsapp_api_client_python.Response.__init__ turns any JSON-decode failure - including that empty
body - into the fallback STRING "[]" rather than None/[]. A non-empty string is truthy, so neither
library method's `if not response.data` guard fires, and both crash indexing that string with a
dict key ("receiptId"/"body") - a hard crash at startup, and a caught-but-noisy 5s stall on every
empty poll cycle during run_forever().

Re-implements both call sites with an is-it-actually-a-dict check instead, via subclassing
(Template Method) rather than monkey-patching the third-party library (CONSTITUTION XVII).
"""
import logging
import time
from typing import Any, Optional

from whatsapp_chatbot_python import GreenAPIBot, GreenAPIBotError


def _notification_data_or_none(data: Any) -> Optional[dict]:
    """Returns `data` if it is a real notification payload (a dict), else None.

    Treats every other shape Response.data can take - None (documented `null` body), "[]" (the
    library's own JSON-decode-failure fallback for a truly empty body), or any other non-dict -
    as "queue empty, nothing to do here".
    """
    return data if isinstance(data, dict) else None


class DeniDinGreenAPIBot(GreenAPIBot):
    """GreenAPIBot with a startup-notification-drain and polling loop that survive a Green API
    backend serving a genuinely empty HTTP body for "notification queue is empty" (bugfix-020),
    instead of the upstream crash (startup) / swallowed-exception-and-5s-stall (run_forever).
    """

    def __init__(self, *args: Any, delete_notifications_at_startup: bool = True, **kwargs: Any):
        # Always disable the library's own (buggy) startup drain; run our corrected one after,
        # once self.api/self.logger exist.
        super().__init__(*args, delete_notifications_at_startup=False, **kwargs)
        if delete_notifications_at_startup:
            self._drain_startup_notifications()

    def _drain_startup_notifications(self) -> None:
        self.api.session.headers["Connection"] = "keep-alive"
        self.logger.log(logging.DEBUG, "Started deleting old incoming notifications.")

        while True:
            response = self.api.receiving.receiveNotification()
            data = _notification_data_or_none(response.data)
            if data is None:
                break
            self.api.receiving.deleteNotification(data["receiptId"])

        self.api.session.headers["Connection"] = "close"
        self.logger.log(logging.DEBUG, "Stopped deleting old incoming notifications.")
        self.logger.log(logging.INFO, "Deleted old incoming notifications.")

    def run_forever(self) -> None:
        self.api.session.headers["Connection"] = "keep-alive"
        self.logger.log(logging.INFO, "Started receiving incoming notifications.")

        while True:
            try:
                response = self.api.receiving.receiveNotification()
                data = _notification_data_or_none(response.data)
                if data is None:
                    continue

                self.router.route_event(data["body"])
                self.api.receiving.deleteNotification(data["receiptId"])
            except KeyboardInterrupt:
                break
            except Exception as error:  # pylint: disable=broad-except
                if self.raise_errors:
                    raise GreenAPIBotError(error) from error
                self.logger.log(logging.ERROR, error)
                time.sleep(5.0)
                continue

        self.api.session.headers["Connection"] = "close"
        self.logger.log(logging.INFO, "Stopped receiving incoming notifications.")
