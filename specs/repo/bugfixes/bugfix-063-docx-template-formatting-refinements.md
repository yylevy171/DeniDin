# Bugfix 063: Fee Agreement DOCX Template Layout & Formatting Refinements

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
