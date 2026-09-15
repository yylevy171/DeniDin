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


def main(argv: Optional[List[str]] = None) -> int:  # pylint: disable=too-many-locals
    ap = argparse.ArgumentParser(prog="model_sanity_check.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, help="path to a real config.*.json")
    ap.add_argument("--model", default=None, help="override config.ai_model (evaluate a candidate)")
    ap.add_argument("--target-input-tokens", type=int, default=66000,
                    help="approx size of the synthetic 14-day window (default 66000)")
    ap.add_argument("--with-mcp", action="store_true",
                    help="also attach the Morning MCP tool (needs a 'running' status file)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
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
    print()


if __name__ == "__main__":
    sys.exit(main())
