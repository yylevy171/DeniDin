#!/usr/bin/env python3
"""
debug_exact_calls / parse_trace.py

Parses one app log file (denidin-app's per-test-file log, or logs/denidin.log)
into a single, timestamp-ordered, VERBATIM trace across all six boundaries:

  1. user  -> app       (boundary='whatsapp' direction='in',  context='webhook')
  2. app   -> user       (boundary='whatsapp' direction='out', any context -
                          text/buttons/reaction/progress/proactive/file/etc.)
  3. app   -> model      (boundary='openai'   direction='out')
  4. model -> app        (boundary='openai'   direction='in')
  5. model -> morning mcp   (mcp_call items INSIDE an 'openai'/'in' response -
                              the `arguments` field)
  6. morning mcp -> model   (the SAME mcp_call items' `output`/`error` field)

2026-09-24: reads `src/utils/wire_log.py`'s ONE unified pair of log lines -
`[WIRE-AUDIT] boundary=... direction=... context=... <concise summary>` and
`[WIRE-DEBUG] boundary=... direction=... context=... payload=<full verbatim
content>` - emitted by every wire-crossing call site in the app (OpenAI and
WhatsApp alike) calling `src/utils/wire_log.py`'s `audit_wire`/`debug_wire`
directly - the ONLY two wire-logging functions in the codebase, no
per-module wrapper anywhere. One consistent format, one parser, no more
per-boundary bespoke log shapes.

2026-09-29: output is now a single Markdown document (not plain text), one
collapsible `<details>` section per logical wire-crossing event - an
AUDIT line and its immediately-following DEBUG line for the SAME
boundary/direction/context (they are always logged back-to-back at the same
call site, same second) are merged into ONE section rather than printed as
two separate blocks. A model->app response's own `instructions` field, and
any embedded `mcp_call` items (Morning MCP request/result, categories 5/6),
are nested `<details>` sub-sections inside that same section, collapsed by
default - GitHub-flavored Markdown renders `<details>` as a real
collapsible widget with no JS needed.

Never paraphrases, truncates, or reorders content - every field is printed
exactly as logged. This is a READ-ONLY tool over EXISTING log files; it makes
no calls of its own and needs no config/credentials.

Usage:
    python3 parse_trace.py --log <path/to/test_file.log> [--since "HH:MM:SS"] [--until "HH:MM:SS"] [--date YYYY-MM-DD]

    --since/--until: plain HH:MM:SS (24h, log's own local-time zone, no need to
        requote the offset) - narrows to one turn/test's window. Omit either to
        run to the start/end of the file. If omitted entirely, the WHOLE file
        is parsed (can be large - always narrow with --since/--until once you
        know roughly when the turn happened, e.g. from a `run_single_test.sh`
        timestamp or a prior grep).
    --date: defaults to today; only matters when combined with --since/--until.

Output is one Markdown document to stdout: a collapsible section per event,
in file order (= chronological order), each labeled with its category and
full verbatim content.
"""
import argparse
import ast
import json
import re
import sys
from datetime import datetime
from pathlib import Path

LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:[+-]\d{4})? - "
    r"(?P<logger>[\w.]+) - (?P<level>\w+) - (?P<msg>.*)$"
)

WIRE_RE = re.compile(
    r"^\[WIRE-(?P<kind>AUDIT|DEBUG)\] boundary=(?P<boundary>'(?:[^'\\]|\\.)*') "
    r"direction=(?P<direction>'(?:[^'\\]|\\.)*') context=(?P<context>'(?:[^'\\]|\\.)*') (?P<rest>.*)$"
)


def parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")


def in_window(ts: datetime, since: datetime, until: datetime) -> bool:
    if since and ts < since:
        return False
    if until and ts > until:
        return False
    return True


def unquote(literal: str) -> str:
    try:
        return ast.literal_eval(literal)
    except (ValueError, SyntaxError):
        return literal


