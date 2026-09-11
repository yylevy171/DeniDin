# Feature Specification: Fee Agreement Docs

**Feature Branch**: `083-fee-agreement-docs`  
**Created**: 2026-09-11
**Status**: Draft  
**Input**: User description: "Support creating "fee agreement" docs from template"

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- ✅ **`user-stories.md`** exists.

---

## User Stories Reference
See **`user-stories.md`** for full Given-When-Then criteria.
- **User Story 1**: Generate Fee Agreement from Template (P1)

### Edge Cases
- Handling Hebrew text alignment (RTL) when generating DOCX or PDF files.
- Missing required fields (AI must proactively ask for missing terms before generation).

## Requirements *(mandatory)*

### Functional Requirements
- **REQ-083-01**: System MUST maintain a standard DOCX template for Fee Agreements (הסכם שכר טרחה).
- **REQ-083-02**: System MUST expose an MCP tool (e.g., `generate_fee_agreement`) that the AI can call with structured parameters (Client Name, ID, Amount, Terms, Dates).
- **REQ-083-03**: The generation service (using `python-docx` or similar) MUST inject the AI-provided parameters into the template placeholders.
- **REQ-083-04**: The system MUST support sending the generated DOCX/PDF file back to the user via WhatsApp (`Green API`).
- **REQ-083-05**: The tool MUST correctly handle Hebrew RTL (Right-to-Left) formatting natively in the generated document.

### Key Entities
- **DocumentGenerator**: Service class handling the replacement of variables in a template.
- **FeeAgreementTemplate**: The source template file.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: Generated documents open without corruption in Microsoft Word and perfectly retain Hebrew RTL alignment.
- **SC-002**: The end-to-end flow from user request to receiving the file in WhatsApp takes under 15 seconds.
