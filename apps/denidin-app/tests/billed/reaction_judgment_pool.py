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
    # --- Added 2026-09-12: reproductions of real live dev failures where the
    # model had react_to_message attached but never called it, despite the
    # "any ask" constitution wording. These are the exact patterns from real
    # WhatsApp T013 testing this session - see logs/reaction_tuning/tuning_log.md
    # for the incident this session's constitution fix addresses.
    {
        "name": "new_client_and_fee_agreement_single_message",
        "description": (
            "Real dev failure repro: a new-client-add + fee-agreement ask, both "
            "stated in ONE message (mirrors the live 'יויו ביויו' conversation, "
            "2026-09-12, which produced zero reactions end to end). Expects a fast "
            "ack once the ask is understood, then a resolution reaction once the "
            "client is actually added (a second one if the agreement resolves "
            "separately)."
        ),
        "role": "godfather",
        "chat_id": "972500000113@c.us",
        "is_group": False,
        "prior_turns": [],
        "message": (
            "בוא ננסה שוב - יש לי לקוח חדש בשם יויו ביויו עם טלפון 0588881117. "
            "הסכם שכר טרחה על 21 שח"
        ),
        "hard_assertions": {},
    },
    {
        "name": "add_client_not_found_needs_full_details",
        "description": (
            "Real dev failure repro: a bare 'add a new client <name>' ask with no "
            "email/phone yet (mirrors the live 'תוסיף לקוח חדש גידי גוב' turn, "
            "2026-09-12, which the model correctly answered by asking for missing "
            "details but never reacted on). Expects a fast ack on the ask itself "
            "even though the turn's whole reply is a clarifying question, not yet "
            "a completed action."
        ),
        "role": "godfather",
        "chat_id": "972500000114@c.us",
        "is_group": False,
        "prior_turns": [],
        "message": "תוסיף לקוח חדש גידי גוב",
        "hard_assertions": {},
    },
    {
        "name": "add_client_then_agreement_two_resolutions",
        "description": (
            "Real dev failure repro: a multi-turn add-client-then-agreement flow "
            "(mirrors the live conversation that added client 'יוסי מרמורק' via "
            "the interactive-buttons approval flow, then documented a fee "
            "agreement against that same client, 2026-09-12 - zero reactions fired "
            "across either resolution). The email/phone were already supplied in "
            "an earlier turn and the client was already approved; this turn's ask "
            "is the fee-agreement documentation, which should get its own fast ack "
            "and its own resolution reaction, independent of the earlier client-add."
        ),
        "role": "godfather",
        "chat_id": "972500000115@c.us",
        "is_group": False,
        "prior_turns": [
            ("user", "לקוח חדש: יוסי מרמורק, מייל yossi@example.com, טלפון 0501234567"),
            ("assistant", "📋 לאישור — לקוח חדש:\nשם: יוסי מרמורק\nמייל: yossi@example.com\nטלפון: 0501234567\n\nאישור — כן/לא?"),
            ("user", "כן"),
            ("assistant", "הלקוח החדש נוסף בהצלחה: יוסי מרמורק."),
        ],
        "message": "מעולה, תעד גם הסכם שכר טרחה מולו על 5,000 ש\"ח",
        "hard_assertions": {},
    },
    {
        "name": "reminder_ask_then_full_local_resolution",
        "description": (
            "A fully-specified create_reminder ask (name + exact time, so the model "
            "has everything it needs and actually proposes the tool call for real - "
            "not just a clarifying question), then a real 'כן' confirmation in the "
            "SAME chat - unlike the add_client scenarios above, this resolves "
            "entirely through LOCAL tools (create_reminder + its own approval flow, "
            "PendingLocalToolApprovalManager), no Morning MCP tunnel required, so the "
            "full ask -> resolution reaction cycle can be verified end to end even "
            "outside a live dev environment. Both turns are dispatched as real "
            "messages through the real pipeline (only 'user'-role prior_turns are "
            "actually replayed by the driver - there is deliberately no seeded "
            "'assistant' turn here, since one that doesn't match what the model "
            "would really say produces a confirmation with nothing real to confirm)."
        ),
        "role": "godfather",
        "chat_id": "972500000118@c.us",
        "is_group": False,
        "prior_turns": [
            # An absolute future date/time, not "מחר" - the manual driver's synthetic
            # webhook carries a fixed historical idMessage timestamp unrelated to the
            # real Israel-local "today" AIHandler injects, and a relative date produced
            # a spurious "that's already in the past" rejection when tried here.
            ("user", "תזכיר לי ב-25/9/2026 בשעה 10:00 להתקשר ללקוח בעניין החוזה"),
        ],
        "message": "כן",
        "hard_assertions": {},
    },
]