def try_literal_or_json(text: str):
    """DEBUG payloads are either a Python repr (`repr(kwargs)`/`repr(dict)`)
    or, for an OpenAI SDK response object, its raw `model_dump_json()` text
    used as-is (see wire_log.py's `debug_wire`). Try JSON first, then a
    Python literal, returning None if both fail (never hide a line just
    because it didn't parse - the caller falls back to the raw text)."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None


# call_id -> tool name, accumulated across every openai/in response seen so
# far in file order - lets a later openai/out block's function_call_output
# items (which carry only call_id, not the tool name) be attributed back to
# the specific tool call they answer, instead of appearing as an anonymous
# blob inside a generic `input` dump.
_CALL_ID_TO_TOOL: dict = {}
# call_id -> parsed arguments, same accumulation - lets a later app log line
# that names only a call_id (e.g. a skipped react_to_message) show what the
# model asked for (the emoji).
_CALL_ID_TO_ARGS: dict = {}

# messaging_actions.py logs this, naming the call, whenever react_to_message
# returns before send_reaction - so no [WIRE-*] reaction line exists for it.
# Rendered as an APP -> USER reaction marked NOT SENT, never silently dropped.
REACTION_SKIPPED_RE = re.compile(
    r"^\[084\] react_to_message call '(?P<call_id>[^']*)': nothing to react through "
    r"\(target_id=(?P<target>.*?), chat_id=(?P<chat>.*?), green_api_bot_set=(?P<bot>True|False)\)$"
)

# How many backticks to fence a code block with - bumped above any run of
# backticks actually present in the content, so a payload that itself
# contains ``` never breaks out of its own fence.
def _fence_for(text: str) -> str:
    longest = 0
    for m in re.finditer(r"`+", text or ""):
        longest = max(longest, len(m.group(0)))
    return "`" * max(3, longest + 1)


def code_block(text: str, lang: str = "") -> str:
    fence = _fence_for(text)
    return f"{fence}{lang}\n{text}\n{fence}"


def details(summary: str, body: str, open_by_default: bool = False) -> str:
    open_attr = " open" if open_by_default else ""
    return f"<details{open_attr}>\n<summary>{summary}</summary>\n\n{body}\n\n</details>"


def _readable_text(value) -> str:
    """Re-renders a value so embedded non-ASCII text (Hebrew etc.) prints
    literally instead of as \\uXXXX escapes. Some upstream producers (e.g.
    morning-mcp-app's own `json.dumps(...)`, which defaults to
    `ensure_ascii=True`) bake those escapes into the actual string content
    before it's ever logged - so a plain str()/repr() of it here would print
    the escapes verbatim, which is exactly what this replaces. If `value` is
    a JSON-encoded string, re-parses and re-dumps it with
    `ensure_ascii=False` (pretty-printed); a dict/list gets the same
    treatment directly; anything else (or anything that doesn't parse as
    JSON) falls back to a plain `str(value)`, unchanged."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except (ValueError, TypeError):
            return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _extract_mcp_calls(data: dict) -> list:
    """Every embedded mcp_call item in one openai/in response's `output`
    list, in order."""
    if not isinstance(data, dict):
        return []
    return [item for item in (data.get("output") or [])
            if isinstance(item, dict) and item.get("type") == "mcp_call"]


def render_mcp_call_sections(item: dict) -> tuple:
    """One embedded mcp_call item split into its two distinct halves, each
    returned as a standalone markdown body with NO commentary linking them -
    the caller gives each its own numbered top-level turn (2026-09-29,
    explicit request: these must be unmistakably separate - what Morning
    actually replied vs. whatever the model does next - never nested inside
    the containing MODEL -> APP turn, never with a note bridging them)."""
    name = item.get("name")
    call_body = "\n".join([
        f"- tool name: `{name}`",
        f"- server_label: `{item.get('server_label')!r}`",
        "",
        "arguments:",
        code_block(_readable_text(item.get("arguments")), "json"),
    ])
    if item.get("error"):
        result_body = "error:\n" + code_block(_readable_text(item.get("error")), "json")
    else:
        result_body = "output:\n" + code_block(_readable_text(item.get("output")), "json")
    return call_body, result_body


