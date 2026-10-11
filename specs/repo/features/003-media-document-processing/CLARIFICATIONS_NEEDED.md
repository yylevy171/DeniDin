# Feature 003: Clarifications Needed - Media & Document Processing

**Created**: January 22, 2026  
**Status**: PENDING - Awaiting Human Input

---

## Critical Questions (Blocking Implementation)

### 1. Green API Media Download Endpoint
**Question**: What is the exact Green API endpoint for downloading media files?

**Action Required**: Research Green API documentation for:
- Endpoint URL format for file downloads
- Authentication requirements
- File URL expiration time (how long are download URLs valid?)
- Rate limits on downloads

**Decision**: PENDING - Needs API documentation research

---

### 2. GPT-4 Vision Model Selection
**Question**: Which GPT-4 Vision model should we use?

**Options**:
- A) `gpt-4o` (latest, best performance)
- B) `gpt-4-vision-preview` (preview version)
- C) `gpt-4o-mini` (if it supports vision - need to verify)

**Context**: Affects cost, performance, and capabilities.

**Decision**: PENDING

---

### 3. PDF Extraction Library Choice
**Question**: Which PDF extraction library should we use?

**Options**:
- A) **pdfplumber** (recommended in spec)
  - Pros: Better text extraction, table support
  - Cons: Slightly slower
- B) **PyPDF2**
  - Pros: Lightweight, fast
  - Cons: Less accurate for complex PDFs
- C) **pymupdf (fitz)**
  - Pros: Very fast, handles complex layouts
  - Cons: GPL license (need to verify compatibility)

**Decision**: PENDING

---

### 4. OCR Library for Images
**Question**: Should we add OCR capability for text extraction from images?

**Context**: Use case from original 013 US3 - contract documents sent as images.

**Options**:
- A) **pytesseract** (local, free)
  - Requires Tesseract binary installation
  - Good accuracy for clear images
- B) **Azure Computer Vision API** (cloud, paid)
  - Very high accuracy
  - Additional API cost
- C) **Google Cloud Vision API** (cloud, paid)
  - Excellent accuracy
  - Additional API cost
- D) **No OCR** - rely only on GPT-4 Vision for text in images
  - GPT-4o can read text from images
  - May be sufficient without dedicated OCR

**Decision**: PENDING

---

### 5. File Storage Strategy
**Question**: How should downloaded media files be stored and managed?

**Proposed in Spec**:
- Storage path: `media/images/`, `media/documents/`, `media/temp/`
- Cleanup: Delete files after 24 hours
- Naming: `{chat_id}_{timestamp}_{filename}`

**Questions**:
- Should files be stored permanently or temporary only?
- Should we store original files or just extracted text in memory?
- What's the maximum storage budget (GB)?

**Decision**: PENDING

---

### 6. File Size Limits
**Question**: What are the maximum file size limits?

**Proposed**: 20MB max

**Considerations**:
- Green API may have its own limits (need to verify)
- Large PDFs may exceed token limits after extraction
- Balance between user convenience and resource usage

**Options**:
- A) 20MB (spec proposal)
- B) 10MB (more conservative)
- C) 50MB (generous, may hit token limits)
- D) Different limits per file type (10MB images, 25MB PDFs)

**Decision**: PENDING

---

### 7. Contract Document Processing Integration
**Question**: Should we integrate US3 (Contract Document Processing) from Feature 013 into this feature?

**Context**: Feature 013 US3 includes:
- Document extraction (PDF/Word/images)
- Contract summary generation
- Approval workflow (Godfather reviews summary)
- File storage with memory references
- Contract retrieval

**Options**:
- A) **Yes, integrate into Feature 003**
  - Makes Feature 003 comprehensive document processing feature
  - Includes business-specific workflow (contracts)
  - Single feature handles all document types
- B) **No, keep separate**
  - Feature 003 = generic document Q&A
  - Feature 013 US3 = contract-specific workflow
  - Two focused features

**Decision**: PENDING (user indicated decision 2.B - merge US3 into 003)

---

### 8. Approval Workflow for Contracts
**Question**: If we integrate US3, what should the approval workflow timeout be?

**Context**: After DeniDin extracts contract and generates summary, how long to wait for Godfather's approval?

