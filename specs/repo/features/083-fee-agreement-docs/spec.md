# Feature Specification: Fee Agreement Document Generation

**Feature Branch**: `feature/083-fee-agreement-docs`  
**Created**: 2026-09-12  
**Status**: Approved Specification — Ready for Implementation Planning  
**Input**: User description: "Creating a fee agreement document automatically based on user details and a well-known template. User asks -> AI asks clarifying info -> AI creates document and provides it back for download. Preference for docx."

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- ✅ **`user-stories.md`** exists and conforms to Given-When-Then standard.

---

## Executive Summary

Drafting boilerplate fee agreements is a repetitive administrative burden. This feature allows users to simply tell DeniDin to "draft an agreement" for a client. The AI will cross-reference the required fields against what the user provided (or what it knows from the ledger), ask clarifying questions if needed, populate a hardcoded Word (`.docx`) template, and deliver the final, editable file directly back to the user via WhatsApp.

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-083-01: Dynamic Template Variants (from Prod)**  
  Rather than a single hardcoded template, the system MUST support $N$ variants of fee agreements derived from the historical corpus of fee agreements currently existing in production media files. The AI MUST select the appropriate variant based on the context of the user's request (e.g., standard consultation vs. retainer vs. specific legal matter).

- **REQ-083-02: Autonomous Data Gathering & Anti-Hallucination Guardrail**  
  When triggered, the AI MUST analyze the placeholders required by the selected template variant. While it can check the CRM/Ledger for existing details, it is **strictly forbidden from hallucinating or guessing** any financial or legal parameters (e.g., fee amount, specific scope). If there is any ambiguity or missing data, it MUST pause generation and explicitly ask the user for clarification. It is always better to ask than to guess.

- **REQ-083-03: Document Generation Engine**  
  The system MUST provide a backend tool (exposed to the AI) that accepts a payload of key-value pairs (the extracted data). This tool MUST load the `.docx` template, replace the placeholders with the provided values, and save a temporary `.docx` output file. The implementation should rely on standard python libraries (like `python-docx`) to preserve the template's formatting.

- **REQ-083-04: AI Self-Verification (QA)**  
  Before releasing the document to the user, the AI MUST explicitly verify the generated `.docx` file. The model must check (via an internal verification tool or text-extraction loop) that the document strictly complies with the template structure and correctly incorporates all user-provided details. A document is only "Released" (sent) once the model itself approves it as correct.

- **REQ-083-05: Direct File Delivery via WhatsApp**  
  To optimize UX and reduce engineering overhead, the system MUST NOT rely on external file hosting or complex download portals. Instead, the WhatsApp integration (Green API) MUST be updated/utilized to support the `sendFileByUpload` endpoint. The newly generated `.docx` file MUST be uploaded and sent directly as a document attachment in the chat.

### Key Entities
- **DocTemplateEngine (Tool)**: AI-facing tool that accepts placeholder parameters and outputs a path to a generated `.docx` file.
- **WhatsApp API (`sendFileByUpload`)**: The delivery mechanism used by the agent to send the file back to the user.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: A user successfully requests an agreement, answers one clarifying question, and receives an editable `.docx` file in WhatsApp containing the exact details discussed.
- **SC-002**: The generated `.docx` file retains all original formatting (fonts, logos, margins) from the base template.
- **SC-003**: No permanent files are leaked or left cluttering the disk (temporary generated files must be cleaned up after dispatch).