def _extract_flows_and_capabilities(instructions_val) -> tuple:
    """Pulls the loaded-flows/loaded-capabilities pair out of an
    `instructions` value in EITHER of its two shapes: the real, full
    backbone prompt text (debug - has literal "## Loaded flows"/"##
    Loaded capabilities" sections), or wire_log.py's own short named
    substitute for it (audit - "backbone (flows=X, capabilities=Y)").
    Returns (flows, capabilities), either side None if not found/not a
    backbone call at all (e.g. the legacy ai_handler / ledger recognition
    prompts, which have neither)."""
    if not isinstance(instructions_val, str):
        return None, None
    m_flows = re.search(r"## Loaded flows\n\n([^\n]+)", instructions_val)
    m_caps = re.search(r"## Loaded capabilities\n\n([^\n]+)", instructions_val)
    if m_flows or m_caps:
        return (m_flows.group(1).strip() if m_flows else None,
                m_caps.group(1).strip() if m_caps else None)
    m_short = re.match(r"backbone \(flows=(.*), capabilities=(.*)\)$", instructions_val)
    if m_short:
        return m_short.group(1), m_short.group(2)
    return None, None


def render_openai_debug_out(data: dict) -> str:
    """The full `instructions`/`input`/`tools`/etc. detail for an APP -> MODEL
    request, as markdown - `instructions` nested in its own collapsible.
    `flows`/`capabilities` get their own always-visible bullet line, up
    front, in BOTH audit and debug alike - no more having to expand and
    scroll the (debug-only) full instructions text just to see what was
    loaded for this round."""
    parts = []
    if "instructions" in data:
        flows, caps = _extract_flows_and_capabilities(data["instructions"])
        if flows is not None or caps is not None:
            parts.append(f"- flows: {flows}")
            parts.append(f"- capabilities: {caps}")
    for key in ("input", "tools", "previous_response_id", "max_output_tokens", "model"):
        if key not in data:
            continue
        val = data[key]
        if key == "tools" and isinstance(val, list):
            parts.append(f"- tools ({len(val)}): {[t.get('name', t.get('type')) for t in val]}")
        elif key == "input":
            lines = ["**input:**", ""]
            for item in val if isinstance(val, list) else []:
                if isinstance(item, dict) and item.get("type") == "function_call_output":
                    call_id = item.get("call_id")
                    tool_name = _CALL_ID_TO_TOOL.get(call_id, "<unknown tool - call_id not seen yet>")
                    lines.append(f"- app's reply to `{tool_name}` (call_id=`{call_id}`):")
                    lines.append(code_block(_readable_text(item.get("output")), "text"))
                elif isinstance(item, dict) and isinstance(item.get("content"), list):
                    # A multi-part message (e.g. a vision request: prompt text + image) -
                    # each part shown on its own, the text readable rather than escaped.
                    lines.append(f"- message (role={item.get('role')}):")
                    for part in item["content"]:
                        if isinstance(part, dict) and part.get("type") == "input_text":
                            lines.append(code_block(part.get("text", ""), "text"))
                        elif isinstance(part, dict) and part.get("type") == "input_image":
                            lines.append(f"  - image: `{part.get('image_url')}` detail=`{part.get('detail')}`")
                        else:
                            lines.append(code_block(json.dumps(part, ensure_ascii=False), "json"))
                else:
                    lines.append(code_block(json.dumps(item, ensure_ascii=False), "json"))
            parts.append("\n".join(lines))
        else:
            parts.append(f"- {key}: `{val!r}`")
    if "instructions" in data:
        val = data["instructions"]
        # A debug call's `instructions` is the real, long prompt text -> its
        # own nested collapsible. An audit call's is wire_log.py's own short
        # name substitute (e.g. "backbone (flows=..., capabilities=...)") -
        # this is what lets the SAME renderer serve both: audit and debug are
        # now identical structured data, this field is the one place they
        # deliberately differ, so it's the one place rendering branches.
        if isinstance(val, str) and len(val) > 300:
            parts.append(details(f"↳↳ instructions ({len(val)} chars)", code_block(val, "text")))
        else:
            parts.append(f"- instructions: {val}")
    extra = {k: v for k, v in data.items()
             if k not in ("instructions", "input", "tools", "previous_response_id", "max_output_tokens", "model")}
    if extra:
        parts.append(f"- other kwargs: `{extra!r}`")
    return "\n\n".join(parts)


