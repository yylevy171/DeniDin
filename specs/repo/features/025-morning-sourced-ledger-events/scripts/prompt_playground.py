#!/usr/bin/env python3
"""
Reconciliation-prompt playground (Feature 025).

A standalone script for iterating on the accounting-reconciliation sweep's
prompt WITHOUT rebuilding/restarting denidin-app-dev each time - reuses the
already-running morning-mcp-app-dev container's live tunnel, makes the exact
same OpenAI Responses API + Morning MCP call _sweep_accounting_documents
makes, and dumps everything the call actually did (every mcp_call's real
tool output, every capture_ledger_event call's full parsed arguments) -
NEVER persists anything via LedgerEventManager. Pure observation.

Once a prompt version here reliably produces correct results (get_invoice_details
called per document, amount/description populated, real creation timestamps -
not list_invoices-only guesses), copy the finalized prompt text into
services/accounting_reconciliation_service.py's _build_reconciliation_prompt
and redeploy for real - this script is a development tool, not part of the
shipped feature.

Run from apps/denidin-app (needs its own venv - the repo-root .venv has
`openai` installed, PYTHONPATH must include apps/denidin-app for the
LEDGER_EVENT_TOOL import to resolve):

    cd apps/denidin-app
    PYTHONPATH=. ../../.venv/bin/python3 \\
        ../../specs/in-progress/025-morning-sourced-ledger-events/scripts/prompt_playground.py \\
        [--since 2026-08-20] [--prompt-file PATH]

Requires morning-mcp-app-dev already running (for its live MCP tunnel) -
does NOT start/stop/touch any container itself.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DENIDIN_APP_ROOT = REPO_ROOT / "apps" / "denidin-app"
DEFAULT_PROMPT_FILE = Path(__file__).resolve().parent / "prompt.txt"
DEFAULT_INSTRUCTIONS_FILE = Path(__file__).resolve().parent / "instructions.txt"

sys.path.insert(0, str(DENIDIN_APP_ROOT))

from openai import OpenAI  # noqa: E402
from src.handlers.ai_handler import LEDGER_EVENT_TOOL, extract_all_function_calls  # noqa: E402


def load_config() -> dict:
    with (DENIDIN_APP_ROOT / "config" / "config.dev.json").open(encoding="utf-8") as f:
        return json.load(f)


def discover_morning_mcp_tool(config: dict) -> dict:
    """Same discovery denidin-app's own MorningMcpLocator does, but reading
    the HOST-side status file path directly (this script runs on the host,
    not inside a container - the container-internal path in config.dev.json's
    mcp.morning_status_file doesn't exist here)."""
    status_file = REPO_ROOT / "shared" / "mcp-status-dev" / "morning_mcp_status.dev.json"
    if not status_file.exists():
        raise SystemExit(f"Morning MCP status file not found: {status_file} - is morning-mcp-app-dev running?")

    with status_file.open(encoding="utf-8") as f:
        status = json.load(f)
    if status.get("status") != "running":
        raise SystemExit(f"Morning MCP server not running: {status}")

    server_url = status["server_url"]
    mcp_config = config["mcp"]
    auth_token = mcp_config["morning_auth_token"]

    return {
        "type": "mcp",
        "server_label": mcp_config.get("morning_server_label", "morning-invoices"),
        "server_url": server_url,
        # No approval-required tools relevant here - playground only ever
        # exercises list_invoices/get_invoice_details (read-only), so no
        # require_approval filtering needed for this script's purpose.
        "require_approval": "never",
        "headers": {"Authorization": f"Bearer {auth_token}"},
    }


def dump_response(response) -> None:
    print("\n" + "=" * 78)
    print("FULL RESPONSE DUMP")
    print("=" * 78)

    output = getattr(response, "output", None) or []
    mcp_calls = [item for item in output if getattr(item, "type", None) == "mcp_call"]
    other_items = [item for item in output if getattr(item, "type", None) not in ("mcp_call", "function_call")]

    print(f"\n--- {len(mcp_calls)} mcp_call item(s) ---")
    for i, item in enumerate(mcp_calls):
        print(f"\n[{i}] tool={item.name!r}")
        print(f"    arguments: {item.arguments}")
        print(f"    error: {item.error}")
        out = item.output or ""
        print(f"    output ({len(out)} chars):")
        print("    " + out.replace("\n", "\n    "))

    ledger_calls = extract_all_function_calls(response, LEDGER_EVENT_TOOL["name"])
    print(f"\n--- {len(ledger_calls)} capture_ledger_event call(s) ---")
    for i, call in enumerate(ledger_calls):
        print(f"\n[{i}] call_id={call['call_id']}")
        if call["arguments"] is None:
            print("    UNPARSEABLE ARGUMENTS")
            continue
        args = call["arguments"]
        print(json.dumps(args, indent=4, ensure_ascii=False))
        # Flag the two known-problematic fields explicitly for quick scanning.
        creation_date = args.get("accounting_document_creation_date")
        flag = ""
        if not creation_date:
            flag = "  <-- MISSING"
        elif creation_date.endswith("T00:00:00") or creation_date.endswith("T00:00"):
            flag = "  <-- SUSPICIOUS (midnight - likely defaulted from list_invoices' date-only field)"
        print(f"    accounting_document_creation_date: {creation_date!r}{flag}")
        components = args.get("components") or []
        for comp in components:
            if comp.get("amount") is None or comp.get("description") is None:
                print(f"    <-- component missing amount/description: {comp}")

    if other_items:
        print(f"\n--- {len(other_items)} other output item(s) ---")
        for item in other_items:
            print(f"  type={getattr(item, 'type', None)!r}")

    print(f"\n--- response.output_text ---")
    print(repr(getattr(response, "output_text", None)))

    usage = getattr(response, "usage", None)
    if usage:
        print(f"\n--- usage --- total={usage.total_tokens} input={usage.input_tokens} output={usage.output_tokens}")

    print(f"\n--- status --- {getattr(response, 'status', None)}")
    incomplete = getattr(response, "incomplete_details", None)
    if incomplete:
        print(f"--- incomplete_details --- reason={getattr(incomplete, 'reason', None)}")

    reasoning_items = [item for item in output if getattr(item, "type", None) == "reasoning"]
    for i, item in enumerate(reasoning_items):
        summary = getattr(item, "summary", None)
        print(f"--- reasoning[{i}] summary --- {summary}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since", default=None,
        help="YYYY-MM-DD - defaults to 2 days ago (matches FALLBACK_LOOKBACK)"
    )
    parser.add_argument(
        "--reasoning-effort", choices=["low", "medium", "high"], default=None,
        help="Never set anywhere in the real app (API default used everywhere) - "
             "test whether a higher effort improves multi-step tool-call compliance."
    )
    parser.add_argument(
        "--max-output-tokens", type=int, default=None,
        help=(
            "Real bug found live: _sweep_accounting_documents never sets this at all "
            "(unlike every conversational call, which explicitly sets it up to "
            "config.ai_reply_max_tokens=20000) - defaults to whatever the API's own "
            "default is, which may be far smaller. Pass e.g. 20000 to test the fix."
        )
    )
    parser.add_argument(
        "--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE,
        help=f"Prompt template file (default: {DEFAULT_PROMPT_FILE}) - edit this between runs"
    )
    parser.add_argument(
        "--instructions-file", type=Path, default=DEFAULT_INSTRUCTIONS_FILE,
        help=(
            f"Optional instructions= (system-level) file (default: {DEFAULT_INSTRUCTIONS_FILE}, "
            "if it exists) - a stronger-weighted channel than the user-role prompt. Pass "
            "--instructions-file /dev/null (or delete the default file) to test WITHOUT "
            "instructions=, matching the original bare-user-message shape."
        )
    )
    args = parser.parse_args()

    since_str = args.since or (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

    if not args.prompt_file.exists():
        raise SystemExit(f"Prompt file not found: {args.prompt_file}")
    template = args.prompt_file.read_text(encoding="utf-8")
    prompt = template.replace("{{SINCE}}", since_str)

    print(f"since = {since_str}")
    print(f"prompt file = {args.prompt_file}")
    print("\n--- PROMPT TEXT ---")
    print(prompt)

    instructions = None
    if args.instructions_file.exists():
        instructions = args.instructions_file.read_text(encoding="utf-8")
        print(f"\ninstructions file = {args.instructions_file}")
        print("--- INSTRUCTIONS TEXT ---")
        print(instructions)
    else:
        print(f"\nNo instructions file at {args.instructions_file} - calling WITHOUT instructions=")

    config = load_config()
    morning_tool = discover_morning_mcp_tool(config)
    tools = [morning_tool, LEDGER_EVENT_TOOL]

    client = OpenAI(api_key=config["ai_api_key"])

    print(f"\nCalling OpenAI ({config['ai_model']}) with Morning MCP + LEDGER_EVENT_TOOL attached...")
    create_kwargs = dict(
        model=config["ai_model"],
        input=[{"role": "user", "content": prompt}],
        tools=tools,
    )
    if instructions:
        create_kwargs["instructions"] = instructions
    if args.max_output_tokens:
        create_kwargs["max_output_tokens"] = args.max_output_tokens
        print(f"max_output_tokens = {args.max_output_tokens}")
    if args.reasoning_effort:
        create_kwargs["reasoning"] = {"effort": args.reasoning_effort}
        print(f"reasoning.effort = {args.reasoning_effort}")
    response = client.responses.create(**create_kwargs)

    dump_response(response)

    out_path = Path(__file__).resolve().parent / f"last_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({
            "since": since_str,
            "prompt": prompt,
            "output_text": getattr(response, "output_text", None),
            "mcp_calls": [
                {"name": item.name, "arguments": item.arguments, "output": item.output}
                for item in (response.output or []) if getattr(item, "type", None) == "mcp_call"
            ],
            "capture_ledger_event_calls": extract_all_function_calls(response, LEDGER_EVENT_TOOL["name"]),
        }, f, indent=2, ensure_ascii=False)
    print(f"\nFull structured dump also saved to: {out_path}")


if __name__ == "__main__":
    main()
