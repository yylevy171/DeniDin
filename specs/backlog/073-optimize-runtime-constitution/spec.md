# Feature Specification: Optimize the Runtime Constitution

**Feature Branch**: `feature/073-optimize-runtime-constitution`
**Created**: 2026-09-03
**Status**: Placeholder / draft — not yet through `speckit.clarify`; do not implement against this file yet
**Input**: User description: "Optimize the runtime constitution — it has grown to ~26.6K tokens / 111KB (6.6× its 2026-07-23 size). Reduce its size significantly with zero behaviour regression, to cut per-turn latency, first-turn / cache-miss cost, and instruction dilution."

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval (present alongside this file; Given-When-Then). Spec approval is BLOCKED without it. See `.github/METHODOLOGY.md §I`.

**IMPORTANT**: This spec MUST comply with:
- **CONSTITUTION.md** (§I–III, §V): coding standards, Israel-local timestamps, git workflow, NO environment variables, integration tests as real entry points, ZERO internal mocking.
- **METHODOLOGY.md** (§I, II, VI, VIII, IX, X): specification-first, mandatory user stories, terminology glossary, technology choices, REQ-* identifiers, "TDD" = billed/expensive acceptance tests written+run once at the end.

**Required Files** (per METHODOLOGY.md): `user-stories.md` (MANDATORY), `spec.md` (this file), `plan.md`, `tasks.md` — the last two are produced by `speckit.plan` / `speckit.tasks` after clarification.

---

## Context & Motivation

