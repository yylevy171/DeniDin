# Contract: `MessageSource`

## Interface

```python
class MessageSource(ABC):
    @abstractmethod
    def start(self, dispatch: Callable[[str, Notification], None]) -> None:
        ...
```

- `dispatch(type_message: str, notification: Notification)` is called
  exactly once per message the source produces, synchronously, in the
  source's natural order.
- `notification` MUST be an object with a `.event` dict whose shape
  `WhatsAppMessage.from_notification` (`src/models/message.py:47-107`)
  already parses today — same keys, same nesting, real or synthesized.
  This contract is what makes downstream processing identical regardless
  of source.
- `notification.event['timestamp']` MUST always be populated with a real
  Unix epoch int reflecting the message's actual historical/live moment —
  never omitted (see research.md R4: `models/message.py:88` silently
  substitutes wall-clock time if this key is missing, which would corrupt
  every downstream date-derived field for a replayed message).
- `notification` MUST support `.answer(text: str)` being called on it
  (live: sends a real WhatsApp reply; player: no-op or captured for the
  run summary — implementation's choice, but must not raise).

## `GreenAPIMessageSource`

- Constructed only from `denidin.py`'s live entry point, never at module
  import time and never by tests or the player.
- `start()` constructs `DeniDinGreenAPIBot(config.green_api_instance_id,
  config.green_api_token)` (today's existing side effects, unchanged),
  registers the handler dispatch table against `bot.router`, and blocks
  running the bot's listen loop. Returns only on shutdown.
- Behavior when actually run (container / `run_denidin.sh`) must be
  byte-for-byte identical to pre-refactor `denidin.py` — this needs
  explicit verification in `/tasks`, not assumed from the design alone.

## Player source (`PlayerExportSource`, `scripts/player/export_source.py`)

- Constructed from a `List[ParsedMessage]` already filtered to `[start,
  end]` and sorted chronologically.
- `start()` iterates the list once, in order; for each `ParsedMessage`,
  synthesizes a `Notification` (via `notification_synth.py`) and calls
  `dispatch(type_message, notification)` directly — no live bot, no
  Green API credentials touched at any point.
- Returns once the list is exhausted (never blocks).
- Unsupported attachment types (voice notes, video, vcf) are **not**
  synthesized into `imageMessage`/`documentMessage` notifications — routed
  instead to a `not-qualifying: unsupported-type` run-summary outcome
  without calling `dispatch` at all, matching the fact that Feature 043's
  scope is ledger-event capture, not full conversational replay.
