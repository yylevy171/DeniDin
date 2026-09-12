# Data Model: Fee Agreement Document Generation

## FeeAgreementVariant (config, not persisted state)

Loaded from `config/fee_agreement_templates/manifest.json` at startup (or first use — see
`doc-template-engine.md` contract). One entry per template variant.

| Field | Type | Notes |
|---|---|---|
| `variant_id` | str | e.g. `"hourly_consultation"`, `"retainer_agreement"`, `"fixed_price_project"`. Stable identifier, used by the AI tool call. |
| `template_filename` | str | Relative filename inside `config/fee_agreement_templates/`, e.g. `"hourly_consultation.docx"`. |
| `placeholders` | List[str] | The exact `{{TOKEN}}` names the template contains, e.g. `["CLIENT_NAME", "FEE_AMOUNT", "SCOPE_OF_WORK", "DATE"]`. Every one MUST be supplied by the AI's tool call — no partial fills. |
| `selection_cues` | List[str] | Free-text natural-language cues (Hebrew + English) describing when this variant applies — read by the AI, not pattern-matched in code (variant selection is the model's judgment call over the manifest content, not a keyword-matching engine in Python). |

## GeneratedDocument (in-memory / ephemeral, not persisted long-term)

Represents one fee agreement generation attempt within a single turn's tool-call chain.

| Field | Type | Notes |
|---|---|---|
| `document_id` | str (uuid4) | Correlates the `generate_fee_agreement` → `verify_fee_agreement_document` → send sequence within one turn. |
| `variant_id` | str | Which `FeeAgreementVariant` was used. |
| `values` | Dict[str, str] | The placeholder→value map the AI supplied — every key MUST match `FeeAgreementVariant.placeholders` exactly (fail loudly, don't silently drop/ignore an unexpected or missing key). |
| `temp_path` | Path | `{data_root}/tmp/fee_agreements/{document_id}.docx`. |
| `created_at` | datetime (Israel local, `now_local()`) | For log correlation only — not embedded in the document unless `DATE` is itself one of the template's placeholders. |
| `verified` | bool | Set only after `verify_fee_agreement_document` is called and returns clean (no leftover `{{...}}` tokens, all values present). `send_document_response()` MUST refuse to send an unverified `GeneratedDocument` (defence-in-depth mirroring `WhatsAppHandler.send_response()`'s own empty-reply guard). |
| `sent` | bool | Set after a successful `sendFileByUpload` call. Drives temp-file cleanup timing. |

**Not a database row, not a dataclass persisted to disk** — this is scoped to one turn's
in-memory tool-call chain (parallels how `PendingLocalToolApproval` is in-memory-per-chat, but
even more transient: this has no "pending until next message" lifecycle at all — it's created and
resolved within the same OpenAI Responses API turn).

## Variable-length component rows (`multi_component_agreement` variant only)

Added per human feedback (2026-09-12): a 4th variant distinguishes a **single, simple** fee
arrangement (the original 3 variants — one rate/fee, one scope) from a **multi-component**
engagement (several distinct, separately-priced items in one agreement — e.g. a retainer *plus*
hourly overage, or a setup fee *plus* a recurring fee). `multi_component_agreement.docx` has a
3-row fee table (`COMPONENT_1_*`/`COMPONENT_2_*`/`COMPONENT_3_*` placeholder groups, each
`_NAME`/`_DESCRIPTION`/`_FEE`) as an upper bound, not a requirement to always fill all 3.

- The AI supplies a `values` map containing only the placeholder groups that correspond to real,
  user-stated components (1, 2, or 3 of them).
- `DocTemplateEngine.generate()` deletes the table row(s) for any `COMPONENT_N_*` group entirely
  absent from `values` — it does **not** require the AI to supply a filler value (e.g. `"N/A"`,
  `"-"`) for an unused slot, since inventing *any* value for a slot the user didn't actually
  describe is still the guessing REQ-083-02 forbids, even for a "there's nothing here" marker.
- This is the one place `generate()`'s "exactly matching placeholder keys" validation rule (see
  Validation Rules below) is relaxed: for `multi_component_agreement` specifically, `COMPONENT_2_*`
  and `COMPONENT_3_*` are optional groups (all-or-nothing per group — supplying `COMPONENT_2_NAME`
  without `COMPONENT_2_FEE` is still a validation error), while every other placeholder
  (`FIRM_NAME`, `DATE`, `CLIENT_NAME`, `SCOPE_OF_WORK`, `TOTAL_FEE`, `COMPONENT_1_*`) remains
  mandatory — every variant needs at least one real fee component.

## Relationships

```
FeeAgreementVariant (1) ──selected-by──> GeneratedDocument (N, one per generation attempt)
GeneratedDocument (1) ──produces──> one temp .docx file on disk (deleted after send/failure)
```

## Validation Rules

- `generate_fee_agreement`'s `values` argument MUST contain exactly the keys in
  `FeeAgreementVariant.placeholders` for the selected `variant_id` — no more, no fewer. A
  mismatch is a tool-call error surfaced back to the model (not a partial/best-effort fill),
  consistent with REQ-083-02's anti-hallucination requirement (the tool itself, not just prompt
  guidance, refuses to silently proceed with incomplete data).
- `verify_fee_agreement_document` MUST be called with the same `document_id` `generate_fee_agreement`
  returned — no re-verifying a stale/different file path supplied by the model from memory (same
  "always re-fetch fresh, same-turn state" principle bugfix-038's Group B reference tools use for
  Morning approval prompts).
- `send_document_response()` MUST reject any `GeneratedDocument` where `verified is not True`.
