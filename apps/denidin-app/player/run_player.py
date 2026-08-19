#!/usr/bin/env python3
"""
run_player.py - CLI entry point / orchestrator for the WhatsApp export ->
ledger event player (Feature 043, tasks.md T014).

See specs/in-progress/043-production-data-setup-tooling/{spec.md,plan.md,
contracts/player-cli.md,quickstart.md}.

This is the driver core only (US1's main loop) - no relevancy/reconciliation/
review-queue wiring yet (later phases, per tasks.md's sequencing).
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from player.config_safety import PlayerSafetyError, validate_data_root
from player.export_parser import ParsedMessage, filter_date_range, parse_export
from player.export_source import PlayerExportSource
from player.media_server import LocalMediaServer
from player.player_config import PlayerConfigError, load_player_config

# 2026-08-19 (explicit user instruction): whenever a dispatched message's turn
# produces no ledger event and the model's real reply reads as a clarifying
# question (contains "?"), the player answers with this fixed, uninformative
# filler - never a fabricated real answer, since the player has no ground
# truth beyond the original message - and logs the question for later human
# review. This repeats (bounded by MAX_CLARIFICATION_ROUNDS) until the model
# reaches a terminal outcome: a ledger event captured, or a plain declarative
# reply with no further "?" (an explicit decision not to create one). A real
# human, unlike the player, would give a real answer instead of this filler.
FOLLOWUP_ANSWER_TEXT = "אין לי עוד מידע, תעשה הכי טוב שאתה מבין."
MAX_CLARIFICATION_ROUNDS = 5


def _build_config_dict(config_path: str, data_root: str) -> dict:
    """Loads an AppConfiguration-shaped JSON file (any of config.test.json/
    config.dev.json/a future config.player.json all work - only AI/OpenAI
    settings matter to the player) and returns initialize_app's config_dict,
    with `data_root` ALWAYS overridden to the validated --data-root value -
    never the config file's own data_root, regardless of what it says.

    2026-08-19 fix: `data_root` alone does NOT, by itself, control where
    SessionManager/MemoryManager write - both read a fixed storage_dir
    straight out of config.memory.session/.longterm, completely independent
    of data_root (see ai_handler.py's SessionManager/MemoryManager
    construction). This was a real, previously-unnoticed gap in this exact
    function - it never surfaced because the one prepared example player
    config's data_root ("test_data") happened to coincidentally match
    config.test.json's own hardcoded memory paths. For any OTHER data_root,
    session/long-term-memory would silently keep writing into config.test.json's
    real storage_dir - the shared directory the actual pytest suite uses -
    instead of the player's own isolated output folder. Explicitly overriding
    both here, the same way this exact fix was already proven out in the
    Feature 043 interactive-review scratch tooling, closes that gap for good.
    """
    from src.models.config import AppConfiguration

    config = AppConfiguration.from_file(config_path)
    config.validate()

    memory = dict(config.memory)  # never mutate the loaded config
    session_cfg = dict(memory.get('session', {}))
    session_cfg['storage_dir'] = str(Path(data_root) / "sessions")
    memory['session'] = session_cfg

    longterm_cfg = dict(memory.get('longterm', {}))
    longterm_cfg['storage_dir'] = str(Path(data_root) / "memory")
    memory['longterm'] = longterm_cfg

    return {
        'green_api_instance_id': config.green_api_instance_id,
        'green_api_token': config.green_api_token,
        'ai_api_key': config.ai_api_key,
        'ai_model': config.ai_model,
        'ai_vision_model': config.ai_vision_model,
        'ai_embedding_model': config.ai_embedding_model,
        'ai_reply_max_tokens': config.ai_reply_max_tokens,
        'log_level': config.log_level,
        'data_root': data_root,
        'feature_flags': config.feature_flags,
        'godfather_phone': config.godfather_phone,
        'memory': memory,
        'constitution_config': config.constitution_config,
        'user_roles': config.user_roles,
        'mcp': config.mcp,
    }


def _last_assistant_reply(denidin_module, chat_id: str) -> str:
    """The real model reply text just stored for this chat (SessionManager's
    own persisted conversation history) - used only to detect "the model
    asked a clarifying question" (a "?" in the reply), never to fabricate or
    guess at content."""
    session_manager = denidin_module.denidin_app.ai_handler.session_manager
    history = session_manager.get_conversation_history(chat_id)
    if history and history[-1]["role"] == "assistant":
        return history[-1]["content"] or ""
    return ""


def _log_needs_clarification(log_path: Path, *, raw_line_no: int, round_num: int,
                              original_text: str, model_question: str) -> None:
    entry = {
        "raw_line_no": raw_line_no,
        "round": round_num,
        "original_text": original_text,
        "model_question": model_question,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_replay(
    export_zip: Path,
    chat_id: str,
    sender_map: Dict[str, str],
    data_root: Path,
    config_path: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
    today: Optional[date] = None,
    extract_dir: Optional[Path] = None,
    whatsapp_own_number: str = "",
    sound_off: bool = False,
) -> List[Dict]:
    """
    Replays every qualifying message in `[start, end]` (clamped per
    export_parser.filter_date_range) through DeniDin's real live pipeline.

    `import denidin` here is safe (research.md R3): the MessageSource
    refactor means it no longer constructs a live Green API bot as a side
    effect - `green_api=None` is passed to initialize_app explicitly, since
    the player never has (or needs) a live Green API connection.

    Returns the run's per-message outcome list (PlayerExportSource.outcomes).

    sound_off: when True, prints one line per dispatched message as it
        happens (index/total, sender, a short text snippet, and the
        resulting ledger-event count) - live progress for a long run,
        rather than only a summary after everything finishes.
    """
    import denidin  # pylint: disable=import-outside-toplevel

    config_dict = _build_config_dict(config_path, str(data_root))
    denidin.denidin_app = denidin.initialize_app(config_dict, green_api=None)
    # 2026-08-19: initialize_app's own _fetch_own_whatsapp_number(green_api=None)
    # always resolves to "" (no live Green API to ask) - PlayerConfig.whatsapp_own_number
    # is the operator-supplied substitute, same idea as sender_map.
    denidin.denidin_app.ai_handler.own_whatsapp_number = whatsapp_own_number

    resolved_extract_dir = extract_dir or (data_root / "_player_extracted")
    all_messages = parse_export(export_zip, resolved_extract_dir)
    messages = filter_date_range(all_messages, start, end, today)

    events_dir = Path(data_root) / "events"
    clarification_log_path = Path(data_root) / "needs_clarification.jsonl"

    outcomes: List[Dict] = []
    total = len(messages)
    with LocalMediaServer(resolved_extract_dir) as media_base_url:
        for i, msg in enumerate(messages, start=1):
            outcome = _dispatch_with_clarification_loop(
                denidin, msg, chat_id=chat_id, sender_map=sender_map,
                media_base_url=media_base_url, events_dir=events_dir,
                clarification_log_path=clarification_log_path,
            )
            outcomes.append(outcome)
            if sound_off:
                snippet = (msg.text or "(no text)").replace("\n", " ")[:50]
                status = outcome.get("status")
                n_events = outcome.get("new_event_count", 0)
                rounds = outcome.get("clarification_rounds", 0)
                extra = f", {rounds} clarification round(s)" if rounds else ""
                print(
                    f"[{i}/{total}] line={msg.raw_line_no} {msg.sender_display_name!r} "
                    f"{snippet!r} -> status={status}, {n_events} ledger event(s){extra}",
                    flush=True,
                )

    return outcomes


def _new_event_count(events_dir: Path, before: set) -> int:
    after = set(events_dir.glob("*.json")) if events_dir.exists() else set()
    return len(after - before)


def _dispatch_with_clarification_loop(
    denidin_module, msg: ParsedMessage, *, chat_id: str, sender_map: Dict[str, str],
    media_base_url: str, events_dir: Path, clarification_log_path: Path,
) -> Dict:
    """Dispatches one real (or synthetic follow-up) message through the real,
    unmodified pipeline, then - per explicit 2026-08-19 instruction - keeps
    answering any clarifying question the model asks with a fixed,
    uninformative filler (never a fabricated real answer) until the turn
    reaches a terminal outcome: a ledger event captured, or a plain
    declarative reply with no further "?" (an explicit decision not to
    create one). Every question asked along the way is logged to
    `clarification_log_path` for later human review - a real human, unlike
    the player, would give a real answer instead of the filler. Bounded by
    MAX_CLARIFICATION_ROUNDS so a model that never settles can't loop forever;
    hitting the cap is itself logged as its own review-worthy signal."""
    before = set(events_dir.glob("*.json")) if events_dir.exists() else set()
    source = PlayerExportSource(
        [msg], chat_id=chat_id, sender_map=sender_map, media_base_url=media_base_url,
    )
    source.start(denidin_module.dispatch_notification)
    outcome = source.outcomes[0] if source.outcomes else {
        "status": "unmapped-sender", "raw_line_no": msg.raw_line_no,
    }

    current = msg
    round_num = 0
    # 2026-08-19 fix: an unmapped-sender (or unsupported-type) message was never
    # actually dispatched at all - PlayerExportSource.start() skipped it before
    # ever calling denidin.dispatch_notification. Without this guard, the loop
    # below would still fire, reading whatever the LAST REAL reply happened to
    # be (from some earlier, unrelated dispatch) and - if that stale reply
    # contained "?" - incorrectly treat this skipped message as needing a
    # clarification follow-up, injecting a bogus filler "answer" to a question
    # nobody actually just asked. Found before this exact scenario would have
    # hit it for real: 255 "דני דין" (DeniDin's own historical replies,
    # deliberately excluded from sender_map) messages in the 2026-07-01..today range.
    while (outcome.get("status") == "dispatched"
           and _new_event_count(events_dir, before) == 0
           and round_num < MAX_CLARIFICATION_ROUNDS):
        reply_text = _last_assistant_reply(denidin_module, chat_id)
        if "?" not in reply_text:
            break  # terminal: a plain declarative reply - decided not to create one
        round_num += 1
        _log_needs_clarification(
            clarification_log_path, raw_line_no=msg.raw_line_no, round_num=round_num,
            original_text=current.text, model_question=reply_text,
        )
        current = ParsedMessage(
            timestamp=current.timestamp + timedelta(seconds=30),
            sender_display_name=current.sender_display_name,
            text=FOLLOWUP_ANSWER_TEXT, attachments=[], raw_line_no=msg.raw_line_no,
        )
        followup_source = PlayerExportSource(
            [current], chat_id=chat_id, sender_map=sender_map, media_base_url=media_base_url,
        )
        followup_source.start(denidin_module.dispatch_notification)
        outcome = followup_source.outcomes[0] if followup_source.outcomes else outcome

    outcome = dict(outcome)
    outcome["clarification_rounds"] = round_num
    outcome["new_event_count"] = _new_event_count(events_dir, before)
    return outcome


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="WhatsApp export -> ledger event player (Feature 043)"
    )
    parser.add_argument("player_config", type=Path,
                         help="Path to a player config JSON file (export_zip/chat_id/"
                              "sender_map/data_root/denidin_config - see "
                              "contracts/player-cli.md)")
    parser.add_argument("--confirm-production-data-root", action="store_true",
                         help="Required in addition to a data_root that resolves to 'data'")
    parser.add_argument("--start", type=str, default=None, help="YYYY-MM-DD, clamped >= 2025-09-01")
    parser.add_argument("--end", type=str, default=None, help="YYYY-MM-DD, clamped <= today")
    parser.add_argument("--extract-dir", type=Path, default=None,
                         help="Where to extract the export zip's media files. Defaults to "
                              "<data_root>/_player_extracted (ephemeral, alongside session/event "
                              "output). Pass an explicit path (e.g. a folder next to the export "
                              "zip itself) when the extracted media should persist independently "
                              "of data_root - e.g. surviving a `--data-root` wipe between runs, "
                              "or living alongside a real source export outside the repo.")
    parser.add_argument("--sound-off", action="store_true",
                         help="Print one line per dispatched message as it happens "
                              "(index/total, sender, text snippet, resulting ledger-event "
                              "count) instead of only a summary after the whole run finishes.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        player_config = load_player_config(args.player_config)
    except PlayerConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    try:
        data_root = validate_data_root(player_config.data_root, args.confirm_production_data_root)
    except PlayerSafetyError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    start = _parse_date(args.start)
    end = _parse_date(args.end)

    outcomes = run_replay(
        export_zip=player_config.export_zip, chat_id=player_config.chat_id,
        sender_map=player_config.sender_map, data_root=data_root,
        config_path=player_config.denidin_config, start=start, end=end,
        extract_dir=args.extract_dir,
        whatsapp_own_number=player_config.whatsapp_own_number,
        sound_off=args.sound_off,
    )

    dispatched = sum(1 for o in outcomes if o["status"] == "dispatched")
    total_events = sum(o.get("new_event_count", 0) for o in outcomes)
    print(f"Processed {len(outcomes)} messages: {dispatched} dispatched, "
          f"{len(outcomes) - dispatched} skipped, {total_events} ledger event(s) total.")
    for outcome in outcomes:
        print(f"  line {outcome.get('raw_line_no')}: {outcome['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