def render_openai_debug_in(data: dict) -> str:
    """The full response detail for a MODEL -> APP response, as markdown.
    Output items render in their ORIGINAL order, never reordered - EXCEPT an
    mcp_call item is skipped here entirely: it gets its own two standalone
    top-level turns instead (see `render_mcp_call_sections` / the caller in
    `render_event`), never nested inside this one, per explicit request
    (2026-09-29) that a Morning reply and the model's own next move must
    read as unmistakably separate things, not one bundled turn."""
    parts = [f"- response.id: `{data.get('id')}`", f"- status: `{data.get('status')}`"]
    usage = data.get("usage")
    if usage:
        parts.append(f"- usage: `{json.dumps(usage, ensure_ascii=False)}`")
    output_items = data.get("output") or []
    for item in output_items:
        item_type = item.get("type")
        if item_type == "reasoning":
            parts.append("- reasoning item (content not user-visible)")
        elif item_type == "message":
            for c in item.get("content", []):
                parts.append(f"- message (role={item.get('role')}): {_readable_text(c.get('text'))!r}")
        elif item_type == "function_call":
            parts.append(f"- function_call: `{item.get('name')}` call_id=`{item.get('call_id')}`")
            parts.append(code_block(_readable_text(item.get("arguments")), "json"))
            if item.get("call_id"):
                _CALL_ID_TO_TOOL[item["call_id"]] = item.get("name")
                _CALL_ID_TO_ARGS[item["call_id"]] = try_literal_or_json(item.get("arguments") or "")
        elif item_type == "mcp_call":
            continue  # rendered as its own separate top-level turns by the caller
        elif item_type == "mcp_approval_request":
            parts.append(f"- mcp_approval_request: name=`{item.get('name')}` args=`{_readable_text(item.get('arguments'))}`")
        elif item_type == "mcp_list_tools":
            names = [t.get("name") for t in item.get("tools", [])]
            parts.append(f"- mcp_list_tools ({item.get('server_label')}): {names}")
        else:
            parts.append(f"- other item type=`{item_type}`: `{json.dumps(item, ensure_ascii=False)}`")
    return "\n".join(parts)


def render_whatsapp_debug(data, payload_text: str) -> str:
    return code_block(json.dumps(data, ensure_ascii=False, indent=2) if data is not None else payload_text, "json")


def category_label(boundary: str, direction: str, context: str) -> str:
    """Just the boundary/direction arrow description - no number. The
    number in front of it is the event's actual chronological position
    (see `render_event`'s `index` param), not a fixed per-category one, so
    it always counts 1, 2, 3, 4, 5... straight up the file regardless of
    which boundary/direction each event happens to be."""
    if boundary == "whatsapp":
        if direction == "in" and context == "webhook":
            return "USER → APP"
        return "APP → USER" if direction == "out" else "USER ← APP (send result)"
    if boundary == "openai":
        return "APP → MODEL" if direction == "out" else "MODEL → APP"
    if boundary == "vision":
        # The media extractors' vision model (config.ai_vision_model) - possibly
        # a different model from the conversational one, so named apart.
        return "APP → VISION MODEL" if direction == "out" else "VISION MODEL → APP"
    return f"UNKNOWN boundary={boundary!r}"


def _render_openai_or_whatsapp_body(boundary: str, direction: str, payload_text: str) -> str:
    """Renders one wire-log payload's full body - shared by Audit and Debug
    alike, since both now carry the same structured shape (see wire_log.py's
    2026-09-29 audit_wire rewrite)."""
    data = try_literal_or_json(payload_text)
    if boundary in ("openai", "vision") and direction == "out":
        return render_openai_debug_out(data) if data is not None else code_block(payload_text, "text")
    if boundary in ("openai", "vision") and direction == "in":
        return render_openai_debug_in(data) if data is not None else payload_text
    return render_whatsapp_debug(data, payload_text)


