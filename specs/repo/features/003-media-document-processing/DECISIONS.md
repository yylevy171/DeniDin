# Feature 003: Clarification Decisions

**Created**: January 22, 2026  
**Status**: RESOLVED - All Decisions Made  
**Session**: Interactive Q&A with Product Owner

---

## Decision Summary

All 13 critical questions have been answered and documented below. Feature is now ready to proceed to planning phase.

---

## Decisions Log

### 1. AI Model Selection ✅ DECIDED

**Question**: Which GPT models should we use for different file types?

**Decision**: 
- **Images (JPG/PNG)**: `gpt-4o` with vision capabilities
- **PDFs**: `gpt-4o` with vision (process pages as images)
- **Word Documents (DOCX)**: `gpt-4o-mini` (text extraction via library)

**Rationale**: Cost optimization - use expensive vision model only when needed, use cheaper mini for text-only processing. Hebrew language support confirmed for both models.

**Date**: January 22, 2026

---

### 2. PDF Processing Approach ✅ DECIDED

**Question**: How should we extract content from PDFs?

**Decision**: Use `gpt-4o` vision to read PDF pages as images (OCR via vision API)

**Rationale**: 
- Handles both text-based and scanned PDFs uniformly
- Works with complex Hebrew layouts
- No need for separate PDF extraction library
- Consistent processing pipeline with image handling

**Alternatives Rejected**:
- pdfplumber/PyPDF2 (text extraction) - less robust for scanned docs
- Hybrid approach - unnecessary complexity

**Date**: January 22, 2026

---

### 3. OCR Library ✅ DECIDED

**Question**: Do we need a dedicated OCR library for text extraction from images?

**Decision**: No separate OCR library - rely entirely on `gpt-4o` vision

**Rationale**:
- `gpt-4o` vision has excellent OCR capabilities for Hebrew
- Simpler architecture - one processing pipeline
- No additional binary dependencies (tesseract)
- Sufficient accuracy for use cases

**Alternatives Rejected**:
- pytesseract - unnecessary complexity, requires binary install
- Cloud OCR services - additional cost, redundant capability

**Date**: January 22, 2026

---

### 4. File Size Limits ✅ DECIDED

**Question**: What maximum file size should we accept?

**Decision**: **10MB maximum** for all file types

**Rationale**:
- Fast processing times
- Controlled API costs
- Prevents abuse
- Sufficient for typical contracts/receipts/invoices

**Alternatives Rejected**:
- 20MB - slower, higher costs
- 50MB - risk of very slow processing
- Different limits per type - unnecessary complexity

**Date**: January 22, 2026

---

### 5. File Storage Strategy ✅ DECIDED

**Question**: How should downloaded media files be stored and managed?

**Decision**: **Permanent storage** with structured folder hierarchy

**Storage Structure**:
```
data/images/{date}/image-{timestamp}/
  ├── DeniDin-image-{timestamp}.{pdf|docx|jpg|png}  # Original file
  └── DeniDin-image-{timestamp}.{ext}.rawtext        # Extracted raw text
```

**Details**:
- Store forever (no automatic deletion)
- Both original file AND raw extracted text saved
- Dated folder structure for organization
- Link to image folder stored in original WhatsApp message metadata

**Rationale**:
- Enables future retrieval ("Show me David's contract")
- Raw text backup for re-processing if needed
- Audit trail for business documents
- Date-based organization for easy browsing

**Note**: This overrides the original spec proposal of 24-hour cleanup.

**Date**: January 22, 2026

---

### 6. Memory Storage ✅ DECIDED

**Question**: Should extracted content be stored in ChromaDB long-term memory?

**Decision**: **Standard session flow** - no special memory handling

**Details**:
- Extracted content becomes part of conversation context
- Short-term memory during active session
- Moves to long-term memory when session expires (existing behavior)
- No immediate ChromaDB storage after approval

**Rationale**:
- Consistent with existing memory architecture
- No special-case logic needed
- Session expiry handles persistence automatically

**Date**: January 22, 2026

---

### 7. Approval Workflow Timeout ✅ DECIDED

**Question**: How long to wait for user approval of document summary?

**Decision**: **No timeout** - wait indefinitely for next user message

**Details**:
- DeniDin sends summary for approval
- User can refine/clarify at any point
- Approval is iterative, not a formal gate
- No automatic "timeout approved" behavior

