# Feature Specification: Net Hamishpat Scanning

**Feature Branch**: `081-net-hamishpat-scanning`  
**Created**: 2026-09-11
**Status**: Draft  
**Input**: User description: "Support נט המשפט scanning"

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- ✅ **`user-stories.md`** exists.

---

## User Stories Reference
See **`user-stories.md`** for full Given-When-Then criteria.
- **User Story 1**: Direct Case Scanning (P1)
- **User Story 2**: Automated Decision Parsing (P2)

### Edge Cases
- Net Hamishpat often has captchas, IP blocks, or requires smart-card authentication for deep case access.
- Court resolutions (החלטות) can be scanned PDFs with poor OCR quality.

## Requirements *(mandatory)*

### Functional Requirements
- **REQ-081-01**: System MUST integrate a mechanism to scan or query public data from Net Hamishpat using a case number.
- **REQ-081-02**: (If scraping is unviable due to CAPTCHA) System MUST provide enhanced PDF processing for Net Hamishpat generated documents, building on Feature 003's `MediaHandler`.
- **REQ-081-03**: AI MUST extract specific legal metadata (Judge name, ruling dates, parties involved, next hearing dates).
- **REQ-081-04**: System MUST trigger automatic reminders for future dates extracted from court documents.

### Key Entities
- **NetHamishpatTool**: An MCP tool or internal service for scraping/querying the court system.
- **LegalDocumentParser**: Specialized logic for court PDFs.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: Successfully parse 95% of provided Net Hamishpat resolution PDFs to extract the next hearing date and judge name.
- **SC-002**: If scraping is implemented, successfully retrieve case status by case number within 10 seconds.
