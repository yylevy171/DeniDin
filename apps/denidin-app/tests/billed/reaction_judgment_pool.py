"""
Feature 084 (WhatsApp reactions) - the billed reaction-judgment scenario pool.

Plain data, NOT test functions (contracts/reaction-judgment-tuning.md) - a list of
representative conversational scenarios, each with enough context to run through the
real AIHandler pipeline. Not exhaustive - designed for variety across user stories and
edge cases, expanded over time as new misses are found during tuning.

Each scenario:
    name: unique identifier (used by the rotation state file)
    description: what this scenario is checking for
    role: "client" | "godfather" | "admin" - governs which tools get attached
    chat_id: a stable per-scenario chat id
    is_group: whether this simulates a group chat
    prior_turns: [(role, content)] - conversation history seeded before the real turn,
        oldest first. Empty for a fresh conversation.
    message: the triggering message's text content for this turn
    hard_assertions: which of this scenario's outcomes are deterministic plumbing,
        not judgment - "zero_calls" (no send_reaction call at all should occur) or
        "is_flip_scenario" (paired with a `flip_from` scenario name; only meaningful
        when both scenarios in a pair are run in the same rotation round).
"""
from typing import Any, Dict, List

BILLED_REACTION_SCENARIOS: List[Dict[str, Any]] = [
    {
        "name": "action_command_clean_success",
        "description": "Action command -> clean success (invoice creation)",
        "role": "godfather",
        "chat_id": "972500000101@c.us",
        "is_group": False,
        "prior_turns": [],
        "message": "צור חשבונית ל-2,000 ש\"ח למשה כהן על שירותי ייעוץ",
        "hard_assertions": {},
    },
    {
        "name": "action_command_blocked_ambiguous_client",
        "description": "Action command -> blocked/ambiguous client",
        "role": "godfather",
        "chat_id": "972500000102@c.us",
        "is_group": False,
        "prior_turns": [],
        "message": "צור חשבונית ל-500 ש\"ח לדוד",
        "hard_assertions": {},
    },
    {
        "name": "action_command_clarification_needed",
        "description": "Action command -> clarification needed mid-flow",
        "role": "godfather",
        "chat_id": "972500000103@c.us",
        "is_group": False,
        "prior_turns": [],
        "message": "תוציא חשבונית",
        "hard_assertions": {},
    },
    {
        "name": "react_no_explicit_target",
        "description": "react_to_message with no explicit target (reacts to current turn)",
        "role": "client",
        "chat_id": "972500000104@c.us",
        "is_group": False,
        "prior_turns": [],
        "message": "יאללה, תודה על העזרה!",
        "hard_assertions": {},
    },
    {
        "name": "react_flip_earlier_message",
        "description": "react_to_message flipping an earlier message's reaction (multi-turn)",
        "role": "godfather",
        "chat_id": "972500000105@c.us",
        "is_group": False,
        "prior_turns": [
            ("user", "מצרף חוזה שכר טרחה לחתימה"),
            ("assistant", "קיבלתי, בודק את המסמך."),
        ],
        "message": "אישרתי את התנאים, אפשר לתעד את ההסכם",
        "hard_assertions": {"is_flip_scenario": True},
    },
    {
        "name": "ambient_group_chatter_lunch",
        "description": "Ambient group chatter, variant A (two people planning lunch)",
        "role": "client",
        "chat_id": "120363000000000001@g.us",
        "is_group": True,
        "prior_turns": [
            ("user", "יוצאים לאכול ב-12?"),
        ],
        "message": "כן בטח, איפה נפגש?",
        "hard_assertions": {"zero_calls": True},
    },
    {
        "name": "ambient_group_chatter_debate",
        "description": "Ambient group chatter, variant B (a debate unrelated to DeniDin)",
        "role": "client",
        "chat_id": "120363000000000002@g.us",
        "is_group": True,
        "prior_turns": [
            ("user", "אני חושב שהפגישה צריכה לעבור ליום שלישי"),
        ],
        "message": "לא נראה לי, יום רביעי נוח יותר לכולם",
        "hard_assertions": {"zero_calls": True},
    },
    {
        "name": "trivial_1on1_ok_thanks",
        "description": "Trivial 1:1 acknowledgment, variant A",
        "role": "client",
        "chat_id": "972500000108@c.us",
        "is_group": False,
        "prior_turns": [
            ("assistant", "הוספתי את התזכורת שלך."),
        ],
        "message": "אוקיי תודה",
        "hard_assertions": {},
    },
    {
        "name": "trivial_1on1_lone_emoji",
        "description": "Trivial 1:1 acknowledgment, variant B (a lone emoji reply)",
        "role": "client",
        "chat_id": "972500000109@c.us",
        "is_group": False,
        "prior_turns": [
            ("assistant", "בדקתי, הכל תקין."),
        ],
        "message": "👍",
        "hard_assertions": {},
    },
    {
        "name": "gratitude_excellent_work",
        "description": "Gratitude (\"תודה רבה, עבודה מצוינת\")",
        "role": "client",
        "chat_id": "972500000110@c.us",
        "is_group": False,
        "prior_turns": [],
        "message": "תודה רבה, עבודה מצוינת!",
        "hard_assertions": {},
    },
    {
        "name": "holiday_greeting_rosh_hashana",
        "description": "Holiday greeting (Rosh Hashana)",
        "role": "client",
        "chat_id": "972500000111@c.us",
        "is_group": False,
        "prior_turns": [],
        "message": "שנה טובה ומתוקה לכל הצוות!",
        "hard_assertions": {},
    },
    {
        "name": "light_banter_joke",
        "description": "Light banter/joke turn (checks against over-reacting to humor)",
        "role": "client",
        "chat_id": "972500000112@c.us",
        "is_group": False,
        "prior_turns": [],
        "message": "האמת שהבוט הזה עובד יותר טוב ממני בבוקר יום שני 😂",
        "hard_assertions": {},
    },
]