`apps/denidin-app/config/runtime_constitution.md` is the model's `instructions` string on **every**
OpenAI Responses API call in the app: every conversational turn, every Feature 022 approval
follow-up, every Feature 024 ledger follow-up, every Feature 025 reconciliation sweep tick, and the
Feature 024 image-path ledger classification call (`ImageExtractor._classify_ledger_event`). It is
assembled as the **stable, byte-identical prefix** of every call so OpenAI prompt caching applies
(constitution first, then recalled-memory context, then a `---` separator, then the per-call date —
see `handlers/ai_handler.py`'s `_build_instructions`).

**Measured 2026-09-03** (Feature 070 T005 spike, `tiktoken` `o200k_base`): the file is **26,618
tokens / 111 KB / 1,750 lines** — up ~6.6× from the "~4.0K tokens" recorded in CLAUDE.md on
2026-07-23. Roughly 84% of the lines are three sections:

| Section | approx lines | approx share |
|---|---|---|
| `## Invoice Management Context (Morning)` | ~780 | ~45% |
| `## Ledger Event Recognition` | ~360 | ~21% |
| `## Ledger Event Querying` | ~330 | ~19% |
| everything else (identity, roles, privacy, contexts, group etiquette, reminders) | ~280 | ~15% |

### Why this is worth doing (it is NOT a correctness problem today)

`gpt-5.6-luna`'s context window is 1,050,000 tokens and caching engages at ~100% after the first
turn of a conversation (Feature 070 D11/D12), so there is **no context-fit or steady-state cost
crisis**. The costs are real but second-order:

1. **First-turn / cache-miss input cost.** ~26.6K uncached input tokens at $0.20/1M ≈ **$0.0053
   every time the cache is cold** — a fresh conversation, or any turn after the prompt cache TTL
   lapses. Multiplied across all 1:1 chats, all group chats, and every background reconciliation
   tick (which has no conversational cache locality), this adds up.
2. **Latency.** A 26.6K-token instruction block is processed on every cold call; a smaller prompt
   is measurably faster to first token.
3. **Instruction dilution / "lost in the middle".** 26.6K tokens of instructions is a lot for the
   model to weight correctly. Rules that matter (RBAC boundaries, "ask, never guess", the
   double-count guard) compete for attention with verbose worked examples and restated caveats.
   Every past bugfix that touched this file did so by *adding* prose; none removed any.
4. **Maintainability.** A 1,750-line instruction file is hard to review and easy to make
   internally contradictory (the CLAUDE.md note about the "ZERO MOCKING" vs §I/§V contradiction is
   the same failure mode).

### Why it is delicate

Nearly every paragraph in this file exists because of a **real incident** (bugfix-014's
double-count guidance, Feature 054's reminder scoping, Feature 044's ambiguous-name handling,
Feature 039's group etiquette, …). This is **not** a "delete the verbose parts" exercise — it is a
"say the same thing in fewer tokens, and move rarely-triggered detail somewhere cheaper" exercise,
verified against the billed/sanity suite so no behaviour regresses.

---

## Goals

- **G1** — Reduce `runtime_constitution.md` to a target token budget (candidate: **≤ 12,000
  tokens**, ~55% reduction; final target set during `speckit.clarify`) measured by `tiktoken`
  `o200k_base`.
- **G2** — **Zero behaviour regression**: every existing `billed`, `expensive`, and `sanity` test
  passes unchanged; the Feature 059 sanity suite is the acceptance gate.
- **G3** — Preserve the prompt-caching property: the constitution stays the byte-stable prefix; no
  per-call-dynamic content is introduced into it.
- **G4** — Every rule currently enforced by the constitution is still enforced — either still in
  the file (tighter wording) or relocated to a place the model still sees at the right time (a
  tool's JSON-schema `description`, per METHODOLOGY §XXI's "every tool-bearing feature needs
  explicit constitution boundaries" — relocation must not weaken those boundaries).
- **G5** — Establish a **standing size budget + a check** so the file can't silently balloon again
  (e.g. a non-blocking test that logs a warning above N tokens, mirroring `verify_sanity_lists.sh`'s
  drift-guard pattern).

## Non-Goals

- **NG1** — Changing what the assistant does, refuses, or asks. This is pure instruction
  compression.
- **NG2** — Splitting the constitution into multiple files or per-environment copies (it is
  deliberately one shared file — bugfix from 2026-07-23 when dev/prod copies drifted).
- **NG3** — Relocating the RECALLED MEMORIES block or touching `_build_instructions`' assembly
  order (Feature 070 D12 closed that as "no change").
- **NG4** — Any change to the Morning MCP tool schemas, the local function tools, or RBAC.
  Relocating *guidance* into an existing tool `description` is in scope; changing tool *behaviour*
  is not.
- **NG5** — Rewriting the SpecKit governance docs (`CONSTITUTION.md` / `METHODOLOGY.md`). Those are
  developer-facing, not the model's `instructions`.

---

## Approach (sketch — refined in `plan.md`)

1. **Baseline & instrument.** Record the current token count per top-level section. Add a
   throwaway measurement of first-token latency and `cached_tokens` behaviour via
   `scripts/model_sanity_check.sh` before/after (billed — human-approved).
2. **Section-by-section compression pass**, largest first (`Invoice Management Context` →
   `Ledger Event Recognition` → `Ledger Event Querying`):
   - collapse repeated worked examples to one canonical example + a rule;
   - de-duplicate guidance that is restated in 2–3 places (e.g. "ask, never guess" appears many
     times — state it once in a principles section, reference it);
   - move deep procedural detail that only matters *inside* a specific tool call into that tool's
     schema `description` (bounded, testable, still seen by the model at call time);
   - keep every negative-scoping / "when NOT to use this tool" boundary verbatim in spirit
     (METHODOLOGY §XXI) — these are the cheapest bytes to get wrong.
3. **Regression gate after every section**: run the relevant `billed`/`sanity` subset; a section's
   compression does not land until its tests are green.
4. **Final acceptance**: full sanity suite + the Feature-070-style billed acceptance scenarios for
   invoicing, ledger capture, ledger querying, reminders, and group etiquette — run once, together.
5. **Add the size-budget check** (G5) and update CLAUDE.md's stale "~4.0K tokens" note with the new
   real number + the budget.

---

## Requirements *(mandatory — REQ-* assigned during `speckit.plan`; FR-* placeholders here)*

### Functional Requirements

- **FR-001**: The system MUST continue to load `runtime_constitution.md` as the model's
  `instructions` via `constitution_config` with mtime hot-reload — unchanged mechanism.
- **FR-002**: The compressed constitution MUST keep the assistant's externally observable
  behaviour identical: same refusals, same clarifying questions, same tool choices, same approval
  prompts, same Hebrew phrasing conventions, for every scenario covered by the existing
  `billed`/`expensive`/`sanity` suites.
- **FR-003**: Every "when this tool does NOT apply" boundary currently in the constitution MUST
  remain expressed with equal or greater clarity, in the constitution or the tool's own
  `description` (METHODOLOGY §XXI). No boundary may be dropped.
- **FR-004**: The constitution MUST remain a single shared file (dev/prod/test identical) and
  remain the byte-stable cache prefix (no per-call-dynamic content moved into it).
- **FR-005**: A size check MUST exist that reports the file's `o200k_base` token count against a
  configured budget and flags (non-blocking) when exceeded; it MUST NOT run automatically in a way
  that blocks unrelated work.
- **FR-006**: CLAUDE.md's constitution size/caching note MUST be updated to the real current
  number and the new budget.

### Key Entities

- **Runtime constitution** (`config/runtime_constitution.md`): the model-facing instruction
  document. Sections, token counts, and the cache-prefix property are its relevant attributes.
- **Tool `description` fields**: the alternative low-cost home for procedural detail that only
  matters at a specific tool call — bounded, per METHODOLOGY §XXI.

---

## Success Criteria *(mandatory)*

- **SC-001**: `runtime_constitution.md` is ≤ the agreed token budget (candidate ≤ 12,000
  `o200k_base` tokens), down from 26,618.
- **SC-002**: 100% of the pre-existing `billed`, `expensive`, and `sanity` tests pass unchanged
  (immutable tests — METHODOLOGY §VI.b).
- **SC-003**: A fresh `speckit`-style billed acceptance pass covering invoicing, ledger capture,
  ledger querying, reminders, and group etiquette passes on the first run against the compressed
  file.
- **SC-004**: Measured cold-call (`cached_tokens == 0`) input token count for a standard turn
  drops by ≥ the same proportion as the file (e.g. ≥ 45%), via `scripts/model_sanity_check.sh`
  before/after.
- **SC-005**: The size-budget check exists and is documented in CLAUDE.md; a deliberate test edit
  pushing the file over budget makes it flag.
- **SC-006**: No new internal contradiction is introduced (a reviewer diff-checks that every
  removed sentence's rule survives somewhere).

---

## Risks & Open Questions

- **R1** — Behaviour regression that no existing test catches (the suites are good but not
  exhaustive). Mitigation: compress section-by-section with a test gate each; keep the diff
  reviewable; a human reads the before/after of each section.
- **R2** — Moving guidance into tool `description`s could bloat the *tools* payload instead (also
  sent every call, also cached). Net token accounting must be measured, not assumed.
- **R3** — The Hebrew worked examples carry subtle phrasing the model imitates; over-compressing
  them could shift the assistant's tone. Keep one canonical example per pattern rather than
  deleting all.
- **Q1** — Final token budget: ≤ 12K? ≤ 10K? ≤ 15K? (`speckit.clarify`)
- **Q2** — Should the size check be a `pytest` test (in the excluded-by-default lane), a standalone
  script like `verify_sanity_lists.sh`, or a pre-commit-style hook? (`speckit.clarify`)
- **Q3** — Is any section a candidate for *removal* rather than compression — i.e. does it describe
  a mechanism that no longer exists or a scenario the model handles fine without it? (audit during
  `speckit.plan`)

---

## Dependencies

- Builds on Feature 070's `scripts/model_sanity_check.sh` for before/after measurement.
- No code dependency on any in-flight feature; touches only `config/runtime_constitution.md`,
  possibly some tool `description` strings, one new check, and a CLAUDE.md note.
