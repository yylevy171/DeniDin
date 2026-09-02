"""
WhatsApp export parser (Feature 043, tasks.md T009).

Parses a WhatsApp chat-export zip (one chat-history .txt file + media files)
into an ordered sequence of ParsedMessage objects - the player's own input
format, independent of Green API's notification shape (notification_synth.py
is the boundary that converts ParsedMessage -> a Green-API-shaped
Notification, per contracts/message-source.md).

Format confirmed against a real sample export this session (research.md R1):

    M/D/YY, H:MM - SenderName: message text
    (continuation lines, no timestamp prefix, until the next
     "M/D/YY, H:MM - Name:" line)
    M/D/YY, H:MM - SenderName: FILENAME.jpg (file attached)

No explicit timezone is present in a WhatsApp export - timestamps are the
exporting device's local wall-clock time. Per research.md R1, this is
treated as Asia/Jerusalem local time and converted to UTC, matching
LedgerEventManager's own ISRAEL_TZ convention.

System-message filtering is defensive/best-effort (research.md's T002
addendum: the one real sample this session inspected happened to contain
none, which is NOT sufficient proof the real full export never will) -
harmless to filter a template that never appears, harmful to crash or
mis-parse on one that does.
"""
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

# Same convention as LedgerEventManager.ISRAEL_TZ (src/managers/ledger_event_manager.py) -
# a WhatsApp export's timestamps are the exporting device's local wall-clock time, with
# no explicit timezone marker, confirmed against a real sample (research.md R1).
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

# The player's own floor - ledger events are never played earlier than this,
# regardless of what start date a caller requests (spec.md's Scope).
EARLIEST_ALLOWED_DATE = date(2025, 9, 1)

# "M/D/YY, H:MM - " prefix shared by every export line that starts something
# new (a real message OR a system notice - WhatsApp system lines have this
# same date prefix but NO "Name:" colon structure, e.g. "8/15/25, 14:02 -
# Messages and calls are end-to-end encrypted..."). Checked FIRST, before
# attempting the stricter sender:text split below - otherwise a system
# notice with no colon at all would fall through as a "continuation line"
# and get silently glued onto whatever real message preceded it, corrupting
# that message's text (a real bug this two-stage check avoids).
_DATE_PREFIX_RE = re.compile(
    r'^(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{2}), '
    r'(?P<hour>\d{1,2}):(?P<minute>\d{2}) - (?P<rest>.*)$'
)

# "Name: text" - splits a date-prefixed line's `rest` into sender/text, once
# it's already been confirmed NOT to be a system notice.
_SENDER_TEXT_RE = re.compile(r'^(?P<sender>[^:]+): (?P<text>.*)$')

# "FILENAME (file attached)" - the message's own first line, when it's an
# attachment. Any further lines are treated as a caption (research.md's T002
# addendum: not observed in the one real sample checked, handled defensively
# regardless).
_ATTACHMENT_RE = re.compile(r'^(?P<filename>.+) \(file attached\)$')

# Invisible bidi control characters WhatsApp exports commonly include (e.g.
# U+200F RLM prefixing a Hebrew message body) - stripped from parsed text,
# never treated as meaningful content. Deliberately NOT stripping emoji -
# real sender display names legitimately include them (research.md R1).
# Written as explicit \uXXXX escapes, never literal characters, so the
# source file itself never embeds real bidi control codepoints (avoids
# tooling flagging this file for exactly the class of issue it's guarding
# against - CVE-2021-42574-style "Trojan Source" obfuscation).
_BIDI_CONTROL_RE = re.compile('[\u200e\u200f\u202a-\u202e\u2066-\u2069]')

# Best-effort, extendable list of known WhatsApp system-message templates to
# filter out entirely (never treated as a real message) - see this module's
# docstring for why this can't be verified exhaustively yet.
_SYSTEM_MESSAGE_MARKERS = (
    "Messages and calls are end-to-end encrypted",
    "\u200eMessages and calls are end-to-end encrypted",  # LRM-prefixed variant
)


