"""
Approved-write safeguards shared by the legacy AIHandler and the Feature 063 backbone
(Item4, 2026-10-01): recognizing a yes to an approval prompt, and checking what an
approved turn actually executed - the approved write ran more than once (a real
compliance problem: every execution already happened server-side), or never ran at
all (bugfix-028 B4(b): the same document was approved eight times and created never).
Moved out of handlers/ai_handler.py with behavior unchanged - one implementation,
used by both paths.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

# Free-form affirmative replies recognized as approval of a pending write (Feature
# 022) - matched against the trimmed, casefolded message (or its leading token), not
# as a substring-anywhere check, to avoid false positives on unrelated longer sentences.
AFFIRMATIVE_REPLIES = {
    "yes", "yep", "yeah", "sure", "ok", "okay", "go ahead",
    "כן", "אישור", "בסדר", "אוקיי", "אוקי",
    # Feature 046: additional common Hebrew affirmatives - "מאשר"/"מאשרת" ("I
    # confirm", masc./fem.) plus "בטח"/"סבבה", not previously recognized.
    "מאשר", "מאשרת", "בטח", "סבבה",
    # bugfix-028 B1: the prompt itself ended "— לאשר?" while this set had only
    # "אישור", so the prompt invited a word the parser rejected. Live: the user
    # answered "לאשר" twice, got the identical prompt back twice, and gave up.
    # The prompt is now a closed question, but the word it used to invite must
    # still be understood.
    "לאשר",
}


def is_affirmative_reply(text: str) -> bool:
    """Whether `text` reads as a yes to a pending approval - matched as the whole
    trimmed message or its leading token, not a substring-anywhere check, to avoid
    false positives on longer unrelated sentences.

    bugfix-028 B2: the leading token is the first RUN OF WORD CHARACTERS, not the
    first whitespace-split token, because WhatsApp prefixes RTL text with Unicode
    bidi controls (U+200F and friends) that are not whitespace - כן preceded by a
    U+200F mark must still read as yes. Anchoring on the FIRST word still refuses "לא נכון, אל תפיק" - a
    containment test would read that as approval and create a real financial
    document against an explicit refusal."""
    normalized = (text or "").strip().casefold()
    if not normalized:
        return False
    if normalized in AFFIRMATIVE_REPLIES:
        return True
    leading_match = re.search(r"\w+", normalized, flags=re.UNICODE)
    if leading_match is None:
        return False
    return leading_match.group(0) in AFFIRMATIVE_REPLIES


def _field(item: Any, name: str) -> Any:
    """`name` off a raw Responses API item (object) or an already-extracted dict."""
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def mcp_error_text(call: Any) -> str:
    """Human-readable failure text off an `mcp_call` item's `.error` (2026-08-12):
    a failed Morning tool call has `output=None` and an error shaped
    `{"type": "mcp_tool_execution_error", "content": [{"type": "text", "text": ...}]}`.
    A plain-string error is returned as-is."""
    error = _field(call, "error")
    if not error:
        return ""
    if isinstance(error, str):
        return error
    content = error.get("content") if isinstance(error, dict) else getattr(error, "content", None)
    if not content:
        return ""
    for block in content:
        text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
        if text:
            return str(text)
    return ""


@dataclass
class WriteExecutions:
    """What an approved turn executed: how many times each write tool ran, and the
    first failure text any call carried (for telling the user why nothing ran)."""
    counts: Dict[str, int] = field(default_factory=dict)
    failure_detail: str = ""

    @property
    def duplicated(self) -> List[str]:
        """Write tools that ran more than once."""
        return [name for name, count in self.counts.items() if count > 1]

    @property
    def ran_any(self) -> bool:
        return bool(self.counts)


def tally_write_executions(calls: Iterable[Any], write_tool_names: Iterable[str]) -> WriteExecutions:
    """Counts executions of each tool in `write_tool_names` among `calls` (raw
    `mcp_call` items or {name, output, error} dicts). The failure detail is taken
    from the first call of ANY name that carries output or error text, cut to 200
    characters - the same text the legacy zero-execution message has always shown."""
    names = set(write_tool_names)
    result = WriteExecutions()
    for call in calls:
        name = _field(call, "name")
        if name in names:
            result.counts[name] = result.counts.get(name, 0) + 1
        if not result.failure_detail:
            output = _field(call, "output")
            if output:
                result.failure_detail = f" ({str(output)[:200]})"
            else:
                error_text = mcp_error_text(call)
                if error_text:
                    result.failure_detail = f" ({error_text[:200]})"
    return result


def approved_write_not_run_message(failure_detail: str) -> str:
    """The reply when the user approved a write and it never ran (bugfix-028 B4(b))."""
    return (f"אישרת, אבל הפעולה לא בוצעה בפועל{failure_detail}. "
            f"לא נוצר שום מסמך. נסי שוב או ספרי לי איך להמשיך.")
