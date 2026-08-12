"""bugfix-028 B1/B2 — unit tests for the approval-reply matcher.

B2: WhatsApp inserts Unicode bidi control characters ahead of Hebrew text on
RTL keyboards, unpredictably. U+200F RIGHT-TO-LEFT MARK is NOT whitespace
(`'‏'.isspace()` is False), so `.strip()` leaves it attached and
`.split()[0]` yields `'‏כן'`, which is not in the whitelist. Verified in
production: on 2026-08-09 04:00:45 UTC the user sent `‏כן` and the log
records `approve=False`. Eight user messages in that window carried bidi
controls.

B1: the prompt ends `— לאשר?` while the whitelist contains `אישור` and not
`לאשר`, so the prompt teaches a word the parser rejects. The user's fix is a
closed question (`אישור — כן/לא?`), but `לאשר` must still be understood - a
user who answers the old prompt's own word is not refusing.

Written as new test functions rather than extending
test_ai_handler_approval_gate.py's existing parametrize lists, per
METHODOLOGY.md's test-immutability rule.

RED ON CURRENT CODE: every case below returns False today.

Fix-approach note (user, 2026-08-09): stripping an enumerated list of bidi
characters was rejected in favour of substring/containment matching. The
negative cases here are the guard on that - a containment fix must not start
reading refusals as approvals.
"""
import pytest

from src.handlers.ai_handler import _is_affirmative_reply

RLM = "‏"   # RIGHT-TO-LEFT MARK - what WhatsApp actually sent
LRM = "‎"   # LEFT-TO-RIGHT MARK
RLE = "‫"   # RIGHT-TO-LEFT EMBEDDING
PDF = "‬"   # POP DIRECTIONAL FORMATTING


@pytest.mark.parametrize("text", [
    f"{RLM}כן",                      # the exact production string (Aug 9 04:00:45 UTC)
    f"{RLM}כן\nלהפיק את המסמך",       # ...as actually sent, with its trailing line
    f"{RLM}אישור",
    f"{RLM}מאשרת",
    f"{LRM}כן",
    f"{RLE}כן{PDF}",
    f"  {RLM}כן  ",
    f"{RLM}כן.",
])
def test_bidi_prefixed_affirmatives_are_recognized(text):
    """B2: a bidi control character must not turn an approval into a refusal."""
    assert _is_affirmative_reply(text) is True, (
        f"{text!r} is an approval; bidi control characters are invisible "
        f"formatting, not content"
    )


@pytest.mark.parametrize("text", [
    "לאשר",
    "לאשר.",
    f"{RLM}לאשר",
    "לאשר בבקשה",
])
def test_the_word_the_prompt_itself_invites_is_recognized(text):
    """B1: the prompt asked `— לאשר?`; answering it with `לאשר` is an approval.

    Live consequence of it not being one (session 12e158e2, turns 18-26): the
    user answered `לאשר` twice, got the identical prompt back twice, and gave
    up with `לא`. The phone update never happened.
    """
    assert _is_affirmative_reply(text) is True


@pytest.mark.parametrize("text", [
    f"{RLM}לא",
    f"{RLM}לא נכון, אל תפיק",
    f"{RLM}לא, אני לא בטוחה שזה נכון",
    f"{RLM}עדיין לא - תן לי לבדוק",
    "אל תאשר את זה",
    f"{RLM}למה אתה מבקש אישור שוב?",
])
def test_bidi_prefixed_refusals_are_still_refusals(text):
    """Guard on the containment-based fix direction: a message that merely
    CONTAINS an affirmative word is not an approval. `לא נכון` contains `כן`
    as a substring; approving on that would be far worse than the bug being
    fixed - it would create real financial documents against a refusal.

    This one passes on current code by design; its job is to fail if the fix
    over-broadens.
    """
    assert _is_affirmative_reply(text) is False