**Rationale**:
- Approval is for quality refinement, not formal workflow
- User might need time to review complex contracts
- Natural conversation flow - user responds when ready

**Date**: January 22, 2026

---

### 8. Document Summary Format ✅ DECIDED

**Question**: What structure should document summaries have?

**Decision**: **Natural language paragraph + bullet points** (NO JSON)

**Format**:
```
[Natural language summary paragraph explaining the document]

Key Details:
• Field 1: Value
• Field 2: Value
• Field 3: Value
```

**Details**:
- Free-text paragraph first (human-readable)
- Bullet points for well-defined metadata
- Metadata fields vary by document type (see Decision 12)
- Easy to read in WhatsApp chat

**Rationale**:
- WhatsApp-friendly formatting
- Human-readable without technical parsing
- Flexible for different document types
- Easy for user to verify accuracy

**Alternatives Rejected**:
- JSON only - not user-friendly in chat
- Markdown tables - poor WhatsApp rendering
- Natural language only - harder to scan key facts

**Date**: January 22, 2026

---

### 9. Contract Storage Location ✅ DECIDED

**Question**: Should contracts be stored separately from other documents?

**Decision**: **No special storage** - all documents use same structure

**Details**:
- Contracts, receipts, invoices all use: `data/images/{date}/image-{timestamp}/`
- No `/contracts/` subfolder
- Document type identified by AI-extracted metadata, not folder structure

**Rationale**:
- Simpler architecture - one storage pattern
- Document type is data attribute, not folder convention
- Easier file management
- Date-based organization sufficient

**Date**: January 22, 2026

---

### 10. Large PDF Handling ✅ DECIDED

**Question**: How to handle PDFs exceeding reasonable page counts?

**Decision**: **10 pages maximum** - reject with error if exceeded

**Error Message**: "This PDF has [X] pages. I can only process documents up to 10 pages. Please send a shorter document or specify which pages you need analyzed."

**Rationale**:
- Controlled processing time
- Prevents token limit issues
- Encourages user to focus on relevant sections
- Clear user feedback

**Alternatives Rejected**:
- Process first 20 pages - confusing behavior
- Chunk and summarize - expensive, complex
- Ask user for page range - too many steps

**Date**: January 22, 2026

---

### 11. Unsupported File Formats ✅ DECIDED

**Question**: How to handle .xls, .ppt, .txt, .zip, etc.?

**Decision**: **Reject with clear error message**

**Supported Formats**:
- Images: JPG, PNG
- Documents: PDF, DOCX

**Error Message**: "I can't process this file type yet. Please send one of these formats: PDF, Word (DOCX), JPG, or PNG images."

**Rationale**:
- Clear scope for Phase 1
- Focus on primary use cases (contracts, receipts, invoices)
- Avoid complex Excel/PowerPoint parsing
- Can expand support in future phases

**Future Consideration**: Excel/PowerPoint support in Phase 2 if needed

**Date**: January 22, 2026

---

### 12. Document Type Detection ✅ DECIDED

**Question**: How to determine document type and what metadata to extract?

**Decision**: **AI auto-detection** with type-specific metadata extraction

**Document Types**:
1. **Contracts**
   - Client name
   - Contract type
   - Amount/payment terms
   - Key dates (start, end, milestones)
   - Deliverables
   
2. **Receipts**
   - Merchant/vendor
   - Date
   - Total amount
   - Payment method
   - Items purchased (if clear)
   
3. **Invoices**
   - Vendor/client
   - Invoice number
   - Invoice date
   - Due date
   - Total amount
   - Line items
   
4. **Court Resolutions**
   - Case number
   - Date
   - Parties involved
   - Decision/ruling
   - Next steps/deadlines

**Implementation**:
- AI analyzes document content
- Determines document type automatically
- Extracts relevant fields for that type
- Returns: Natural language summary + bullet points with type-specific metadata

**Rationale**:
- No manual classification needed
- Flexible - handles multiple business document types
- User-friendly - just send the document
- Extensible - easy to add new document types

**Note**: All documents get same treatment regardless of type - no special workflows. Contract detection is for metadata extraction only, not workflow branching.

**Date**: January 22, 2026

---

### 13. Document Retrieval Method ✅ DECIDED

