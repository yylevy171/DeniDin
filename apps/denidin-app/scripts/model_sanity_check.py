#!/usr/bin/env python3
"""Model sanity check — real billed OpenAI calls that validate the assumptions
DeniDin's prompt design leans on, for a given model.

Run this **whenever `config.ai_model` changes** (or when evaluating a candidate
model) before trusting it in dev/prod. Originally Feature 070 task T005; kept as
a permanent tool rather than a throwaway.

Checks
------
(a) A large, 14-day-window-shaped call **succeeds** at the target model, and
    reports `usage` (input / cached / output tokens).
(b) **Prompt caching** engages on an identical repeated prefix
    (`input_tokens_details.cached_tokens > 0` on the second call).
(c) Prints the model id + a reminder to verify its **context window / pricing**
    against the OpenAI account & docs (the API does not expose pricing).
(d) **A/B on the RECALLED MEMORIES block placement** — cached_tokens with the
    block trailing `instructions` (current shape) vs. relocated to the first
    `input` item; plus a **needle check** that a fact planted at the very start
    of the window is still answered correctly (proves nothing is silently
    dropped / uncached in a way that hurts recall).

BILLED — makes ~6 real `responses.create` calls (each output capped at 200
tokens). Never runs in CI. Reads a real `config.*.json` (no env vars,
CONSTITUTION §I). Host `python3` via the app venv — same documented
containers-only exception the backfill sub-apps use.

Usage
-----
    scripts/model_sanity_check.sh --config config/config.dev.json
    scripts/model_sanity_check.sh --config config/config.dev.json --model <candidate>
    scripts/model_sanity_check.sh --config config/config.dev.json --with-mcp --json
"""
# Standalone billed diagnostic run via the app venv - the sys.path bootstrap below
# (same pattern as apps/prod-ledger-backfill) means the src.* imports can't sit at
# the top of the module. Not part of `pylint src/` / `mypy src/` CI scope.
# pylint: disable=wrong-import-position,import-error
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from openai import OpenAI  # noqa: E402

from src.handlers.ai_handler import (  # noqa: E402
    CREATE_REMINDER_TOOL,
    DELETE_REMINDER_TOOL,
    LEDGER_EVENT_TOOL,
    LIST_REMINDERS_TOOL,
    MODIFY_REMINDER_TOOL,
    QUERY_LEDGER_EVENTS_TOOL,
)
from src.models.config import AppConfiguration  # noqa: E402
from src.models.message import AIRequest  # noqa: E402
from src.utils.logger import DEFAULT_VERSION_FILE, read_version  # noqa: E402
from src.utils.time_utils import now_local  # noqa: E402

_ENC: Any = None
try:
    import tiktoken
    _ENC = tiktoken.get_encoding("o200k_base")
except Exception:  # pragma: no cover - tiktoken is a hard dep of the app venv
    _ENC = None

NEEDLE_FACT = "מספר הפרויקט הסודי הוא 74-ALPHA-9152"
NEEDLE_QUESTION = "מה מספר הפרויקט הסודי שהוזכר קודם?"
NEEDLE_TOKEN = "74-ALPHA-9152"

RECALLED_MEMORIES_BLOCK = (
    "\n\nRECALLED MEMORIES (long-term context relevant to this conversation):\n"
    "- The client prefers invoices in ILS.\n"
    "- A fee agreement of 15% + VAT was recorded on 2026-04-02.\n"
    "- Bank deposit of 12,000 ILS noted 2026-05-11.\n"
)


def _count(text: str) -> int:
    return len(_ENC.encode(text)) if _ENC else len(text) // 4


