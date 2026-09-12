# Data Model: Fee Agreement Document Generation

## FeeAgreementVariant (config, not persisted state)

Loaded from `config/fee_agreement_templates/manifest.json` at startup (or first use — see
`doc-template-engine.md` contract). One entry per template variant.

| Field | Type | Notes |
|---|---|---|
| `variant_id` | str | e.g. `"hourly_consultation"`, `"retainer_agreement"`, `"fixed_price_project"`, `"multi_component_agreement"`, `"alternative_tracks"`. Stable identifier, used by the AI tool call. |
| `template_filename` | str | Relative filename inside `config/fee_agreement_templates/`, e.g. `"hourly_consultation.docx"`. |
| `placeholders` | List[str] | The exact scalar `{{TOKEN}}` names the template contains, e.g. `["CLIENT_NAME", "FEE_AMOUNT", "SCOPE_OF_WORK", "DATE"]`. Every one MUST be supplied by the AI's tool call — no partial fills. Does NOT include the tokens inside a `repeating_group`'s row (see below) — those are supplied per-item via `components`, not as flat scalar keys. |
| `repeating_group` | Optional[dict] | Present for `multi_component_agreement` and `alternative_tracks`. `{"min_items": 2, "row_placeholders": [...], "example_terms": [...]}`. Declares that this variant's template has exactly one repeatable block (a table row for `multi_component_agreement`; a heading+paragraph block for `alternative_tracks`), cloned once per entry in the tool call's `components` list. `example_terms` is a small set of illustrative phrasing patterns, sourced from a 2026-09-12 review of real historical fee-proposal letters, the AI can match a described component/track against and fill in — a guide for register/structure, not a closed enum; a genuinely different real arrangement is composed as its own free-text line instead of being forced into the nearest example. `None`/absent for every single-fee variant. |
| `selection_cues` | List[str] | Free-text natural-language cues (Hebrew + English) describing when this variant applies — read by the AI, not pattern-matched in code (variant selection is the model's judgment call over the manifest content, not a keyword-matching engine in Python). Each variant's cues now state explicitly whether it's single- or multi-component. |

## GeneratedDocument (in-memory / ephemeral, not persisted long-term)

Represents one fee agreement generation attempt within a single turn's tool-call chain.

| Field | Type | Notes |
|---|---|---|
| `document_id` | str (uuid4) | Correlates the `generate_fee_agreement` → `verify_fee_agreement_document` → send sequence within one turn. |
| `variant_id` | str | Which `FeeAgreementVariant` was used. |
| `values` | Dict[str, str] | The scalar placeholder→value map the AI supplied — every key MUST match `FeeAgreementVariant.placeholders` exactly (fail loudly, don't silently drop/ignore an unexpected or missing key). For `multi_component_agreement` this covers only `FIRM_NAME`/`DATE`/`CLIENT_NAME`/`SCOPE_OF_WORK`/`TOTAL_FEE` — the per-component data lives in `components`, not here. |
| `components` | Optional[List[Dict[str, str]]] | Only present (and only meaningful) for a variant with a `repeating_group`. Each entry: `{"label": ..., "terms": ...}` — one real, user-described fee component. `label` is a short name (e.g. "Referral Fee"); `terms` is ONE free-text line the AI composes fully from the conversation — a flat amount, a percentage, a cost-share split with a named partner, a specific payer entity, or any combination, whatever the user actually described (see "Variable-length component rows" below for why this is free text rather than rigid sub-fields). `len(components)` is unbounded (any N ≥ `repeating_group.min_items`), never padded or collapsed to hit a particular count. `None` for every single-fee variant. |
| `temp_path` | Path | `{data_root}/tmp/fee_agreements/{document_id}.docx`. |
| `created_at` | datetime (Israel local, `now_local()`) | For log correlation only — not embedded in the document unless `DATE` is itself one of the template's placeholders. |
| `verified` | bool | Set only after `verify_fee_agreement_document` is called and returns clean (no leftover `{{...}}` tokens, all values present). `send_document_response()` MUST refuse to send an unverified `GeneratedDocument` (defence-in-depth mirroring `WhatsAppHandler.send_response()`'s own empty-reply guard). |
| `sent` | bool | Set after a successful `sendFileByUpload` call. Drives temp-file cleanup timing. |

**Not a database row, not a dataclass persisted to disk** — this is scoped to one turn's
in-memory tool-call chain (parallels how `PendingLocalToolApproval` is in-memory-per-chat, but
even more transient: this has no "pending until next message" lifecycle at all — it's created and
resolved within the same OpenAI Responses API turn).

## Variable-length component rows (`multi_component_agreement` variant only)

Added per human feedback (2026-09-12; revised same day — an earlier draft of this section
described a fixed 3-slot cap with unused-slot deletion, which does NOT satisfy "any N > 1" and
was replaced entirely by the design below). A 4th variant distinguishes a **single, simple** fee
arrangement (the original 3 variants — one rate/fee, one scope) from a **multi-component**
engagement (several distinct, separately-priced items in one agreement — e.g. a retainer *plus*
hourly overage, or a setup fee *plus* a recurring fee *plus* a one-time onboarding charge). This
variant MUST support **any N > 1** real components — never a fixed maximum baked into the
template file.

**Implementation: one repeatable table row, cloned N times, not N pre-declared placeholder
groups.**
- `multi_component_agreement.docx` contains exactly **one** template data row in its fee table
  (generic, non-indexed placeholders: `{{COMPONENT_LABEL}}`, `{{COMPONENT_TERMS}}`) — identified
  structurally as "the only non-header row present in the source template," not by special
  marker text (the placeholders already make it unambiguous).
- `generate_fee_agreement` supplies a `components` list for this variant — one `{label, terms}`
  object per real component, `len(components) >= repeating_group.min_items` (2). Below that, the
  request isn't actually multi-component and the AI should have picked a single-fee variant
  instead.
- `DocTemplateEngine.generate()` clones the template row once per `components` entry (in the
  order given), fills each clone's two placeholders from that entry's values, inserts all clones
  in place of the original row, and discards the original (still-templated) row. The finished
  document's row count is driven entirely by `len(components)` at generation time — 2, 5, 12,
  whatever the real engagement has.
- The AI must never pad `components` to reach a round number, and never merge two genuinely
  distinct components into one entry to reduce the count — both are the same REQ-083-02
  violation (inventing/collapsing real data), just applied to a list instead of a scalar.

**Why `terms` is one free-text field, not rigid amount/percentage/payer sub-fields (human
feedback, 2026-09-12):** a component's actual arrangement varies too much to force into fixed
columns — a flat fee, a percentage/commission, a cost-share split with a named partner, a
specific payer entity different from the main Client, or any combination of these. Rather than
declaring a sub-schema for every possible shape (and inevitably missing one), `terms` is a single
line the AI composes fully from what the conversation actually established (e.g. *"15% of the
collected amount, split 50/50 with Partner Cohen, payable by the Client upon receipt"*). This
does NOT relax REQ-083-02 — every detail inside `terms` still must come from the user, never
invented; the anti-hallucination guardrail now applies at the level of "every fact stated inside
this free-text line," not just "every placeholder was filled."

**Example-guided composition (human feedback, same day): `manifest.json`'s `example_terms`
give the AI a small library of phrasing patterns drawn from typical real-world fee-agreement
shapes** (flat amount, percentage/commission, cost-share split, non-Client payer entity, hourly
overage) — each with `{{SLOT}}` placeholders of its own, purely as in-context guidance for
register and structure, never as a mechanically-enforced template. When a user-described
component matches one of these shapes, the AI fills that pattern's slots from the real facts
stated; when it doesn't (a genuinely novel arrangement), the AI composes an equally natural
free-text line from scratch rather than distorting the description to fit the nearest example.
Nothing in code parses or enforces `example_terms` against the AI's actual output — this is
prompt-level guidance surfaced through the same manifest content the AI already reads for
variant selection, not a second validation layer.

## Alternative fee tracks (`alternative_tracks` variant only)

Added 2026-09-12 per human-confirmed decision, following a review of real historical fee-proposal
letters that revealed a structural shape distinct from `multi_component_agreement`: the client is
offered a choice between **two or more mutually-exclusive fee structures for the SAME
engagement** (e.g. a flat-fee track vs. a lower-base-fee-plus-contingency-percentage track) and
picks exactly ONE — never a combination of tracks, unlike `multi_component_agreement` where every
component applies together.

**Implementation: same clone-and-discard mechanism as `multi_component_agreement`'s row, applied
one level up (at the track, not the component, granularity).**
- `alternative_tracks.docx` contains exactly **one** template "track" block (a heading placeholder
  `{{TRACK_LABEL}}` and one free-text paragraph placeholder `{{TRACK_TERMS}}`), plus a separate
  scalar placeholder `{{SHARED_ADDON_TERMS}}` for any add-on that applies regardless of which
  track is chosen (e.g. a fee for one specific extra step/appearance, as seen in the real corpus).
- `generate_fee_agreement` supplies a `components` list for this variant too (same tool-call field
  name as `multi_component_agreement`, reused for consistency rather than introducing a second,
  differently-named list parameter) — one `{label, terms}` entry per real track,
  `len(components) >= repeating_group.min_items` (2).
- Each track's `terms` is ONE free-text passage that MAY itself describe multiple sub-items
  within that track (e.g. a track that is itself staged) — fully composed by the AI from what the
  user described for THAT track specifically. Never invented, never borrowed from another track's
  description.
- `SHARED_ADDON_TERMS` is a required scalar (in `values`, not `components` — it applies once, not
  per-track). If the user described no shared add-on, the AI must state that explicitly (e.g.
  "אין תוספות החלות על שני המסלולים") rather than omitting the placeholder or inventing content —
  an empty/whitespace value is still rejected by the same validation rule as every other
  placeholder (REQ-083-02: an empty string is not a legitimate answer).
- Same anti-padding/anti-merging discipline as `multi_component_agreement`: never invent a track
  the user did not actually offer as a real alternative, never pad to a round number, never merge
  two genuinely distinct tracks into one.

## Relationships

```
FeeAgreementVariant (1) ──selected-by──> GeneratedDocument (N, one per generation attempt)
GeneratedDocument (1) ──produces──> one temp .docx file on disk (deleted after send/failure)
GeneratedDocument.components (0..1) ──drives──> N cloned table rows (multi_component_agreement only)
```

## Validation Rules

- `generate_fee_agreement`'s `values` argument MUST contain exactly the keys in
  `FeeAgreementVariant.placeholders` for the selected `variant_id` — no more, no fewer. A
  mismatch is a tool-call error surfaced back to the model (not a partial/best-effort fill),
  consistent with REQ-083-02's anti-hallucination requirement (the tool itself, not just prompt
  guidance, refuses to silently proceed with incomplete data).
- For a variant with a `repeating_group` (currently only `multi_component_agreement`):
  `components` is REQUIRED, must be a list of objects each containing exactly
  `repeating_group.row_placeholders`' keys, and `len(components) >= repeating_group.min_items`.
  For every other variant, `components` MUST be absent/`None` — supplying it is a tool-call error.
- `verify_fee_agreement_document` MUST be called with the same `document_id` `generate_fee_agreement`
  returned — no re-verifying a stale/different file path supplied by the model from memory (same
  "always re-fetch fresh, same-turn state" principle bugfix-038's Group B reference tools use for
  Morning approval prompts).
- `send_document_response()` MUST reject any `GeneratedDocument` where `verified is not True`.