**Question**: When user asks "Show me David's contract", how to re-send the stored file?

**Decision**: Use Green API **`SendFileByUpload`** method

**Implementation**:
- Retrieve file from storage: `data/images/{date}/image-{timestamp}/DeniDin-image-{timestamp}.{ext}`
- Re-upload to WhatsApp via Green API
- Include original caption/context if available

**Rationale**:
- Files stored locally on server
- No public URL infrastructure needed
- Simple, reliable file delivery
- Works with Green API architecture

**Alternatives Rejected**:
- SendFileByUrl - requires public URL or local server
- Send summary only - user wants original document

**Date**: January 22, 2026

---

## Implementation Readiness

✅ All critical questions answered  
✅ Technical approach clarified  
✅ Storage strategy defined  
✅ AI model selection finalized  
✅ Edge cases addressed  
✅ User experience flow confirmed  
✅ Requirements quality checklist validation complete (27 critical items)

**Next Step**: Proceed to planning phase (`plan.md` generation)

---

## Checklist Validation Decisions (January 22, 2026)

The following decisions were made during requirements quality checklist validation to resolve ambiguities and ensure spec completeness:

### Format Support (CHK039-041)
**Decision**: Supported formats are **JPG/JPEG, PNG, PDF, DOCX ONLY**
- GIF: Not supported (removed from spec)
- TXT: Not supported (clarified in error handling)
- Rationale: Focus on core business document formats, reduce testing surface area

### Document Type Consistency (CHK043)
**Decision**: Use `court_resolution` (not `court`) everywhere
- Rationale: More descriptive, consistent with spec §4.D implementation

### AI Model Usage (CHK044-046)
**Decision**: Confirmed consistent usage
- gpt-4o: Images (JPG/PNG) + PDFs
- gpt-4o-mini: DOCX + document analysis
- No conflicts found

### Retry Logic (CHK047-048)
**Decision**: **1 retry maximum** (not 3)
- Aligns with code CONST
- Spec updated to reflect actual implementation
- Rationale: Quick failure feedback, user can retry manually

### Hebrew Text Extraction Quality (CHK006-011)
**Decision**: Best-effort approach with clear failure handling
- No specific accuracy threshold (relies on GPT-4o vision quality)
- Fail gracefully with explanation if garbled/failed
- Primary language detection, best-effort for minority languages
- Test dataset with accuracy thresholds to be defined during testing phase
- Layout preservation: paragraphs, line breaks, spatial positioning
- 150 DPI for PDF-to-image (GPT-4o vision optimal resolution)

### Document Type Detection (CHK012-018)
**Decision**: AI-driven with flexible metadata
- Classification: AI-determined, no explicit rules needed
- Fallback: Default to "generic" when uncertain (no confidence threshold)
- Multi-type: AI determines best-fit + user context influence
- Metadata: All fields optional, dynamic per document
- Missing fields: Silently omitted (future: user-driven rules)
- Ambiguous docs: Best-effort with quality warnings

### Storage Requirements (CHK019-024)
**Decision**: UTC timestamps, no special handling
- Timestamps: UTC with microsecond precision
- Collision prevention: Timestamp uniqueness sufficient
- Atomicity: Not required (files saved independently)
- Disk space monitoring: Operational concern, not feature requirement
- Encoding: UTF-8 for .rawtext files (Hebrew support)
- Duplicate detection: None (same file twice = two storage entries)

### Terminology Clarifications (CHK111-114)
**Decisions**:
- **Caption** (CHK111): WhatsApp message text sent with file (user's question/comment), NOT file-embedded metadata
- **Approval** (CHK112): Informal satisfaction (any positive response: "looks good", "thanks", "ok")
- **Permanent Storage** (CHK113): Forever until manual deletion feature implemented
- **Generic Type** (CHK114): Both fallback for low-confidence AND valid classification for misc documents

---

## Notes

- User confirmed merging Feature 013 US3 (Contract Processing) into Feature 003
- All document types (contracts, receipts, invoices, court resolutions) treated uniformly
- No special approval workflow - approval is for summary refinement only
- Storage is permanent (no 24-hour cleanup as originally proposed in spec)
- Document type detection is automatic via AI content analysis
- Total checklist decisions: 27/125 items addressed (critical and high-priority conflicts resolved)
