# Bugfix 063: Fee Agreement DOCX Template Layout & Formatting Refinements

**Status**: Done (fix implemented; all 7 billed acceptance tests for fee agreement generation passing; PR: #641)
**Branch**: `bugfix/063-docx-template-formatting-refinements`

## Problem
Based on real user feedback from production usage of Feature 083 (`083-fee-agreement-docs`), the generated Word document (`.docx`) fee agreement templates contain three formatting and layout defects that detract from a professional legal appearance:

1. **Upper Date Alignment**: The document date in the upper section is currently right-aligned with the rest of the Hebrew RTL text, rather than left-aligned at the top as customary in formal Israeli legal letterheads.
2. **Missing Definition Emphasis**: The party definitions in the header introduction section lack bold emphasis on the defined roles:
   - Needs: `להלן - *הלקוח*` (with **הלקוח** bolded)
   - Needs: `להלן - *עוה״ד*` (with **עוה״ד** bolded)
3. **Duplicate Acceptance & Signature Block**: The document generates a double/repeated "אני מאשר" (I approve) and signature section at the bottom, creating redundant and messy closing blocks.

## Scope of Fix
Modify the fee agreement template files and/or template generator logic (`apps/denidin-app/config/fee_agreement_templates/` and `DocTemplateEngine`):

1. **Date Layout**: Ensure the upper date paragraph is explicitly formatted with left alignment (`WD_ALIGN_PARAGRAPH.LEFT`).
2. **Typography**: Ensure run-level formatting in the parties paragraph applies bold weight specifically to the strings `"הלקוח"` and `"עוה״ד"`.
3. **Closing Block Dedup**: Ensure exactly one instance of the approval statement and signature table/line renders at the end of the document.

## User Acceptance Criteria (UAT)
- **UAT-1 (Date Alignment)**: When an agreement is generated, the top date paragraph has left alignment in the resulting `.docx`.
- **UAT-2 (Role Bold Text)**: In the opening parties block, the words **הלקוח** and **עוה״ד** appear in bold weight.
- **UAT-3 (Single Signature Section)**: The generated document concludes with exactly one closing approval statement and one signature line block.

## Update 2026-09-17/23: follow-up finding during UAT — date/title order, plus how UAT-3 was actually fixed

- **UAT-3 was fixed at the prompt-content layer, not in code**, per explicit instruction: the
  regression was the AI reproducing the opening parties line and closing signature block from
  curated reference examples that happened to include them (since those examples are real,
  complete letters), not a code-level duplication bug. The fix is in
  `config/fee_agreement_templates/examples/multi_component_agreement.json`'s `directive` field,
  telling the AI to ignore the opening/closing boilerplate in the reference examples since
  `render_fee_agreement_document` already injects the real header/signature block automatically.
  A code-level regex filter to strip AI-authored closing lines was tried first and explicitly
  rejected ("NO CODE for this! ... review the prompt.") and fully reverted.
- **A second, related defect surfaced during manual review after UAT-1/2/3 were otherwise
  fixed**: the upper date line was rendering *after* the title instead of before it, as in a
  real formal Israeli legal letterhead. Unlike UAT-3, this one genuinely required a code change
  — `DocTemplateEngine.render_free_text()`'s S1 header paragraph insertion order was swapped so
  the date paragraph is emitted before the title paragraph. New positive-order assertions were
  added to both `tests/unit/test_doc_template_engine.py` and
  `tests/billed/test_fee_agreement_generation_flow.py`, and
  `VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL`'s description (`fee_agreement_tools.py`) was updated so
  the AI's own self-verification step is aware of and can flag this ordering.
- All 7 billed acceptance tests in `tests/billed/test_fee_agreement_generation_flow.py` (each
  parametrized case run and approved individually) pass with both fixes in place.