def _load_config(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return dict(data)


def _load_constitution(cfg: Dict[str, Any]) -> str:
    cc = cfg.get("constitution_config", {}) or {}
    filename = cc.get("file") or (cc.get("files") or [None])[0]
    if not filename:
        raise SystemExit("⚠️  config has no constitution_config.file — cannot measure the real prefix")
    base = Path(cc.get("base_dir", "config"))
    fp = base if base.is_absolute() else APP_ROOT / base
    fp = fp / filename
    if not fp.is_file():
        raise SystemExit(f"⚠️  constitution file not found: {fp}")
    return str(fp.read_text(encoding="utf-8").strip())


def _build_window(target_tokens: int, *, needle_first: bool = True) -> List[Dict[str, str]]:
    """A synthetic 14-day rolling window: alternating turns, deterministic filler,
    sized to ~target_tokens. The needle fact is the very first user turn."""
    items: List[Dict[str, str]] = []
    if needle_first:
        items.append({"role": "user", "content": f"חשוב שתזכור לאורך כל השיחה: {NEEDLE_FACT}."})
        items.append({"role": "assistant", "content": "רשמתי לפניי. אמשיך."})
    filler_u = ("סיכום פעילות יומי: נשלחו הצעות מחיר, בוצעו שיחות מעקב עם לקוחות, "
                "והוזנו קבלות. נא לעדכן את הספר. ") * 6
    filler_a = ("קיבלתי. עדכנתי את הרישום הפנימי ואין צורך בפעולה נוספת כרגע. "
                "אעדכן אם יעלה משהו חריג. ") * 6
    i = 0
    running = sum(_count(x["content"]) for x in items)
    while running < target_tokens:
        if i % 2 == 0:
            c = f"[יום {i // 2 + 1}] {filler_u}"
            items.append({"role": "user", "content": c})
        else:
            c = f"{filler_a} (#{i})"
            items.append({"role": "assistant", "content": c})
        running += _count(c)
        i += 1
    return items


def _tools(cfg: Dict[str, Any], with_mcp: bool) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = [
        LEDGER_EVENT_TOOL, QUERY_LEDGER_EVENTS_TOOL,
        CREATE_REMINDER_TOOL, LIST_REMINDERS_TOOL, MODIFY_REMINDER_TOOL, DELETE_REMINDER_TOOL,
    ]
    if not with_mcp:
        return tools
    mcp = cfg.get("mcp", {}) or {}
    status_file = mcp.get("morning_status_file")
    if not status_file:
        print("⚠️  --with-mcp given but config.mcp.morning_status_file is unset — skipping MCP tool")
        return tools
    sp = Path(status_file)
    sp = sp if sp.is_absolute() else APP_ROOT / sp
    try:
        status = json.loads(sp.read_text(encoding="utf-8"))
    except OSError:
        print(f"⚠️  --with-mcp: cannot read {sp} — skipping MCP tool")
        return tools
    if status.get("status") != "running" or not status.get("url"):
        print(f"⚠️  --with-mcp: status file is not 'running' ({sp}) — skipping MCP tool")
        return tools
    tools.insert(0, {
        "type": "mcp",
        "server_label": "morning",
        "server_url": status["url"].rstrip("/") + "/mcp/",
        "headers": {"Authorization": f"Bearer {mcp.get('auth_token', '')}"},
        "require_approval": "always",
    })
    return tools


def _instructions(constitution: str, *, memories_in_instructions: bool) -> str:
    base = constitution + (RECALLED_MEMORIES_BLOCK if memories_in_instructions else "")
    # Replicates AIHandler._build_instructions' suffix (constitution + date/time +
    # version line) — same stable-prefix / trailing-dynamic-content shape that
    # makes the constitution eligible for OpenAI prompt caching.
    now = now_local()
    version = read_version(Path(DEFAULT_VERSION_FILE))
    return (
        f"{base}\n\n---\n"
        f"THE CURRENT DATE AND TIME IS {now:%Y-%m-%d %H:%M} (Asia/Jerusalem, Israel "
        f"local time). Treat this as the authoritative \"now\" when resolving any "
        f"relative or partial date/time the user gives.\n"
        f"YOUR CURRENT VERSION IS {version}. If asked what version you are running "
        f"(in any language), state this exact value."
    )


def _usage(resp: Any) -> Dict[str, Optional[int]]:
    u = getattr(resp, "usage", None)
    details = getattr(u, "input_tokens_details", None)
    return {
        "input_tokens": getattr(u, "input_tokens", None),
        "cached_tokens": getattr(details, "cached_tokens", None),
        "output_tokens": getattr(u, "output_tokens", None),
    }


def _call(client: OpenAI, model: str, instructions: str, items: List[Dict[str, str]],
          tools: List[Dict[str, Any]]) -> Any:
    return client.responses.create(
        model=model, instructions=instructions, input=items, tools=tools,  # type: ignore[arg-type]
        max_output_tokens=200,
    )


def _run_backbone_checks(client: OpenAI, cfg_path: Path,  # pylint: disable=too-many-locals
                          model: str) -> Dict[str, Any]:
    """Feature 063 R6 — Instrumentation for UAT2/UAT3/SC-004/SC-005 (no new pytest
    acceptance tests, per user-stories.md; this is the billed diagnostic run
    research.md's R6 decision named). With the flag's own real code
    (BackboneOrchestrator/identify_intent/build_plan), not a simulation:
    (a) UAT2 — small-talk turn produces an empty plan (no domain capability step
        ever executes).
    (b) UAT3 — a cross-domain turn (Ledger Query + Invoicing Read in one message)
        produces a plan with >=2 domain-capability steps.
    (c) REQ-063-04a — a media-attached turn (raw, not pre-extracted, mirroring
        denidin.py's own flag-on dispatch) produces a plan whose first step is
        Media Analysis.
    (d) REQ-063-06/SC-005 — two turns exercising the same capability (two Ledger
        Query turns) report `cached_tokens > 0` on the Backbone+capability
        instructions prefix on the second call, proving OpenAI prompt caching
        engages across turns exactly as it does for the legacy constitution.
    """
    # pylint: disable=import-outside-toplevel
    from src.backbone.capability_tags import CapabilityTag
    from src.backbone.intent_identification import identify_intent
    from src.backbone.orchestrator import BackboneOrchestrator
    from src.backbone.planning import build_plan, role_allowed_capabilities
    from src.models.media import Media
    from src.models.user import Role

    app_config = AppConfiguration.from_file(str(cfg_path))
    orchestrator = BackboneOrchestrator(client, app_config)
    allowed_tags = role_allowed_capabilities(Role.GODFATHER)

    def _request(prompt: str) -> AIRequest:
        return AIRequest(user_prompt=prompt, constitution="", max_tokens=200,
                          model=model, chat_id="model_sanity_check", message_id="msg1")

    result: Dict[str, Any] = {}

    # (a) UAT2 — small talk => empty plan
    small_talk_req = _request("מה שלומך היום?")
    intent_a = identify_intent(orchestrator, small_talk_req, allowed_tags)
    plan_a = build_plan(orchestrator, small_talk_req, intent_a, allowed_tags)
    result["uat2_small_talk_plan_is_empty"] = plan_a.is_empty
    result["uat2_small_talk_step_count"] = len(plan_a.steps)

    # (b) UAT3 — cross-domain => >=2 domain-capability steps
    cross_domain_req = _request(
        "כמה עמיר כץ שילם לפי הספר, וגם תראה לי את החשבוניות הפתוחות שלו במורנינג"
    )
    intent_b = identify_intent(orchestrator, cross_domain_req, allowed_tags)
    plan_b = build_plan(orchestrator, cross_domain_req, intent_b, allowed_tags)
    result["uat3_cross_domain_step_count"] = len(plan_b.steps)
    result["uat3_cross_domain_capabilities"] = [s.capability.value for s in plan_b.steps]
    result["uat3_cross_domain_has_multiple_steps"] = len(plan_b.steps) >= 2

    # (c) REQ-063-04a — raw media turn => Media Analysis is a plan step (first,
    # since extraction must happen before any capability can reason over content)
    media_req = _request("[media message]")
    media = Media(data=b"\xff\xd8\xff\xe0fake-jpeg-bytes", mime_type="image/jpeg", filename="receipt.jpg")
    intent_c = identify_intent(orchestrator, media_req, allowed_tags, is_media=True, media_extraction=None)
    plan_c = build_plan(orchestrator, media_req, intent_c, allowed_tags)
    result["media_plan_step_count"] = len(plan_c.steps)
    result["media_plan_capabilities"] = [s.capability.value for s in plan_c.steps]
    result["media_analysis_is_first_step"] = bool(
        plan_c.steps and plan_c.steps[0].capability == CapabilityTag.MEDIA_ANALYSIS
    )
    del media  # constructed for parity with the real dispatch shape; not sent here -
    # identify_intent/build_plan only need is_media/media_extraction, the real
    # extraction call only happens if/when a media_analysis step actually executes,
    # which this diagnostic intentionally stops short of (keeps the check cheap).

    # (d) REQ-063-06/SC-005 — same capability, two turns => caching engages
    ledger_req_1 = _request("כמה סוכם עם עמיר כץ?")
    ledger_req_2 = _request("וכמה סוכם עם דנה לוי?")
    orchestrator.ledger_event_manager = _NullLedgerEventManager()
    from src.capabilities.ledger_events.handler import query as ledger_query
    ledger_query(orchestrator, ledger_req_1, "", "עמיר כץ", {"chat_id": "model_sanity_check"})
    r2 = client.responses.create(
        model=model,
        instructions=orchestrator.build_instructions(CapabilityTag.LEDGER_QUERY, "", ledger_req_2.timestamp),
        input=[{"role": "user", "content": ledger_req_2.user_prompt}],
        max_output_tokens=200,
    )
    result["caching_second_call_usage"] = _usage(r2)
    result["caching_engaged_across_turns"] = bool((_usage(r2)["cached_tokens"] or 0) > 0)

    return result


class _NullLedgerEventManager:  # pylint: disable=too-few-public-methods
    """Minimal stand-in so ledger_query's own capability handler has a real
    (if empty) LedgerEventManager to call query_events against — this script
    deliberately never touches real persisted ledger data."""

    @staticmethod
    def query_events(_criteria: List[Dict[str, str]]) -> List[Any]:
        return []


def main(argv: Optional[List[str]] = None) -> int:  # pylint: disable=too-many-locals,too-many-statements
    ap = argparse.ArgumentParser(prog="model_sanity_check.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, help="path to a real config.*.json")
    ap.add_argument("--model", default=None, help="override config.ai_model (evaluate a candidate)")
    ap.add_argument("--target-input-tokens", type=int, default=66000,
                    help="approx size of the synthetic 14-day window (default 66000)")
    ap.add_argument("--with-mcp", action="store_true",
                    help="also attach the Morning MCP tool (needs a 'running' status file)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--backbone", action="store_true",
                    help="Feature 063 R6: also run the flag-on Backbone instrumentation "
                         "checks (UAT2/UAT3/media-plan-step/cross-turn caching) — additional "
                         "billed calls, real BackboneOrchestrator code, config.feature_flags."
                         "enable_capability_backbone need not be true in the config for this "
                         "(the orchestrator is exercised directly, not via denidin.py's flag "
                         "check)")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        print(f"⚠️  config not found: {cfg_path}", file=sys.stderr)
        return 1
    cfg = _load_config(cfg_path)
    api_key = cfg.get("ai_api_key")
    model = args.model or cfg.get("ai_model")
    if not api_key or not model:
        print("⚠️  config needs ai_api_key and ai_model (or pass --model)", file=sys.stderr)
        return 1

    constitution = _load_constitution(cfg)
    client = OpenAI(api_key=api_key)
    tools = _tools(cfg, args.with_mcp)

    instr_trailing = _instructions(constitution, memories_in_instructions=True)
    instr_leading = _instructions(constitution, memories_in_instructions=False)
    window = _build_window(args.target_input_tokens)
    window_leading = ([{"role": "user", "content": RECALLED_MEMORIES_BLOCK.strip()}] + window)

    report: Dict[str, Any] = {"model": model, "config": str(cfg_path),
                              "approx_prefix_tokens": _count(instr_trailing),
                              "approx_window_tokens": sum(_count(i["content"]) for i in window),
                              "tool_count": len(tools),
                              "with_mcp": any(t.get("type") == "mcp" for t in tools)}

    # (a) large call succeeds + usage
    r1 = _call(client, model, instr_trailing, window, tools)
    report["a_first_call"] = _usage(r1)

    # (b) identical repeat → caching
    r2 = _call(client, model, instr_trailing, window, tools)
    report["b_repeat_call"] = _usage(r2)
    report["b_caching_engaged"] = bool((_usage(r2)["cached_tokens"] or 0) > 0)

    # (c) context window / pricing pointer
    ctx = None
    try:
        m = client.models.retrieve(model)
        ctx = getattr(m, "context_window", None) or getattr(m, "max_context_window", None)
    except Exception:  # pragma: no cover
        ctx = None
    report["c_context_window_from_api"] = ctx
    report["c_pricing_note"] = ("verify input/output $/1M tokens for "
                                f"'{model}' against the OpenAI account & docs — not exposed via API")

    # (d) A/B placement of RECALLED MEMORIES + needle check
    d_trailing = _call(client, model, instr_trailing, window, tools)
    d_leading = _call(client, model, instr_leading, window_leading, tools)
    report["d_memories_trailing_instructions"] = _usage(d_trailing)
    report["d_memories_leading_input"] = _usage(d_leading)

    needle = _call(client, model, instr_trailing,
                   window + [{"role": "user", "content": NEEDLE_QUESTION}], tools)
    answer = (getattr(needle, "output_text", "") or "")
    report["d_needle_answer_excerpt"] = answer[:200]
    report["d_needle_recalled"] = NEEDLE_TOKEN in answer

    if args.backbone:
        report["backbone"] = _run_backbone_checks(client, cfg_path, model)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_human(report)

    ok = report["a_first_call"]["input_tokens"] is not None and report["d_needle_recalled"]
    return 0 if ok else 1


def _print_human(r: Dict[str, Any]) -> None:
    print(f"\n=== model sanity check: {r['model']} ===")
    print(f"config              : {r['config']}")
    print(f"prefix tokens (~)   : {r['approx_prefix_tokens']}")
    print(f"window tokens (~)   : {r['approx_window_tokens']}")
    print(f"tools attached       : {r['tool_count']} (mcp: {r['with_mcp']})")
    print("\n(a) large call succeeded:")
    print(f"    {r['a_first_call']}")
    print("\n(b) prompt caching on identical repeat:")
    print(f"    {r['b_repeat_call']}")
    print(f"    caching engaged  : {r['b_caching_engaged']}")
    print("\n(c) context / pricing:")
    print(f"    context_window (API): {r['c_context_window_from_api']}")
    print(f"    {r['c_pricing_note']}")
    print("\n(d) RECALLED MEMORIES placement A/B:")
    print(f"    trailing instructions : {r['d_memories_trailing_instructions']}")
    print(f"    leading input item    : {r['d_memories_leading_input']}")
    print(f"    needle recalled       : {r['d_needle_recalled']}  ({r['d_needle_answer_excerpt']!r})")
    if "backbone" in r:
        b = r["backbone"]
        print("\n=== Feature 063 Backbone instrumentation (R6) ===")
        print(f"UAT2 small-talk -> empty plan : {b['uat2_small_talk_plan_is_empty']} "
              f"(steps={b['uat2_small_talk_step_count']})")
        print(f"UAT3 cross-domain -> >=2 steps: {b['uat3_cross_domain_has_multiple_steps']} "
              f"(steps={b['uat3_cross_domain_capabilities']})")
        print(f"Media turn -> Media Analysis first: {b['media_analysis_is_first_step']} "
              f"(steps={b['media_plan_capabilities']})")
        print(f"Cross-turn caching engaged     : {b['caching_engaged_across_turns']} "
              f"({b['caching_second_call_usage']})")
    print()


if __name__ == "__main__":
    sys.exit(main())
