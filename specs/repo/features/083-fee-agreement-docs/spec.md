# Feature Specification: Fee Agreement Document Generation

**Feature Branch**: `feature/083-fee-agreement-docs`  
**Created**: 2026-09-12  
**Status**: Draft — Pending Review  
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

- **REQ-083-01: Template Repository**  
  The system MUST store a hardcoded base template (e.g., `assets/templates/fee_agreement_template.docx`). This template will contain distinct text placeholders (e.g., `{{CLIENT_NAME}}`, `{{FEE_AMOUNT}}`, `{{SCOPE_OF_WORK}}`, `{{DATE}}`).

- **REQ-083-02: Autonomous Data Gathering**  
  When triggered, the AI MUST analyze the placeholders required by the template. If fields are missing, the AI is free to autonomously decide how to retrieve them—either by checking the internal CRM/Ledger (if it's an existing client) or by halting the generation and explicitly asking the user for the missing details in the chat.

- **REQ-083-03: Document Generation Engine**  
  The system MUST provide a backend tool (exposed to the AI) that accepts a payload of key-value pairs (the extracted data). This tool MUST load the `.docx` template, replace the placeholders with the provided values, and save a temporary `.docx` output file. The implementation should rely on standard python libraries (like `python-docx`) to preserve the template's formatting.

- **REQ-083-04: Direct File Delivery via WhatsApp**  
  To optimize UX and reduce engineering overhead, the system MUST NOT rely on external file hosting or complex download portals. Instead, the WhatsApp integration (Green API) MUST be updated/utilized to support the `sendFileByUpload` endpoint. The newly generated `.docx` file MUST be uploaded and sent directly as a document attachment in the chat.

### Key Entities
- **DocTemplateEngine (Tool)**: AI-facing tool that accepts placeholder parameters and outputs a path to a generated `.docx` file.
- **WhatsApp API (`sendFileByUpload`)**: The delivery mechanism used by the agent to send the file back to the user.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: A user successfully requests an agreement, answers one clarifying question, and receives an editable `.docx` file in WhatsApp containing the exact details discussed.
- **SC-002**: The generated `.docx` file retains all original formatting (fonts, logos, margins) from the base template.
- **SC-003**: No permanent files are leaked or left cluttering the disk (temporary generated files must be cleaned up after dispatch).