@dataclass
class ParsedMessage:
    """One parsed WhatsApp export message - the player's own input shape,
    independent of Green API's notification format."""
    timestamp: datetime          # tz-aware UTC (converted from Asia/Jerusalem)
    sender_display_name: str     # emoji preserved, bidi control chars stripped
    text: str                    # message body (or attachment caption, if any)
    attachments: List[Path] = field(default_factory=list)  # [] for plain text
    raw_line_no: int = 0          # source line, for error messages/audit trail


def _strip_bidi_controls(text: str) -> str:
    return _BIDI_CONTROL_RE.sub('', text)


def _is_system_message(rest: str) -> bool:
    """Checked against a date-prefixed line's raw `rest` text (before any
    sender:text splitting) - a system notice has no "Name:" colon structure
    at all, so it must be recognized here, not after attempting that split."""
    return any(marker in rest for marker in _SYSTEM_MESSAGE_MARKERS)


def _resolve_attachment_path(filename: str, media_dir: Path) -> Path:
    """Resolves an attachment filename against the extracted media
    directory - exact match first, case-insensitive fallback (WhatsApp
    exports occasionally normalize case on extraction). Returns the
    filename's Path even if genuinely not found (media_dir / filename) -
    callers (notification_synth.py's media server) fail loud on a missing
    file rather than this function silently guessing or raising."""
    exact = media_dir / filename
    if exact.exists():
        return exact
    if media_dir.exists():
        for candidate in media_dir.iterdir():
            if candidate.name.lower() == filename.lower():
                return candidate
    return exact


def _find_chat_text_file(extract_dir: Path) -> Path:
    txt_files = sorted(extract_dir.glob("*.txt"))
    if len(txt_files) == 0:
        raise ValueError(f"No .txt chat-history file found in export at {extract_dir}")
    if len(txt_files) > 1:
        raise ValueError(
            f"Expected exactly one .txt chat-history file in export, found "
            f"{len(txt_files)}: {[f.name for f in txt_files]}"
        )
    return txt_files[0]


def parse_export(zip_path: Path, extract_dir: Path) -> List[ParsedMessage]:
    """
    Extracts `zip_path` into `extract_dir` and parses its chat-history .txt
    file into an ordered list of ParsedMessage (chronological, matching the
    export's own line order - never re-sorted here, see filter_date_range's
    caller for the defensive re-sort before replay).

    Raises ValueError if the zip doesn't contain exactly one .txt file.
    """
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)

    chat_file = _find_chat_text_file(extract_dir)
    lines = chat_file.read_text(encoding="utf-8").splitlines()

    messages: List[ParsedMessage] = []
    current: Optional[dict] = None

    for line_no, raw_line in enumerate(lines, start=1):
        prefix_match = _DATE_PREFIX_RE.match(raw_line)
        if prefix_match is None:
            # No date prefix at all - a genuine continuation line of `current`.
            if current is not None:
                current['text_lines'].append(_strip_bidi_controls(raw_line))
            # A continuation line before any message-start line (shouldn't
            # happen in a real export) is silently dropped - there is no
            # message to attach it to.
            continue

        rest = prefix_match['rest']
        if _is_system_message(rest):
            # A system notice (no "Name:" colon structure at all) - never
            # attached to `current` as a continuation, and starts nothing
            # new. Finalize whatever was in progress and move on.
            if current is not None:
                messages.append(_finalize(current, extract_dir))
                current = None
            continue

        sender_match = _SENDER_TEXT_RE.match(rest)
        if sender_match is None:
            # Date-prefixed but no colon-separated sender, and not a known
            # system template - an unrecognized line shape. Treat the same
            # as a system notice (never guess a sender) rather than crash.
            if current is not None:
                messages.append(_finalize(current, extract_dir))
                current = None
            continue

        if current is not None:
            messages.append(_finalize(current, extract_dir))
        month, day, year = int(prefix_match['month']), int(prefix_match['day']), int(prefix_match['year'])
        hour, minute = int(prefix_match['hour']), int(prefix_match['minute'])
        local_dt = datetime(2000 + year, month, day, hour, minute, tzinfo=ISRAEL_TZ)
        current = {
            'timestamp': local_dt.astimezone(timezone.utc),
            'sender': _strip_bidi_controls(sender_match['sender']).strip(),
            'text_lines': [_strip_bidi_controls(sender_match['text'])],
            'raw_line_no': line_no,
        }

    if current is not None:
        messages.append(_finalize(current, extract_dir))

    return messages