**Options**:
- A) 5 minutes (quick turnaround expected)
- B) 1 hour (Godfather might be busy)
- C) 24 hours (very generous)
- D) No timeout (wait indefinitely)

**Decision**: PENDING (only if integrating US3)

---

### 9. Multi-page PDF Handling
**Question**: How should we handle very large PDFs (50+ pages)?

**Concerns**:
- May exceed token limits after extraction
- Processing time may be slow

**Options**:
- A) Extract all pages, chunk into multiple AI calls
- B) Extract first 20 pages only, warn user
- C) Ask user which pages to extract ("Which pages do you want me to focus on?")
- D) Summarize in chunks, then summarize the summaries

**Decision**: PENDING

---

### 10. Media Context Persistence
**Question**: Should extracted media content be stored in long-term memory?

**Scenarios**:
- User sends contract PDF → Should summary go into ChromaDB?
- User sends product image → Should description be stored?

**Options**:
- A) **Always store** - all extracted content goes to memory
- B) **Ask user** - "Should I remember this document for future reference?"
- C) **Session only** - keep in session context, don't persist
- D) **Smart decision** - Store contracts/important docs, not casual images

**Decision**: PENDING

---

### 11. Unsupported File Format Handling
**Question**: How to handle unsupported file formats (.xls, .ppt, .txt, .zip)?

**Options**:
- A) **Reject with error**: "Unsupported format. Please send PDF, Word, or image."
- B) **Best-effort extraction**: Try to extract text anyway
- C) **Store without processing**: Save file but mark as "manual review needed"
- D) **Expand support**: Add Excel, PowerPoint, TXT support in Phase 1

**Decision**: PENDING

---

### 12. File Naming Conflicts
**Question**: How to handle file naming collisions?

**Scenario**: Same client sends multiple files in same second.

**Proposed**: `{chat_id}_{timestamp}_{filename}`

**Options**:
- A) Add random suffix: `{chat_id}_{timestamp}_{random_uuid}_{filename}`
- B) Add counter: `{chat_id}_{timestamp}_{filename}_1.pdf`
- C) Use UUID as primary name: `{uuid}.pdf` (metadata stores original name)

**Decision**: PENDING

---

## Research Tasks

1. **Green API File Download**: Research exact endpoint, authentication, URL expiration
2. **GPT-4 Vision Pricing**: Calculate cost per image analysis
3. **PDF Library Comparison**: Benchmark pdfplumber vs PyPDF2 vs pymupdf for accuracy and speed
4. **OCR Evaluation**: Test pytesseract vs GPT-4o vision for text extraction from images
5. **File Storage Limits**: Determine Green API download size limits
6. **Token Limits**: Test how many PDF pages fit in GPT-4o context window

---

## Integration Questions (if merging US3)

### 13. Contract Summary Format
**Question**: What structure should contract summaries have?

**Required Fields**:
- Client name
- Contract type
- Amount/payment terms
- Key dates
- Deliverables

**Options**:
- A) Structured JSON metadata
- B) Markdown bullet points
- C) Natural language paragraph
- D) Both: Natural language + JSON metadata

**Decision**: PENDING

---

### 14. Contract Storage Location
**Question**: Where should contract files be permanently stored?

**Options**:
- A) `data/images/contracts_{timestamp}_{client}.{ext}` (per US3 spec)
- B) `media/documents/contracts/{client}/{timestamp}.{ext}`
- C) `contracts/{client_name}/{date}_{contract_type}.{ext}`

**Decision**: PENDING

---

### 15. Contract Retrieval Method
**Question**: How should contracts be re-sent when Godfather asks "Show me David's contract"?

**Green API Options**:
- A) `SendFileByUpload` - re-upload from disk
- B) `SendFileByUrl` - provide URL to file (requires public URL or local server)

**Which method does Green API support? Which should we use?**

**Decision**: PENDING - Research Green API capabilities

---

**Total Questions**: 15 critical questions + 6 research tasks  
**Blocking**: Implementation should not start until clarifications resolved  
**Next Step**: Human input required for all decisions

---

## Notes

- User indicated decision 2.B from original analysis: Merge US3 into Feature 003
- This makes Feature 003 comprehensive: Generic document Q&A + Contract-specific workflow
- Need to answer questions 7-15 to define contract workflow integration
