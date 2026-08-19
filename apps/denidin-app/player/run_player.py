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
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from player.config_safety import PlayerSafetyError, validate_data_root
from player.export_parser import filter_date_range, parse_export
from player.export_source import PlayerExportSource
from player.media_server import LocalMediaServer
from player.player_config import PlayerConfigError, load_player_config


def _build_config_dict(config_path: str, data_root: str) -> dict:
    """Loads an AppConfiguration-shaped JSON file (any of config.test.json/
    config.dev.json/a future config.player.json all work - only AI/OpenAI
    settings matter to the player) and returns initialize_app's config_dict,
    with `data_root` ALWAYS overridden to the validated --data-root value -
    never the config file's own data_root, regardless of what it says."""
    from src.models.config import AppConfiguration

    config = AppConfiguration.from_file(config_path)
    config.validate()
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
        'memory': config.memory,
        'constitution_config': config.constitution_config,
        'user_roles': config.user_roles,
        'mcp': config.mcp,
    }


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
) -> List[Dict]:
    """
    Replays every qualifying message in `[start, end]` (clamped per
    export_parser.filter_date_range) through DeniDin's real live pipeline.

    `import denidin` here is safe (research.md R3): the MessageSource
    refactor means it no longer constructs a live Green API bot as a side
    effect - `green_api=None` is passed to initialize_app explicitly, since
    the player never has (or needs) a live Green API connection.

    Returns the run's per-message outcome list (PlayerExportSource.outcomes).
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

    with LocalMediaServer(resolved_extract_dir) as media_base_url:
        source = PlayerExportSource(
            messages, chat_id=chat_id, sender_map=sender_map, media_base_url=media_base_url,
        )
        source.start(denidin.dispatch_notification)

    return source.outcomes


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
        whatsapp_own_number=player_config.whatsapp_own_number,
    )

    dispatched = sum(1 for o in outcomes if o["status"] == "dispatched")
    print(f"Processed {len(outcomes)} messages: {dispatched} dispatched, "
          f"{len(outcomes) - dispatched} skipped.")
    for outcome in outcomes:
        print(f"  line {outcome.get('raw_line_no')}: {outcome['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
