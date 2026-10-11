#!/usr/bin/env python3
"""Feature 075 helper for scripts/run_sanity_parallel.sh.

Read a parallel-sweep results file and print, one node id per line, the failures
whose traceback carries a transport/infra signature: a dropped ngrok tunnel
under concurrent load, an OpenAI 424 "Failed Dependency" on the MCP tool-list
fetch, an API timeout/connection error. These - and only these - are what the
sweep re-runs. Real assertion failures and model nondeterminism are terminal and
never printed here.

Usage:  _sanity_retryable_failures.py <results_file>
Exit 0 always (a classifier, not a gate). No matches => no output.
"""
import re
import sys

# Signatures that mean "the request never got a fair shot at the server".
_SIG = re.compile(
    r"mcp_network_error"
    r"|mcp_tool_execution_error"
    r"|Failed Dependency"
    r"|Connection failed\."
    r"|Error retrieving tool list from MCP server"
    r"|external_connector_error"
    r"|APITimeoutError"
    r"|APIConnectionError"
    r"|ReadTimeout|ConnectTimeout"
    r"|502 Bad Gateway|503 Service|504 Gateway"
    r"|Http status code: 424",
    re.IGNORECASE,
)

# A pytest per-test traceback header: a whole line that starts and ends with
# underscores and carries a test-ish name in the middle. Log lines never match
# (they start with a timestamp, not "_ "). Handles pytest's width-dependent
# padding (as few as one underscore each side for a very long name) and the
# "ERROR at setup of <Class>.<test>" form.
_HEADER = re.compile(r"^_+ (.+?) _+\s*$", re.M)
# End-of-section rule ("=== warnings summary ===", "=== short test summary ===", ...).
_SECTION = re.compile(r"^=+ .+? =+\s*$", re.M)


def _last_summary(text):
    blocks = re.findall(
        r"=+ short test summary info =+\n(.*?)(?:\n=+ |\Z)", text, re.S
    )
    return blocks[-1] if blocks else ""


def _name_matches(nodeid, header_name):
    """Does a FAILURES/ERRORS header name refer to this node id?"""
    segs = nodeid.split("::")
    func = segs[-1]
    if func not in header_name:
        return False
    if len(segs) >= 3:  # Class::test - header is "Class.test" or "... of Class.test"
        cls = segs[-2]
        if cls not in header_name:
            return False
    return True


def main(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    summary = _last_summary(text)
    failed = re.findall(r"^(?:FAILED|ERROR)\s+(\S+)", summary, re.M)
    if not failed:
        return

    headers = list(_HEADER.finditer(text))

    def block_for(nodeid):
        """Concatenate every traceback/section body under a header naming this test."""
        chunks = []
        for i, h in enumerate(headers):
            if not _name_matches(nodeid, h.group(1)):
                continue
            start = h.end()
            end = len(text)
            if i + 1 < len(headers):
                end = headers[i + 1].start()
            sec = _SECTION.search(text, start, end)
            if sec:
                end = sec.start()
            chunks.append(text[start:end])
        return "\n".join(chunks)

    seen = set()
    for nodeid in failed:
        if nodeid in seen:
            continue
        seen.add(nodeid)
        if _SIG.search(block_for(nodeid)):
            print(nodeid)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: _sanity_retryable_failures.py <results_file>")
    main(sys.argv[1])
