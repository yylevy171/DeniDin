# Bugfix 062: Naked Deposit Image Bypass

**Priority**: P0 — a real, silently dropped bank-deposit ledger event in prod, plus a
week-long deploy-config gap (missing `config/ledger_recognition_prompt.md` and
`config/fee_agreement_templates/`) that degraded the ledger recognizer and likely broke Fee
Agreement Document Generation entirely.
**Status**: Done (fix implemented and live in prod; acceptance test passing; PR: #337)
**Branch**: `bugfix/062-naked-deposit-image-bypass`

## Update 2026-09-16: original root-cause analysis was disproven; two real bugs found instead

The original theory below (a "caption" breaking the model out of a passive image-extraction
mode) was written from the acceptance test's shape, without checking real production behavior
first, and turned out to be wrong: **none** of the 4 real bank-deposit images sent in prod on
2026-09-16 had a caption — they all arrive as bare images auto-annotated by the same synthetic
"📸 התקבלה תמונה..." system message — yet 3 of the 4 still got ledger events. Verified against
the real prod session/messages and the `morning-mcp-app-prod`/`denidin-app-prod` audit logs for
that day. The caption/Invoice-Management-firewall story does not hold; the constitution edits
made in response to it (reclassifying `resolve_client_name`/`add_client` as a universal
Client Management capability, decoupled from "Invoice Management" scoping) are still good
practice and are being kept, but they do not explain or fix what actually happened. Two
separate, verified bugs are the real story:

### Bug A: mandatory client resolution is not actually enforced

Constitution's "Ledger Event Recognition" section says a `בנק` event's client must be resolved
to an exact Morning name via `resolve_client_name` before the event can be recorded. In
practice, for all 3 successful captures today, the post-turn recognizer (`recognize_ledger_event`
in `ai_handler.py`) wrote the ledger event **using the raw OCR'd payer name straight off the
deposit image** (e.g. `"ליטל תורג'מן"`, apostrophe variant) *minutes before* `resolve_client_name`
was ever called for that person — and the persisted event was never updated to the actual
resolved Morning name (`"ליטל תורגמן"`, no apostrophe) once resolution did happen. Resolution
only occurred later, as a side effect of an unrelated flow (the operator proactively sharing a
contact card, or asking for an invoice) — never because the recognizer or the main LLM
proactively drove it. The recognizer's own tool set (`RECOGNITION_TOOL`,
`QUERY_LEDGER_EVENTS_TOOL`) doesn't even include `resolve_client_name` — it has no way to verify
a client itself. Existing tests didn't catch this because they run against a correctly-mounted
`config/ledger_recognition_prompt.md` (see Bug B) — the actual enforcement logic that file is
supposed to carry (per its own commit history: "mandatory client resolution before ledger
event") has been unreachable in prod since 2026-09-07.

### Bug B (the one that actually dropped the 4th deposit): stale anonymous Docker volume

`apps/denidin-app/Dockerfile` declares `VOLUME ["/app/config", "/app/data", "/app/logs"]`.
`docker/docker-compose.{dev,prod}.yml` bind-mount only two specific files inside `/app/config`
(`config.json`, `runtime_constitution.md`) — every other file under `config/` in the image,
including `config/ledger_recognition_prompt.md` and all of `config/fee_agreement_templates/`,
depends entirely on whatever got copied into that anonymous volume the one time it was first
created. `docker compose up -d` (what `run_denidin.sh`/`deploy_release_single.sh` actually run)
does **not** refresh an existing anonymous volume on redeploy, even when a newer image adds or
changes files under that path.

Verified live on the Windows prod box:
- The `/app/config` anonymous volume was created **2026-09-07**.
- Today's running image was built **2026-09-15** and does contain `ledger_recognition_prompt.md`
  (confirmed via `git show denidin-app-v0.7.5:apps/denidin-app/config/ledger_recognition_prompt.md`).
- The container's actual `/app/config/` had no `ledger_recognition_prompt.md` and no
  `fee_agreement_templates/` at all before this fix — both post-date the volume's creation.
- `denidin-app-prod`'s logs show `WARNING - Recognition prompt file not found:
  config/ledger_recognition_prompt.md` on **every single turn** of the day, not just the missed
  deposit — `_load_recognition_prompt()` has been silently returning `""` since 2026-09-07,
  meaning the recognizer has run with no domain instructions at all (just a generic one-line
  directive) this entire time.
- For the specific missed deposit (הראל חברה לביטוח, ₪37,918, 2026-09-16 08:09): the recognition
  call fired (2 OpenAI requests, 08:10:10/08:10:13) and produced no `report_ledger_recognition`
  call at all. Per `recognize_ledger_event`'s code, that is a silent, **unlogged**
  `{"verdict": "none"}` — with no prompt telling it how to handle an ambiguous, multi-account
  company deposit, it fell back to the directive's own instruction: "When in doubt,
  verdict='none'."
- `config/fee_agreement_templates/` (Fee Agreement Document Generation's `.docx` templates +
  manifest) is under the same unmounted path — that feature has very likely been broken in prod
  since 2026-09-07 too, for the identical reason.

## Fix Specification (revised)

1. **Immediate manual fix (done 2026-09-16, live prod)**: `docker cp`'d
   `config/ledger_recognition_prompt.md` and `config/fee_agreement_templates/` directly into the
   running `denidin-app-prod` container's `/app/config/`. Both are picked up without a restart
   (`_load_recognition_prompt` is mtime-cached).
2. **Long-term fix**: added explicit bind mounts for both paths in `docker-compose.dev.yml` and
   `docker-compose.prod.yml`, matching the existing `runtime_constitution.md` pattern, so a
   redeploy always serves the current file regardless of the anonymous volume's history.
3. **Constitution wording (kept from the original analysis)**: `resolve_client_name`/
   `add_client` reclassified as a universal Client Management capability, decoupled from
   "Invoice Management" scoping, with explicit instructions to proactively resolve a naked
   `בנק` image's client. Still correct practice, even though it wasn't the cause of the dropped
   event.
4. **Test**: `caption` removed from
   `test_given_real_bank_deposit_image_then_full_fields_correctly_persisted` in
   `test_ledger_event_capture_e2e.py` so it exercises a genuinely naked upload — kept, since a
   naked upload is the real-world shape regardless of which bug caused today's incident.
5. **Bug A follow-up (done)**: re-investigation showed Bug A was fully explained by Bug B —
   `config/ledger_recognition_prompt.md` already specifies correct mandatory-client-resolution
   enforcement (an explicit evidence table: no MCP resolution evidence → `NOT resolved →
   'none', wait`); it just wasn't being read at all in prod since 2026-09-07. No separate
   enforcement redesign was needed. What *was* added: `verdict='none'` was completely silent
   (no log line, no reason field) — added an optional `none_reason` field to
   `RECOGNITION_TOOL`'s schema and an INFO log line for every `none` path in
   `recognize_ledger_event`/`_normalize_recognition_verdict`, so a future silently-dropped event
   is diagnosable without a forensic log dig like this one required. 16/16 existing unit tests
   in `tests/unit/test_recognition_call.py` still pass unmodified.

---

## Original Root Cause Analysis (2026-09-16, disproven — kept for history)

Feature 69 (Ledger Recognition) was designed to act as a background safety net, silently recording financial events (like bank deposits) based on the context of the main conversation. A core requirement for recording a bank deposit is that the client must be verified in the Morning system. The Ledger Recognizer relies entirely on the main LLM having called the `resolve_client_name` MCP tool during its turn.

However, the main LLM operates under a strict "Customer Engagement" firewall for images. The `runtime_constitution.md` dictates that when the user uploads an image, the LLM must only extract its metadata ("מטא־נתונים") and must NOT use "Invoice Management" tools.

Because `resolve_client_name` is conceptually misclassified as an "Invoice Management" tool instead of a generic client management capability (despite it interacting with Morning), the LLM refuses to use it when presented with a "naked" deposit image (an image uploaded with no explicit caption or command).

As a result:
1. The user uploads a deposit image with no caption.
2. The main LLM obediently extracts the metadata and stops, deliberately NOT calling `resolve_client_name`.
3. The Ledger Recognizer (Feature 69) runs post-turn, sees no MCP evidence of a resolved client, and strictly (but correctly, according to its rules) returns `none`.
4. The deposit is silently dropped from the ledger.

### Why the Tests Passed (original, disproven theory)
The expensive acceptance test (`test_given_real_bank_deposit_image_then_full_fields_correctly_persisted`) explicitly simulated a user uploading the image WITH a command caption: `caption="הפקדה שנכנסה, תרשום ביומן"`. This active directive caused the main LLM to break out of the passive "Customer Engagement" image extraction mode, call `resolve_client_name`, and trigger the clarification detour, which gave the Ledger Recognizer the verified client it needed.