def render_event(index: int, ts: str, kind_seen: str, boundary: str, direction: str, context: str,
                  audit_rest: str, debug_payload_text: str):
    """One or more turn-level sections for a single wire-crossing event,
    exactly 3 levels deep each, nothing more:
      1. turn title (one per returned block) - collapses everything below.
         Numbered sequentially starting at `index`, always going up by
         exactly 1 per block, never jumping around by category.
      2. exactly two possible sub-sections directly under it, each its own
         independently collapsible `<details>`, prefixed "↳" so the level
         is visually obvious even in a plain-text editor with no
         indentation rendering: "↳ Audit" and "↳ Debug".
      3. inside Debug ONLY, the long `instructions` text (openai/out calls)
         gets its own nested collapsible, prefixed "↳↳" (one arrow deeper
         than its parent) - everything else in Debug (function calls,
         messages, usage, etc.) sits directly in the Debug body and
         collapses/expands with it, no further nesting.

    An `openai`/`in` event whose response embeds one or more `mcp_call`
    items (2026-09-29, explicit request) is NOT rendered as a single turn
    with the mcp traffic buried inside it - each embedded mcp_call becomes
    its OWN two standalone top-level turns ("MODEL -> MORNING MCP" then
    "MORNING MCP -> MODEL" - source -> destination, same convention as every
    other label here, e.g. "APP -> MODEL"/"MODEL -> APP"), with no linking
    commentary between them and no
    commentary inside the MODEL -> APP turn that contains them either - the
    reader must be able to tell distinctly, from the numbered title alone,
    which is a Morning reply and which is the model's next move. Returns
    (blocks, next_index) so the caller can print however many blocks this
    one event actually produced and advance its own running counter
    correctly."""
    blocks = []

    def _make_block(i, label_text, audit_body_text, debug_body_text):
        summary = f"{i}. [{ts}] {label_text}"
        sub_sections = []
        if audit_body_text is not None:
            sub_sections.append(details("↳ Audit (concise, INFO-level - what prod actually logs)", audit_body_text))
        if debug_body_text is not None:
            sub_sections.append(details("↳ Debug (full, verbatim)", debug_body_text))
        return details(summary, "\n\n".join(sub_sections))

    label = f"{category_label(boundary, direction, context)} — context={context}"

    # Parse both payloads (if present) up front so we can detect embedded
    # mcp_call items and split them out of the main MODEL -> APP body.
    audit_data = try_literal_or_json(audit_rest) if audit_rest is not None else None
    debug_data = try_literal_or_json(debug_payload_text) if debug_payload_text is not None else None

    mcp_calls = []
    if boundary == "openai" and direction == "in":
        # Prefer debug_data (full payload) for extraction; fall back to
        # audit_data (structurally identical since 2026-09-29) if debug is
        # missing for some reason.
        source = debug_data if isinstance(debug_data, dict) else audit_data
        if isinstance(source, dict):
            mcp_calls = _extract_mcp_calls(source)

    if not mcp_calls:
        audit_body = _render_openai_or_whatsapp_body(boundary, direction, audit_rest) if audit_rest is not None else None
        debug_body = (_render_openai_or_whatsapp_body(boundary, direction, debug_payload_text)
                      if debug_payload_text is not None else None)
        blocks.append(_make_block(index, label, audit_body, debug_body))
        return blocks, index + 1

    # 2026-09-30: hosted MCP calls execute server-side INSIDE this one
    # response, and their position in `output` is real ordering - items
    # listed after an mcp_call were produced after its result came back.
    # Rendering every MCP turn after the whole response made later
    # function_calls look like they preceded the MCP result (a false
    # "premature success" finding). So the response is split into
    # segments at each mcp_call, and the turns are emitted in output order:
    # [items before] -> MCP call -> MCP result -> [items after] -> ...
    def _segments(data):
        segs, cur = [], []
        for item in (data.get("output") or []) if isinstance(data, dict) else []:
            if item.get("type") == "mcp_call":
                segs.append(cur)
                segs.append(item)
                cur = []
            else:
                cur.append(item)
        segs.append(cur)
        return segs

    debug_segs = _segments(debug_data)
    audit_segs = _segments(audit_data) if isinstance(audit_data, dict) else None
    if audit_segs is not None and len(audit_segs) != len(debug_segs):
        audit_segs = None
    n_parts = sum(1 for s in debug_segs if isinstance(s, list))
    part = 0
    next_index = index
    for pos, seg in enumerate(debug_segs):
        if isinstance(seg, list):
            part += 1
            if not seg and part not in (1, n_parts):
                continue  # two adjacent mcp_calls - nothing between them
            debug_body = render_openai_debug_in({**(debug_data or {}), "output": seg}) if debug_data is not None else "(debug data missing)"
            audit_body = (render_openai_debug_in({**audit_data, "output": audit_segs[pos]})
                          if audit_segs is not None else None)
            if not seg:
                debug_body += "\n- (no output items in this part)"
            blocks.append(_make_block(next_index, f"{label} (response part {part}/{n_parts})",
                                      audit_body, debug_body))
            next_index += 1
        else:
            name = seg.get("name")
            call_body, result_body = render_mcp_call_sections(seg)
            # Same content serves as both Audit and Debug here - an mcp_call's
            # arguments/output are already fully verbatim in the response dump
            # this was extracted from; there is no separate concise/full pair
            # for it the way there is for a top-level openai/whatsapp event.
            blocks.append(_make_block(next_index, f"MODEL → MORNING MCP — {name}", None, call_body))
            next_index += 1
            blocks.append(_make_block(next_index, f"MORNING MCP → MODEL — {name}", None, result_body))
            next_index += 1

    return blocks, next_index


