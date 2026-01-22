# Feature 003: Media & Document Processing

## Status: ✅ READY FOR PLANNING

All clarifications resolved. Ready to proceed to planning phase (plan.md generation).

---

## Documents

### 📋 [spec.md](./spec.md)
**Complete feature specification with all clarified requirements**
- Problem statement & use cases (generic + business documents)
- Technical design (GPT-4o vision, GPT-4o-mini)
- Data models & processing components
- Storage strategy (permanent, date-based folders)
- Configuration & dependencies
- Implementation phases
- Cost analysis
- Technology choices documented

### ✅ [DECISIONS.md](./DECISIONS.md)
**All 13 critical questions answered**
1. AI Model Selection: gpt-4o (images/PDFs), gpt-4o-mini (DOCX)
2. PDF Processing: Vision-based (pages as images)
3. OCR Library: None (rely on GPT-4o vision)
4. File Size Limit: 10MB
5. Storage Strategy: Permanent with .rawtext files
6. Memory: Standard session flow
7. Approval Timeout: None (iterative refinement)
8. Summary Format: Natural language + bullet points
9. Storage Location: Unified (no special contract folders)
10. Large PDFs: 10 pages max, reject if exceeded
11. Unsupported Formats: Reject with clear error
12. Document Type: AI auto-detection with type-specific metadata
13. Retrieval: SendFileByUpload from disk

### 📝 [CLARIFICATIONS_NEEDED.md](./CLARIFICATIONS_NEEDED.md)
**Original questions (now answered in DECISIONS.md)**
- Research tasks identified
- Integration questions for contract workflow
- All marked as RESOLVED

---

## Feature Summary

**What This Feature Does:**
- Processes images (JPG, PNG), PDFs (max 10 pages), and Word documents (DOCX)
- Extracts text with Hebrew support using GPT-4o vision (images/PDFs) and python-docx (DOCX)
- Auto-detects document type: contracts, receipts, invoices, court resolutions
- Extracts type-specific metadata with AI
- Generates natural language summaries with bullet points
- Iterative approval workflow (no timeout)
- Permanent storage in `data/images/{date}/image-{timestamp}/` with .rawtext files
- Document retrieval: "Show me David's contract"

**Key Integrations:**
- ✅ Feature 013 US3 (Contract Processing) MERGED into this feature
- Uses existing session management (Feature 002)

**Technology Stack:**
- GPT-4o (vision) - images & PDFs
- GPT-4o-mini - DOCX processing & document analysis
- PyMuPDF (fitz) - PDF to image conversion
- python-docx - Word document text extraction
- Green API - file download & SendFileByUpload

**Constraints:**
- Max file size: 10MB
- Max PDF pages: 10
- Supported formats: JPG, PNG, PDF, DOCX
- Hebrew language optimized
- Permanent storage (no cleanup)

---

## Next Steps (Spec Kit Methodology)

1. ✅ **COMPLETED**: Clarifications resolved (DECISIONS.md)
2. ✅ **COMPLETED**: Spec updated with all decisions (spec.md)
3. **NEXT**: Generate `plan.md` using Spec Kit methodology
   - Technical context (language, dependencies, constraints)
   - Data model definitions (MediaAttachment, storage structure)
   - Integration contracts (component interactions)
   - Phase breakdown with validation checkpoints
   - Methodology & Constitution compliance check
4. **THEN**: Generate `tasks.md` with TDD workflow
   - Split by user story priority
   - Task A (write tests) → APPROVAL → Task B (implementation)
   - Dependency ordering with parallelization markers
5. **FINALLY**: Begin Phase 1 implementation (Foundation & Image Support)

---

## Questions for Product Owner

None - all questions answered in interactive session (January 22, 2026).

Ready to proceed! 🚀