def _finalize(current: dict, extract_dir: Path) -> ParsedMessage:
    full_text = "\n".join(current['text_lines'])
    sender = current['sender']

    first_line = current['text_lines'][0]
    attachment_match = _ATTACHMENT_RE.match(first_line)
    if attachment_match:
        attachment_path = _resolve_attachment_path(attachment_match['filename'], extract_dir)
        caption = "\n".join(current['text_lines'][1:])
        return ParsedMessage(
            timestamp=current['timestamp'], sender_display_name=sender,
            text=caption, attachments=[attachment_path], raw_line_no=current['raw_line_no'],
        )

    return ParsedMessage(
        timestamp=current['timestamp'], sender_display_name=sender,
        text=full_text, attachments=[], raw_line_no=current['raw_line_no'],
    )


def filter_date_range(
    messages: List[ParsedMessage],
    start: Optional[date],
    end: Optional[date],
    today: Optional[date] = None,
) -> List[ParsedMessage]:
    """
    Filters (and chronologically re-sorts, defensively - never assumes the
    export was already in order) to messages within `[start, end]`, clamped
    server-side: `start` is never earlier than EARLIEST_ALLOWED_DATE,
    `end` is never later than `today` - regardless of what's requested,
    per spec.md's Scope ("start >= 2025-09-01, end <= today").

    `start`/`end` default to the full allowed range when None.
    `today` defaults to the real current UTC date when None - a caller
    can inject a fixed date for deterministic testing.
    """
    resolved_today = today if today is not None else datetime.now(timezone.utc).date()
    resolved_start = max(start or EARLIEST_ALLOWED_DATE, EARLIEST_ALLOWED_DATE)
    resolved_end = min(end or resolved_today, resolved_today)

    in_range = [
        m for m in messages
        if resolved_start <= m.timestamp.date() <= resolved_end
    ]
    return sorted(in_range, key=lambda m: m.timestamp)


def filter_from_line(
    messages: List[ParsedMessage],
    start_at_line: Optional[int],
) -> List[ParsedMessage]:
    """
    Filters to messages with `raw_line_no >= start_at_line` - a precise,
    exact-message resume point for a replay interrupted mid-run (a real
    OpenAI outage/credit exhaustion, a killed process, etc.), independent of
    `filter_date_range`'s day-granularity `--start`/`--end` clamp: a day can
    hold well over a hundred messages, so restarting from the start of that
    same day would re-dispatch everything already processed earlier that day
    (real duplicate ledger events - `LedgerEventManager` allocates a fresh
    seq digit per capture, it does not overwrite/dedupe), while skipping to
    the next day would silently drop the unfinished remainder of the
    interrupted day.

    Callers apply this AFTER `filter_date_range` (see run_player.py's
    `run_replay`) - it does not itself re-sort or date-clamp.

    `raw_line_no` is the export's own source line number (see
    `ParsedMessage.raw_line_no` / a completed run's own `sound_off` output,
    e.g. `[174/569] line=2535 ...` - the exact same number a human reads off
    a prior run's log/summary to pick this up).

    `start_at_line=None` returns `messages` unchanged (no filtering).
    """
    if start_at_line is None:
        return messages
    return [m for m in messages if m.raw_line_no >= start_at_line]