def handle_capability_audit(index: int, ts, msg) -> str:
    return details(f"{index}. [{ts}] APP-INTERNAL: tool dispatch outcome",
                    code_block(msg, "text"))


def handle_reaction_skipped(index: int, ts, msg, m) -> str:
    """A react_to_message the app never sent: APP -> USER, marked NOT SENT,
    with the reason read from the app's own log line (shown verbatim)."""
    args = _CALL_ID_TO_ARGS.get(m.group("call_id"))
    emoji = args.get("emoji", "?") if isinstance(args, dict) else "?"
    if m.group("bot") == "False":
        reason = "no WhatsApp bot in this run"
    elif m.group("target") == "None":
        reason = "no message to react to"
    else:
        reason = "no chat to react in"
    return details(f"{index}. [{ts}] APP → USER — context=reaction — {emoji} — NOT SENT ({reason})",
                   code_block(msg, "text"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True, action="append", help="Log file path (repeatable)")
    ap.add_argument("--since", help="HH:MM:SS, narrows the start of the window")
    ap.add_argument("--until", help="HH:MM:SS, narrows the end of the window")
    ap.add_argument("--date", help="YYYY-MM-DD, defaults to today (only used with --since/--until)")
    args = ap.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    since = parse_ts(f"{date_str} {args.since}") if args.since else None
    until = parse_ts(f"{date_str} {args.until}") if args.until else None

    events = []
    for log_path in args.log:
        path = Path(log_path)
        if not path.exists():
            print(f"ERROR: log file not found: {path}", file=sys.stderr)
            sys.exit(1)
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                m = LINE_RE.match(line.rstrip("\n"))
                if not m:
                    continue
                ts = parse_ts(m.group("ts"))
                if not in_window(ts, since, until):
                    continue
                events.append((ts, m.group("msg")))

    events.sort(key=lambda e: e[0])

    if not events:
        print("No matching log lines in the given window. Widen --since/--until or check the log path.", file=sys.stderr)
        sys.exit(1)

    print("# Wire trace\n")
    print("Each numbered section below is one wire-crossing event, in strict "
          "chronological order (the number always goes up by 1, regardless "
          "of which boundary/direction it is). Click a section to expand it. "
          "Each has exactly two sub-sections, marked `↳` - Audit (concise) "
          "and Debug (full, verbatim) - and, inside Debug only, the long "
          "`instructions` text nests one level deeper, marked `↳↳`.\n")

    i = 0
    n = len(events)
    event_index = 0  # sequential position of the next top-level section,
    # incremented once per section actually printed below - always goes up
    # by 1, straight through the file in chronological order, regardless
    # of which boundary/direction/branch produced it.
    consumed = set()  # indices already rendered as the partner of an earlier line
    while i < n:
        if i in consumed:
            i += 1
            continue
        ts, msg = events[i]
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")

        if msg.startswith("[WIRE-AUDIT]") or msg.startswith("[WIRE-DEBUG]"):
            m = WIRE_RE.match(msg)
            if not m:
                event_index += 1
                print(details(f"{event_index}. [{ts_str}] UNPARSEABLE [WIRE-*] line (report this)",
                               code_block(msg, "text")))
                print()
                i += 1
                continue
            kind = m.group("kind")
            boundary = unquote(m.group("boundary"))
            direction = unquote(m.group("direction"))
            context = unquote(m.group("context"))
            rest = m.group("rest")

            audit_rest = None
            debug_payload_text = None
            if kind == "AUDIT":
                audit_rest = rest
            else:
                debug_payload_text = rest[len("payload="):] if rest.startswith("payload=") else rest

            # Look ahead to the next [WIRE-*] line in the same second: same
            # boundary/direction/context, the other kind - they are logged
            # back-to-back at the same call site (see module docstring), but
            # an unrelated line from another thread (e.g. the apscheduler
            # typing keepalive) can land between them, so skip non-wire lines.
            j = i + 1
            while (j < n and events[j][0] == ts
                   and not events[j][1].startswith(("[WIRE-AUDIT]", "[WIRE-DEBUG]"))):
                j += 1
            if j < n and j not in consumed:
                ts2, msg2 = events[j]
                m2 = WIRE_RE.match(msg2) if (msg2.startswith("[WIRE-AUDIT]") or msg2.startswith("[WIRE-DEBUG]")) else None
                if m2 and ts2 == ts:
                    kind2 = m2.group("kind")
                    boundary2 = unquote(m2.group("boundary"))
                    direction2 = unquote(m2.group("direction"))
                    context2 = unquote(m2.group("context"))
                    if (kind2 != kind and boundary2 == boundary
                            and direction2 == direction and context2 == context):
                        rest2 = m2.group("rest")
                        if kind2 == "AUDIT":
                            audit_rest = rest2
                        else:
                            debug_payload_text = rest2[len("payload="):] if rest2.startswith("payload=") else rest2
                        consumed.add(j)  # the paired line is rendered here, not again

            blocks, next_index = render_event(event_index + 1, ts_str, kind, boundary, direction, context,
                                               audit_rest, debug_payload_text)
            event_index = next_index - 1  # keep event_index as "last index used", like every other branch
            for block in blocks:
                print(block)
                print()
            i += 1

        elif msg.startswith("[CAPABILITY-AUDIT]"):
            event_index += 1
            print(handle_capability_audit(event_index, ts_str, msg))
            print()
            i += 1

        elif REACTION_SKIPPED_RE.match(msg):
            event_index += 1
            print(handle_reaction_skipped(event_index, ts_str, msg, REACTION_SKIPPED_RE.match(msg)))
            print()
            i += 1

        # Backward compatibility with older log files predating the
        # 2026-09-24 wire_log.py consolidation.
        elif msg.startswith("[AUDIT-IN]"):
            event_index += 1
            print(details(f"{event_index}. [{ts_str}] USER → APP (legacy [AUDIT-IN] format, pre-2026-09-24 log)",
                           code_block(msg[len("[AUDIT-IN] "):], "text")))
            print()
            i += 1
        elif msg.startswith("[AUDIT-OUT]"):
            event_index += 1
            print(details(f"{event_index}. [{ts_str}] APP → USER (legacy [AUDIT-OUT] format, pre-2026-09-24 log)",
                           code_block(msg[len("[AUDIT-OUT] "):], "text")))
            print()
            i += 1
        elif msg.startswith("[RAWLOG]"):
            rm = re.match(r"^\[RAWLOG\] (?P<context>.+?) (?P<dir>>>> SENDING|<<< RECEIVED): (?P<payload>.*)$", msg)
            if not rm:
                i += 1
                continue
            context, direction, payload = rm.group("context"), rm.group("dir"), rm.group("payload")
            data = try_literal_or_json(payload)
            event_index += 1
            if direction == ">>> SENDING":
                body = render_openai_debug_out(data) if data is not None else code_block(payload, "text")
                print(details(f"{event_index}. [{ts_str}] APP → MODEL — {context} (legacy [RAWLOG], pre-2026-09-24)", body))
            else:
                main = render_openai_debug_in(data) if data is not None else payload
                print(details(f"{event_index}. [{ts_str}] MODEL → APP — {context} (legacy [RAWLOG], pre-2026-09-24)", main))
            print()
            i += 1
        else:
            i += 1


if __name__ == "__main__":
    main()
