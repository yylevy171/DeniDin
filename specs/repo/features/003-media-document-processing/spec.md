# Feature Spec: Media & Document Processing

**Feature ID**: 003-media-document-processing  
**Priority**: P1 (High)  
**Status**: ✅ COMPLETE - Phase 7 Done (All Integration Tests Passing)  
**Created**: January 17, 2026  
**Updated**: January 27, 2026  
**Completed**: January 27, 2026  
**Decisions Log**: See `DECISIONS.md`  
**Phase 3 Implementation Decisions**: See § Phase 3 Implementation Choices below  
**Phase 4 Decision**: Merge document analysis INTO extractors (single AI call for text + analysis)  
**Phase 5 Clarification**: NO DocumentAnalyzer component - extractors already provide document_analysis

## ⚠️ CRITICAL REQUIREMENT: Language

**ALL BOT INTERACTIONS MUST BE IN THE USER'S LANGUAGE**

- **Default language: HEBREW** - If user language cannot be determined, use Hebrew
- Language detection from user's conversation history
- All messages MUST be translated:
  - Summaries and metadata reports
  - Error messages (file size, unsupported formats, processing failures)
  - Prompts (missing identification, corrections)
  - Contextual answers to user questions
- No English-only responses allowed
- Hebrew is the primary language for this bot

**Examples:**
- ✅ Correct: "הקובץ גדול מדי (מקסימום 10MB)"
- ❌ Wrong: "File too large (max 10MB)"
- ✅ Correct: "מצאתי חוזה. לקוח: פיטר אדם, סכום: 20,000 ש\"ח"
- ❌ Wrong: "Found contract. Client: Peter Adam, Amount: 20,000 NIS"

---

## Problem Statement

Currently, DeniDin only processes text messages. Users cannot send images, PDFs, or Word documents for the bot to analyze, extract content from, or use as context in conversations.

**Desired Capabilities:**
- 📷 **Images**: Analyze images, answer questions about them, extract text (OCR) - especially Hebrew text
- 📄 **PDFs**: Extract text (including Hebrew), summarize content, identify document type, extract metadata
- 📝 **Word Documents (DOCX)**: Parse content, summarize, use as context
- 📋 **Business Documents**: Process contracts, receipts, invoices, court resolutions with type-specific metadata extraction

**Key Business Use Cases (Integrated from Feature 013 US3):**
- **Contract Processing**: Extract client name, contract type, amounts, dates, deliverables
- **Receipt/Invoice Management**: Track expenses, vendor details, payment information
- **Court Document Tracking**: Case numbers, rulings, deadlines
- **Document Retrieval**: "Show me David's contract" → Re-send stored document

---

## Terminology Glossary

**Core Media Terms:**
- **media_type**: File category - one of: `image`, `pdf`, `docx`
- **document_type**: AI-detected business document classification - one of: `contract`, `receipt`, `invoice`, `court_resolution`, `generic`
- **caption**: WhatsApp message text sent WITH the media file (user's question/comment, NOT file metadata)
- **raw_text_path**: File path to extracted text stored as `.rawtext` file (UTF-8 encoded for Hebrew support)

**WhatsApp Identifiers:**
- **whatsapp_chat**: WhatsApp chat identifier (e.g., "1234567890@c.us" for individual chats)
- **session_id**: UUID identifier for a conversation session (links messages to sessions)

**Storage Paths:**
- **file_path**: Local storage location: `{data_root}/media/DD-{sender_phone}-{uuid}.{ext}`
- **STORAGE_BASE**: Root directory for all media files: `{data_root}/media/`
- **Filename Format**: `DD-{sender_phone}-{uuid}.{ext}` where uuid is randomly generated

**Processing States:**
- **extraction_quality**: Text extraction quality assessment - one of: `good`, `fair`, `poor`, `failed`
- **approval_status**: User approval state - one of: `pending`, `approved`, `rejected`

**File Format Identifiers:**
- **mime_type**: MIME type string (e.g., `image/jpeg`, `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
- **Supported formats**: JPG, JPEG, PNG (images); PDF (max 10 pages), DOCX (documents)
- **Unsupported formats**: GIF, TXT, XLS, PPT, ZIP (return error message to user)

**AI Model Names:**
- **VISION_MODEL**: From config `ai_vision_model` (default: `gpt-4o`) - Used for image and PDF page analysis
- **TEXT_MODEL**: From config `ai_model` (default: `gpt-4o-mini`) - Used for DOCX text processing and document analysis

**Metadata Field Types (Document-Specific):**
- **Contract metadata**: `client_name`, `contract_type`, `amount`, `start_date`, `end_date`, `deliverables`
- **Receipt metadata**: `merchant`, `date`, `total`, `items`, `payment_method`
- **Invoice metadata**: `vendor`, `invoice_number`, `amount`, `due_date`, `line_items`
- **Court Resolution metadata**: `case_number`, `parties`, `decision`, `deadline`

**Deprecated Terms:**
- **DEPRECATED: media_url** - Use `file_url` (Green API download URL) instead
- **DEPRECATED: document_metadata** - Use `extracted_metadata` for type-specific fields instead

---

## Use Cases

### Core Media Processing Use Cases

**UC1: Media Without Caption - Automatic Analysis**
- User sends media file (image/PDF/DOCX) with NO caption
- Bot automatically analyzes media type and extracts relevant metadata
- Bot sends summary with document type and extracted metadata
- Example: User sends contract image → Bot: "מצאתי חוזה. לקוח: פיטר אדם, סכום: 20,000 ש״ח, תאריך יעד: 29 בינואר 2026"

**UC2: Unsupported Media Type - Rejection**
- User sends unsupported media (audio, video) or unsupported file format (GIF, TXT, XLS, etc.)
- Bot rejects with clear error message explaining supported formats
- Error message in user's language (Hebrew default)
- Example: "אני לא יכול לעבד סוגי קבצים מסוג וידאו. אני תומך ב: תמונות (JPG, PNG), PDF (עד 10 עמודים), DOCX"

**UC3: Document Analysis + Contextual Q&A**

**UC3a: PDF Contract Analysis**
- User sends PDF contract (no caption)
- Bot extracts: client name (Peter Adam), amount (20,000 NIS), date due (Jan 29, 2026)
- Bot sends summary in Hebrew: "מצאתי חוזה. לקוח: פיטר אדם, סכום: 20,000 ש״ח, תאריך יעד: 29 בינואר 2026"
- User asks: "מתי הסכום מפיטר צריך להתקבל?" 
- Bot replies: "29 בינואר, בעוד 3 ימים"
- User asks: "כמה פיטר חייב?"
- Bot replies: "פיטר חייב 20,000 ש״ח לפי החוזה"

**UC3b: DOCX Document Analysis**
- User sends DOCX file
- Bot extracts text and metadata
- User asks questions about specific data points in document
- Bot answers using extracted metadata and context

**UC3c: Image Receipt Analysis**
- User sends receipt image
- Bot extracts: merchant, date, total, items
- User asks questions about receipt details
- Bot answers from extracted metadata

**UC4: User Correction of Metadata**
- User sends document with no caption
- Bot returns summary and metadata
- User corrects mistaken metadata (e.g., "הסכום הוא 25,000 לא 20,000")
- Bot accepts correction: "תודה על התיקון. עדכנתי את הסכום ל-25,000 ש״ח"
- Bot resends corrected summary and metadata
- User's correction becomes the authoritative data
- Future questions use corrected values

**UC5: Missing Client Identification - Bot Prompts**
- User sends document with no caption
- Bot analyzes and finds NO client/user identification in metadata
- Bot sends summary + metadata + prompt: "האם תרצה להוסיף פרטי זיהוי למסמך זה? (שם, טלפון, אימייל)"
- User can provide identification or skip
- If provided, bot adds to metadata and confirms

### Business Document Processing (Feature 013 US3 Integration)

**UC6: Contract Processing**
- User sends contract PDF/image
- AI extracts: client name, contract type, amount, dates, deliverables
- Bot sends summary as reply (no approval workflow)
- Stored for future retrieval

**UC7: Receipt Management**
- User sends receipt photo
- AI extracts: merchant, date, total, items
- Stored with metadata for expense tracking

**UC8: Invoice Processing**
- User sends invoice
- AI extracts: vendor, invoice #, amount, due date, line items
- Stored with metadata

**UC9: Court Document Tracking**
- User sends court resolution
- AI extracts: case #, parties, decision, deadlines
- Stored for legal tracking

**UC10: Document Retrieval**
- User asks "הראה לי את החוזה של דוד מהחודש שעבר"
- Bot searches conversation memory
- Finds and re-sends document using `SendFileByUpload`

---

## Requirements

### File Handling Requirements

**REQ-MEDIA-001**: File Size Validation
- Maximum file size: 10MB (10,485,760 bytes)
- Reject files exceeding limit with user-friendly error message
- Validate BEFORE downloading file from Green API

**REQ-MEDIA-002**: Format Support
- Supported image formats: JPG, JPEG, PNG (case-insensitive)
- Supported document formats: PDF (max 10 pages), DOCX
- Unsupported formats: GIF, TXT, XLS, PPT, ZIP
- Return error message for unsupported formats

**REQ-MEDIA-003**: PDF Page Limit
- Maximum 10 pages per PDF document
- Count pages after download, before processing
- Reject PDFs exceeding limit with error message

**REQ-MEDIA-004**: Storage Structure
- Base path: `{data_root}/media/` (flat structure, no date subdirectories)
- File naming: `DD-{sender_phone}-{uuid}.{ext}` where uuid is randomly generated
- UUID generation ensures collision prevention
- Permanent storage - no automatic deletion

**REQ-MEDIA-005**: File Naming
- Original file: `DD-{sender_phone}-{uuid}.{ext}` (uuid-based, includes sender identification)
- Extracted text: `DD-{sender_phone}-{uuid}.{ext}.rawtext`
- UTF-8 encoding for all `.rawtext` files (Hebrew support)
- UUID generated using Python's uuid.uuid4() for uniqueness

### Processing Requirements

**REQ-PROC-001**: Text Extraction Quality
- Hebrew text extraction required for all file types
- Mixed Hebrew/English support
- Quality assessment: `good`, `fair`, `poor`, `failed`
- Graceful degradation on low-quality extractions

**REQ-PROC-002**: Document Classification
- AI-determined document types: contract, receipt, invoice, court_resolution, generic
- Default to `generic` when uncertain (no confidence threshold)
- Multi-type scenarios: AI selects best-fit type

**REQ-PROC-003**: Metadata Extraction
- Type-specific metadata fields (all optional)
- Dynamic extraction based on document content
- Missing fields silently omitted from summary
- No required field validation

**REQ-PROC-004**: Metadata Correction Flow
- User can correct any extracted metadata after initial analysis
- Bot accepts corrections with confirmation message (in user's language)
- Corrected metadata overwrites AI-extracted values
- Future queries use corrected data as authoritative
- Example: User corrects amount from 20,000 to 25,000 → Bot updates and confirms

**REQ-PROC-005**: Missing Identification Prompts
- When document metadata lacks client/user identification (name, phone, email)
- Bot proactively asks if user wants to add identification
- Prompt in user's language (Hebrew default)
- User can provide info or skip
- If provided, added to document metadata

### AI Model Requirements

**REQ-AI-001**: Model Selection
- Images and PDFs: `ai_vision_model` from config (default: `gpt-4o`)
- DOCX documents: `ai_model` from config (default: `gpt-4o-mini`)
- Document analysis: `ai_model` from config

**REQ-AI-002**: Configuration Source
- All configuration from `config/config.json`
- NO environment variables (per CONSTITUTION.md §I)
- Model names, API keys in config file

**REQ-AI-003**: Language Detection and Response
- **CRITICAL**: ALL bot interactions MUST be in the user's language
- Language detection from user's message history
- **Default language: HEBREW** if language cannot be determined
- All messages (summaries, errors, prompts) MUST be translated
- Hebrew text in prompts and responses
- RTL direction handling in summaries
- Hebrew character encoding (UTF-8)

**REQ-AI-004**: Error Message Localization
- **CRITICAL**: ALL error messages MUST be in user's language (Hebrew default)
- Unsupported format errors in Hebrew: "אני לא יכול לעבד סוגי קבצים מסוג..."
- File size errors in Hebrew: "הקובץ גדול מדי (מקסימום 10MB)"
- Processing errors in Hebrew: "לא הצלחתי לעבד את הקובץ"
- If user language is English, provide English errors

### Integration Requirements

**REQ-INT-001**: Session Linkage
- Media messages linked to conversation sessions
- Summary added to conversation context
- Media metadata persists to long-term memory

**REQ-INT-002**: WhatsApp Message Handling
- Caption field contains user's message text (not file metadata)
- Media download via Green API `file_url`
- Error messages sent via WhatsApp response

**REQ-INT-003**: Retry Logic
- Maximum 1 retry for file downloads (2 total attempts)
- No retries for AI API calls (fail fast)
- User notified of all failures

### Error Handling Requirements

**REQ-ERR-001**: User-Friendly Messages
- All error messages in plain language
- Specific guidance for each error type
- No technical stack traces to users

**REQ-ERR-002**: Graceful Degradation
- Corrupted files: Return "unable to process" message
- Low-quality extraction: Include quality warnings in summary
- API failures: Clear error message, suggest retry

**REQ-ERR-003**: Edge Case Handling
- Zero-byte files: Reject with error
- Empty documents: Process with quality warning
- Unsupported formats: Clear format list in error

---

## Technical Design

### 1. WhatsApp Media Types

Green API supports these message types:
- `imageMessage` - Images (JPG/JPEG, PNG)
- `documentMessage` - Documents (PDF, DOCX)
- `videoMessage` - Videos (future enhancement)
- `audioMessage` - Voice notes (future enhancement)

**Supported Formats** (CHK039-041):
- **Images**: JPG, JPEG, PNG only (GIF not supported)
- **Documents**: PDF (max 10 pages), DOCX only
- **Not Supported**: GIF, TXT, XLS, PPT, ZIP (see error handling for messages)

### 2. Media Processing Flow

```
WhatsApp Message (with media)
    ↓
Validate file size (10MB max)
    ↓
Download media file from Green API
    ↓
Generate UUID for unique filename
    ↓
Store permanently: {data_root}/media/DD-{sender_phone}-{uuid}.{ext}
    ↓
Determine file type & validate format (JPG, PNG, PDF, DOCX only)
    ↓
Process based on type:
    - Image (JPG/PNG) → GPT-4o Vision API → Extract text
    - PDF → Convert pages to images → GPT-4o Vision API → Extract text (max 10 pages)
    - DOCX → python-docx library → Extract text → GPT-4o-mini
    ↓
Save raw extracted text: {filename}.rawtext
    ↓
AI analyzes content & detects document type (contract/receipt/invoice/court_resolution/generic)
    ↓
Generate summary (natural language + type-specific bullet points)
    ↓
Send summary to user for approval
    ↓
User provides feedback/clarification (no timeout - iterative refinement)
    ↓
Once approved: Add to conversation context
    (CHK112: Approval = informal satisfaction, any positive response like "looks good", "thanks", "ok")
    ↓
Store message with link to file location (standard session flow → long-term memory on expiry)
    ↓
Enable future retrieval: "Show me X's contract" → SendFileByUpload
```

### 3. Data Model Updates

```python
# src/models/message.py - Enhancement

class MediaAttachment:
    media_type: str          # 'image', 'pdf', 'docx'
    file_url: str            # Green API download URL
    file_path: str           # Local storage path: {data_root}/media/DD-{sender_phone}-{uuid}.{ext}
    raw_text_path: str       # Path to extracted .rawtext file
    mime_type: str           # 'image/jpeg', 'application/pdf', etc.
    file_size: int           # Size in bytes
    page_count: int          # Number of pages (PDFs only)
    caption: str             # WhatsApp message text sent with file (CHK111: user's question/comment, NOT file metadata)
    document_type: str       # AI-detected: 'contract', 'receipt', 'invoice', 'court', 'generic'
    extracted_metadata: Dict # Type-specific metadata (client name, amounts, dates, etc.)
    
class WhatsAppMessage:
    # Existing fields...
    media: Optional[MediaAttachment]  # NEW field
```

### 4. Processing Components

#### A. Image Processing (JPG, PNG)

**Technology**: OpenAI GPT-4o Vision API

**Decision**: Use `gpt-4o` with vision capabilities for all image analysis, including OCR for Hebrew text. No separate OCR library needed.

```python
# src/handlers/vision_handler.py

class VisionHandler:
    def __init__(self, config):
        self.vision_model = config.get('ai_vision_model', 'gpt-4o')
    
    def analyze_image(image_path: str, user_prompt: str = None) -> Dict:
        """
        Send image to GPT-4o Vision for analysis.
        Supports: JPG, PNG
        Returns: Extracted text + AI analysis
        """
        with open(image_path, 'rb') as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        prompt = user_prompt or "Extract all text from this image and describe what you see."
        
        response = openai.chat.completions.create(
            model=self.vision_model,  # From config: ai_vision_model
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url", 
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ]
        )
        return {
            "extracted_text": response.choices[0].message.content,
            "model_used": self.vision_model
        }
```

**Features**:
- Image description
- Hebrew OCR (via GPT-4o vision)
- Visual Q&A
- Document analysis from images

#### B. PDF Processing

**Technology**: GPT-4o Vision API (treat PDF pages as images)

**Decision**: Convert PDF pages to images, then use GPT-4o vision for text extraction. Handles both text-based and scanned PDFs uniformly. **Maximum 10 pages** - reject larger documents.

```python
# src/handlers/document_handler.py

class DocumentHandler:
    MAX_PDF_PAGES = 10
    
    def __init__(self, config, vision_handler):
        self.vision_handler = vision_handler
        self.vision_model = config.get('ai_vision_model', 'gpt-4o')
    
    def process_pdf(file_path: str) -> Dict:
        """
        Extract text from PDF by converting pages to images.
        Max 10 pages. Uses GPT-4o vision for OCR.
        """
        import fitz  # PyMuPDF for PDF to image conversion
        
        pdf = fitz.open(file_path)
        page_count = len(pdf)
        
        if page_count > self.MAX_PDF_PAGES:
            raise ValueError(
                f"PDF has {page_count} pages. Maximum is {self.MAX_PDF_PAGES}. "
                "Please send a shorter document or specify which pages to analyze."
            )
        
        extracted_text = ""
        for page_num in range(page_count):
            page = pdf[page_num]
            # Convert page to image
            pix = page.get_pixmap(dpi=150)
            image_bytes = pix.tobytes("png")
            
            # Send to GPT-4o vision
            page_text = self.vision_handler.analyze_image(
                image_bytes, 
                f"Extract all text from page {page_num + 1}. Preserve Hebrew characters."
            )
            extracted_text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
        
        return {
            "extracted_text": extracted_text,
            "page_count": page_count,
            "model_used": "gpt-4o-vision"
        }
```

**Features**:
- Handles text-based and scanned PDFs
- Hebrew text extraction
- Page-by-page processing (max 10 pages)
- Preserves text structure

#### C. Word Document Processing

**Technology**: python-docx + GPT-4o-mini

**Decision**: Extract text using python-docx library, then process with `ai_model` from config (default: `gpt-4o-mini`) for cost efficiency (text-only processing).

```python
def extract_docx_text(file_path: str, config: dict) -> Dict:
    """Extract text from DOCX file."""
    from docx import Document
    
    doc = Document(file_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    
    return {
        "extracted_text": text,
        "model_used": "python-docx-library",
        "processing_model": config.get('ai_model', 'gpt-4o-mini')  # From config
    }
```

**Features**:
- Text extraction (Hebrew supported)
- Lightweight processing
- Cost-effective (no vision API needed)

#### D. Document Type Detection & Metadata Extraction

**Technology**: ai_model from config (for DOCX) or ai_vision_model (for images/PDFs)

**Decision**: AI automatically detects document type and extracts type-specific metadata.

```python
def detect_document_type_and_extract_metadata(raw_text: str, config: dict, source_type: str) -> Dict:
    """
    AI analyzes document to determine type and extract relevant metadata.
    Supported types: contract, receipt, invoice, court, generic
    """
    # Use vision model for images/PDFs, text model for DOCX
    model = config.get('ai_vision_model') if source_type in ['image', 'pdf'] else config.get('ai_model')
    system_prompt = """
    Analyze this document and:
    1. Identify the document type: contract, receipt, invoice, court_resolution, or generic
    2. Extract relevant metadata based on type
    3. Return a natural language summary with bullet points for key details
    
    Document Type Metadata:
    - Contract: client_name, contract_type, amount, start_date, end_date, deliverables
    - Receipt: merchant, date, total_amount, payment_method, items
    - Invoice: vendor, invoice_number, invoice_date, due_date, total_amount, line_items
    - Court Resolution: case_number, date, parties, ruling, next_steps
    - Generic: summary only
    """
    
    response = openai.chat.completions.create(
        model=model,  # gpt-4o-mini or gpt-4o based on source
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_text}
        ]
    )
    
    # Parse AI response into structured format
    return {
        "document_type": "contract",  # AI-detected
        "summary": "Natural language summary paragraph...",
        "metadata_bullets": [
            "Client: David Cohen",
            "Contract Type: Service Agreement",
            "Amount: ₪50,000",
            "Duration: Jan 2026 - Dec 2026"
        ]
    }

**Document Type Detection Requirements** (CHK012-018):
- **Classification**: AI-determined, no explicit rules or examples needed
- **Fallback**: Default to "generic" type when uncertain (no confidence threshold)
- **Multi-type Scenarios**: AI determines best-fit type + user context can influence classification
- **Metadata Extraction**: All fields are optional, AI extracts what's available (dynamic per document)
- **Missing Fields**: Silently omit from summary (future: user-driven AI rules for required fields)
- **Ambiguous Documents**: Best-effort processing with quality warnings in summary (handwritten, partial forms, stamps/watermarks)
```

### 5. File Management

```python
# src/utils/media_manager.py

class MediaManager:
    STORAGE_BASE = Path(data_root) / "media"
    MAX_FILE_SIZE_MB = 10
    
    def download_and_store_media(file_url: str, mime_type: str, sender_phone: str) -> Dict:
        """
        Download media from Green API and store permanently.
        Storage: {data_root}/media/DD-{sender_phone}-{uuid}.{ext}
        
        Storage Requirements (CHK019-024):
        - UUID: Randomly generated uuid4() for collision prevention
        - Sender Identification: Phone number included for file organization
        - Atomicity: Not required (file and .rawtext saved independently)
        - Disk Space: No monitoring required (operational concern, not feature requirement)
        - Encoding: UTF-8 for .rawtext files (Hebrew support)
        - Duplicate Detection: None (same file sent twice = two separate storage entries)
        """
        import uuid
        file_uuid = uuid.uuid4()
        
        # Flat structure in media directory
        folder = self.STORAGE_BASE
        os.makedirs(folder, exist_ok=True)
        
        ext = self._get_extension(mime_type)
        filename = f"DD-{sender_phone}-{file_uuid}.{ext}"
        file_path = f"{folder}/{filename}"
        
        # Download file
        response = requests.get(file_url)
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        return {
            "file_path": file_path,
            "folder": folder,
            "filename": filename
        }
    
    def save_raw_text(folder: str, filename: str, raw_text: str):
        """Save extracted raw text alongside original file."""
        raw_text_path = f"{folder}/{filename}.rawtext"
        with open(raw_text_path, 'w', encoding='utf-8') as f:
            f.write(raw_text)
        return raw_text_path
        
    def validate_file_size(file_size: int) -> bool:
        """Check if file is within 10MB limit."""
        return file_size <= (self.MAX_FILE_SIZE_MB * 1024 * 1024)
```

**Storage Structure** (PERMANENT - no cleanup):
(CHK113: Permanent = forever until manual deletion feature is implemented)
(CHK114: Generic type = both fallback for low-confidence AND valid classification for misc documents)
```
{data_root}/media/
  ├── DD-972501234567-a3f4e8d2-1c9b-4e6a-8f2d-9b7c5e4d3a2b.pdf
  ├── DD-972501234567-a3f4e8d2-1c9b-4e6a-8f2d-9b7c5e4d3a2b.pdf.rawtext
  ├── DD-972509876543-f7e2d1c4-6b8a-4d9e-7f3c-2a1b8e5d4c3f.jpg
  ├── DD-972509876543-f7e2d1c4-6b8a-4d9e-7f3c-2a1b8e5d4c3f.jpg.rawtext
  ├── DD-972501234567-c9b8a7d6-5e4f-3c2b-1a9e-8d7c6b5a4f3e.docx
  └── DD-972501234567-c9b8a7d6-5e4f-3c2b-1a9e-8d7c6b5a4f3e.docx.rawtext
```

**Key Points**:
- Files stored **permanently** (no automatic deletion)
- Both original file AND extracted raw text saved
- Date-based organization
- Link to folder stored in message metadata for retrieval

### 6. Integration with Chat Sessions

Media processing integrates with existing conversation flow:

**For Images/PDFs (GPT-4o Vision)**:
```python
{
    "role": "user",
    "content": [
        {"type": "text", "text": user_message_or_caption},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    ]
}
```

**For Word Documents (GPT-4o-mini with extracted text)**:
```python
{
    "role": "user",
    "content": f"[Document uploaded: {filename}]\n\n{extracted_text}\n\nUser message: {user_caption}"
}
```

**Document Summary Approval Flow**:
1. Bot sends generated summary to user
2. User responds with feedback/approval (no timeout - iterative)
3. Bot refines summary based on feedback
4. Once user satisfied, summary becomes part of conversation context
5. Message stored with link to file location: `media.file_path`
6. Standard session flow: short-term → long-term memory on expiry

**Document Retrieval**:
When user asks "Show me David's contract":
1. AI searches conversation memory for mention of David + contract
2. Retrieves `file_path` from stored message metadata
3. Uses Green API `SendFileByUpload` to re-send file from disk

## Configuration

```json
{
  "media": {
    "enabled": true,
    "storage_path": "{data_root}/media/",
    "max_file_size_mb": 10,
    "max_pdf_pages": 10,
    "supported_formats": {
      "images": ["jpg", "jpeg", "png"],
      "documents": ["pdf", "docx"]
    },
    "permanent_storage": true
  },
  "ai_model": "gpt-4o-mini",
  "ai_vision_model": "gpt-4o",
  "document_analysis": {
    "auto_detect_type": true,
    "supported_types": ["contract", "receipt", "invoice", "court_resolution", "generic"]
  }
}
```

**Key Configuration Changes from Original Spec**:
- Reduced `max_file_size_mb` from 20 to 10
- Added `max_pdf_pages: 10`
- Removed `cleanup_after_hours` (permanent storage)
- Removed unsupported formats (GIF, TXT, WebP)
- Use existing `ai_model` and new `ai_vision_model` config parameters (not nested under ai_models)
- Added `document_analysis` configuration

## Dependencies

```python
# requirements.txt additions
PyMuPDF>=1.23.0           # PDF to image conversion (fitz)
python-docx>=1.0.0        # DOCX text extraction
Pillow>=10.0.0            # Image processing utilities
```

**Removed Dependencies** (from original spec):
- `pdfplumber` - Not needed (using vision-based PDF processing)
- `python-magic` - Not needed (simplified MIME type detection)

**Note**: No OCR library (tesseract) needed - GPT-4o vision handles OCR

## Implementation Plan

### Phase 1: Foundation & Image Support
- [ ] Update data models (MediaAttachment with new fields)
- [ ] Implement MediaManager (download, permanent storage, validation)
- [ ] Create storage folder structure ({data_root}/media/)
- [ ] Implement VisionHandler for GPT-4o vision integration
- [ ] Update WhatsApp handler to detect imageMessage
- [ ] Implement image processing: download → store → extract → save .rawtext
- [ ] Write tests for image processing
- [ ] Update config with vision settings

### Phase 2: PDF Support  
- [ ] Install PyMuPDF dependency
- [ ] Implement PDF page count validation (10 page max)
- [ ] Create PDF-to-image conversion in DocumentHandler
- [ ] Integrate with VisionHandler for page-by-page OCR
- [ ] Handle multi-page text aggregation
- [ ] Write tests for PDF processing
- [ ] Test with Hebrew PDFs

### Phase 3: DOCX Support
- [ ] Install python-docx dependency
- [ ] Add DOCX extraction to DocumentHandler
- [ ] Integrate with GPT-4o-mini for analysis
- [ ] Support Hebrew text extraction
- [ ] Write tests for DOCX processing

### Phase 4: Enhanced Extractors (Document Analysis Integration) ✅ COMPLETE
- [x] Create MediaExtractor base interface for consistent contract
- [x] Enhance ImageExtractor to return document analysis (type, summary, key points) in same AI call
- [x] Enhance PDFExtractor to aggregate document analysis from multiple pages
- [x] Add optional AI analysis to DOCXExtractor (analyze parameter, default=True)
- [x] Write interface contract tests (5 tests)
- [x] Write ImageExtractor Phase 4 tests (3 new tests, 10 total passing)
- [x] Write PDFExtractor Phase 4 tests (4 new tests, 10 total passing)
- [x] Write DOCXExtractor Phase 4 tests (5 new tests, 12 total passing)
- [x] Verify all 37 extractor tests pass together

**Implementation Summary**:
- MediaExtractor interface ensures consistent return format: {extracted_text, document_analysis, extraction_quality, warnings, model_used}
- ImageExtractor: Single Vision API call returns text + document analysis
- PDFExtractor: Aggregates per-page analyses (most common type, combined summaries, deduplicated key points)
- DOCXExtractor: Optional AI analysis after python-docx text extraction (analyze parameter)
- Cost savings: ~50% reduction vs separate analysis call
- 37 tests passing, 100% coverage on new code

**Commits**: 
- f0bd1c3: ImageExtractor enhancement
- 1f72d00: PDFExtractor enhancement
- 8899fcf: DOCXExtractor enhancement + base class fix

**Status**: Phase 4 complete. Ready for Phase 5 (Media Handler Orchestration).

### Phase 5: Media Handler Orchestration
**Goal**: Create MediaHandler to coordinate the complete media processing workflow.

**Note**: DocumentAnalyzer component is NOT needed - extractors already return document analysis in Phase 4.

- [ ] Create MediaHandler class to orchestrate workflow
- [ ] Integrate with MediaManager (download, validate, storage)
- [ ] Route to appropriate extractor based on file type
- [ ] Format user-friendly summary from extractor's document_analysis
- [ ] Create MediaAttachment model from results
- [ ] Handle all error cases (file size, format, download, extraction failures)
- [ ] Write 14 MediaHandler unit tests
- [ ] Verify end-to-end flow works

**Implementation**: MediaHandler receives file → validates → calls extractor → formats summary → returns response

### Phase 6: WhatsApp Integration
- [ ] Detect media messages in WhatsApp Handler
- [ ] Route media messages to Media Handler
- [ ] Send summary to user for approval
- [ ] Handle approval workflow (informal acceptance)
- [ ] Add approved media to conversation context
- [ ] Write WhatsApp media integration tests

### Phase 7: Document Retrieval (Future)
- [ ] Implement document search in conversation memory
- [ ] Integrate Green API SendFileByUpload for file re-sending
- [ ] Add natural language queries ("Show me David's contract")
- [ ] Handle multiple matches (ask user to clarify)
- [ ] Write tests for retrieval workflow

### Phase 8: Production Polish
- [ ] Add comprehensive error handling
- [ ] Performance optimization (async processing where possible)
- [ ] Documentation updates
- [ ] End-to-end testing
- [ ] Production deployment

## Message Flow Examples

### Example 1: Image Analysis
```
User: [sends sunset.jpg] "Where might this be?"
Bot: Downloads → Stores permanently → GPT-4o vision analysis
Bot: "This appears to be a sunset over a beach, possibly in a tropical location. 
      The palm trees and warm colors suggest somewhere near the equator..."
[Summary sent for approval]
User: "Perfect, thanks"
[Approved - added to conversation context]
```

### Example 2: Contract Processing (Feature 013 US3 Integration)
```
User: [sends contract.pdf - 5 pages]
Bot: Downloads → Stores in {data_root}/media/DD-972501234567-{uuid}.pdf
Bot: Converts PDF pages to images → GPT-4o vision extraction
Bot: Detects document type: "contract"
Bot: "I've analyzed this contract. Here's what I found:

This is a service agreement between you and David Cohen for web development services.

Key Details:
• Client: David Cohen
• Contract Type: Service Agreement  
• Amount: ₪50,000
• Start Date: January 15, 2026
• End Date: December 31, 2026
• Deliverables: E-commerce website with payment integration
• Payment Terms: 50% upfront, 50% on delivery

Does this look correct?"

User: "Yes, but the end date is actually January 31, 2027"
Bot: "Got it, I'll update that. Here's the corrected summary:
[Updated summary with Jan 31, 2027]
Is this better?"

User: "Perfect!"
[Approved - stored in conversation memory with link to file path]
```

### Example 3: Document Retrieval
```
User: "Show me David's contract"
Bot: Searches memory → Finds message with contract metadata
Bot: Retrieves file from {data_root}/media/DD-972501234567-{uuid}.pdf
Bot: [Re-sends PDF via SendFileByUpload]
Bot: "Here's David Cohen's service agreement from January 2026"
```

### Example 4: Receipt Processing
```
User: [sends receipt photo]
Bot: GPT-4o vision analysis → Detects type: "receipt"
Bot: "I've processed this receipt:

You spent ₪287 at Super-Pharm on January 22, 2026.

Key Details:
• Merchant: Super-Pharm Tel Aviv
• Date: January 22, 2026
• Total: ₪287.50
• Payment Method: Credit Card
• Main Items: Vitamins, skincare products, toiletries

Should I remember this for expense tracking?"
```

### Example 5: Multi-turn with PDF Context
```
User: [sends product_spec.pdf - 8 pages]
Bot: Processes → Generates summary → Sends for approval
User: "Looks good"
Bot: "Great! How can I help you with this document?"
User: "What are the technical requirements?"
Bot: [References extracted text from memory]
Bot: "Based on the document, the technical requirements are:
1. Python 3.11+
2. PostgreSQL database
3. Redis for caching
..."
```

## Error Handling

| Error | Handling |
|-------|----------|
| File too large (>10MB) | "This file is [X]MB. I can only process files up to 10MB. Please send a smaller file." |
| PDF too many pages (>10) | "This PDF has [X] pages. I can only process documents up to 10 pages. Please send a shorter document or specify which pages you need analyzed." |
| Unsupported format (.xls, .ppt, .txt, .zip) | "I can't process this file type yet. Please send one of these formats: PDF, Word (DOCX), JPG, or PNG images." |
| Download failed | Retry 1 time (max), then: "Unable to download this file. Please try sending it again." |
| Corrupted file | "Unable to process this file. It might be corrupted. Please try sending it again." |
| Vision API error | "I had trouble analyzing this image. Please try again or send a different format." |
| Empty document | "This document appears to be empty or I couldn't extract any text from it." |

## Testing Strategy

### Unit Tests
- Media type detection
- File download and storage
- Text extraction from PDF/DOCX
- File size validation
- Cleanup logic

### Integration Tests
- End-to-end image message processing
- End-to-end PDF processing
- Multi-turn conversation with document context
- Error handling for invalid files

### Manual Testing
1. Send various image types (JPG, PNG) - GIF should be rejected
2. Send PDFs of different sizes (1 page, 10 pages, 11 pages for boundary testing)
3. Send DOCX documents with formatting
4. Send unsupported file types (GIF, TXT, XLS, ZIP)
5. Send files exceeding size limit

## Success Metrics

- ✅ Accurately processes images with GPT-4 Vision
- ✅ Extracts text from 95%+ of PDFs successfully
- ✅ Handles DOCX documents correctly
- ✅ Maintains context across media messages
- ✅ Proper error messages for unsupported files
- ✅ 85%+ test coverage for media handlers

## Security Considerations

- Validate file types before processing
- Scan for malware (future enhancement)
- Limit file sizes to prevent DoS
- Clean up temporary files regularly
- Don't expose file paths to users
- Sanitize extracted text before sending to AI

## Cost Implications

**AI Model Usage**:
- **GPT-4o Vision** (images/PDFs): ~$0.01-0.03 per image/page
  - Used for: JPG, PNG images + PDF pages (max 10 pages)
  - Cost example: 10-page PDF = ~$0.10-0.30
- **GPT-4o-mini** (text processing): ~$0.0001 per request
  - Used for: DOCX analysis, document type detection
  - Cost example: DOCX analysis = ~$0.0001

**Storage**: 
- Permanent file storage (no cleanup)
- 10MB max per file
- Estimate: 100 documents/month = ~1GB/month (~$0.02/month on typical cloud storage)

**Bandwidth**: 
- Download files from Green API (free)
- Upload files via SendFileByUpload (Green API pricing)

**Total Estimated Cost**:
- Light usage (10 docs/month): ~$1-3/month
- Medium usage (50 docs/month): ~$5-15/month
- Heavy usage (200 docs/month): ~$20-60/month

**Cost Optimization Strategies**:
- Use gpt-4o-mini wherever possible (DOCX processing)
- 10-page PDF limit prevents excessive vision API costs
- 10MB file size limit controls bandwidth
- No unnecessary re-processing (stored .rawtext can be reused)

## Future Enhancements (Post-MVP)

- **Expand file type support**: Excel (.xlsx), PowerPoint (.pptx), plain text (.txt)
- **Increase PDF page limit**: Support >10 pages with chunked processing
- **Video processing**: Extract frames, transcribe audio
- **Audio/voice note transcription**: Whisper API integration
- **Image generation**: DALL-E integration for visual responses
- **Document comparison**: "Compare these 2 contracts and show differences"
- **Batch processing**: Handle multiple files in single message
- **Advanced OCR**: Fallback to Tesseract for edge cases
- **Table extraction**: Structured data from PDF/DOCX tables
- **Signature detection**: Identify if document is signed
- **Multi-language support**: Beyond Hebrew/English

---

## Technology Choices Documentation

### GPT-4o Vision for Images/PDFs
**Decision Date**: January 22, 2026  
**Rationale**:
- Excellent Hebrew OCR capabilities (no separate OCR needed)
- Handles both text-based and scanned documents uniformly
- Simpler architecture - one processing pipeline
- Better than traditional OCR for complex layouts

**Alternatives Considered**:
- pdfplumber + PyPDF2 (text extraction libraries): Limited to text-based PDFs, poor Hebrew support
- pytesseract (local OCR): Requires binary installation, less accurate than GPT-4o vision
- Cloud OCR (Azure/Google): Additional cost, redundant with GPT-4o capabilities

**Migration Path**: If vision API costs become prohibitive, fall back to pytesseract for simple documents

### GPT-4o-mini for Word Documents
**Decision Date**: January 22, 2026  
**Rationale**:
- Cost-effective for text-only processing
- Hebrew support confirmed
- No vision capabilities needed for DOCX (extracted as text)

**Alternatives Considered**:
- GPT-4o for everything: Unnecessarily expensive for text processing
- GPT-3.5-turbo: Lower quality, deprecated

### PyMuPDF (fitz) for PDF-to-Image Conversion
**Decision Date**: January 22, 2026  
**Rationale**:
- Fast PDF page rendering
- High-quality image output for vision API
- Well-maintained library

**Alternatives Considered**:
- pdf2image: Requires poppler binary dependency
- pdfplumber: Not designed for image conversion

**Note**: GPL license - verify compatibility with project licensing

### Permanent Storage (No Cleanup)
**Decision Date**: January 22, 2026  
**Rationale**:
- Business documents (contracts) need long-term retention
- Enables document retrieval feature
- Storage costs minimal (~$0.02/month for 100 docs)
- Audit trail for legal documents

**Alternatives Considered**:
- 24-hour cleanup (original spec): Breaks document retrieval feature
- Store summaries only: Loses original documents for verification

---

**Dependencies**: 
- Feature 002 (Chat Sessions) - Media integrated into conversation context
- **Feature 013 US3 MERGED** - Contract processing workflow integrated into this feature

**Next Steps**:
1. ✅ Review and approve spec (COMPLETE)
2. ✅ Resolve all clarifications (COMPLETE - see DECISIONS.md)
3. ✅ Create implementation plan (plan.md) following Spec Kit methodology (COMPLETE)
4. ✅ Create tasks.md with TDD workflow (COMPLETE)
5. ✅ Phase 3: Text Extraction (COMPLETE - PR #61 merged)
6. → Phase 4: Document Analysis (NEXT)

---

## Phase 3 Implementation Choices

**Completed**: January 24, 2026  
**PR**: #61 (merged to master)  
**Test Coverage**: 30 passing tests

### Architecture Decisions Made During Implementation

#### 1. In-Memory Media Processing (Media Model)

**Decision**: Create `Media` model for in-memory file handling instead of file path passing

**Rationale**:
- Decouples extractors from file I/O
- Enables easier testing with mock data
- Better memory management (10MB limit enforced)
- Cleaner API boundaries

**Implementation**:
```python
@dataclass
class Media:
    data: bytes           # Raw file content (max 10MB)
    mime_type: str        # MIME type validation
    filename: Optional[str]
    
    def to_base64() -> str       # For API calls
    def get_data_url() -> str    # data:mime;base64,... format
```

**Impact on Future Phases**:
- Phase 4 (Document Analysis): Will receive Media objects
- Phase 5 (Media Handler): Must create Media from downloads
- All extractors use consistent Media interface

---

#### 2. DeniDin Context Pattern

**Decision**: Pass DeniDin global context to extractors instead of individual dependencies

**Implementation**:
```python
class ImageExtractor:
    def __init__(self, denidin_context):
        self.ai_handler = denidin_context.ai_handler
        self.config = denidin_context.config
```

**Rationale**:
- Single source of truth for configuration
- Easier dependency injection
- Consistent with existing codebase patterns (AIHandler, SessionManager)
- Simplified testing (mock one object)

**Impact on Future Phases**:
- All new components should use DeniDin context
- Media Handler will be initialized with denidin_context
- Document Analyzer will use same pattern

---

#### 3. Constitution in User Prompt (NO System Message)

**Decision**: Prepend constitution to user prompt instead of using system message

**Rationale**:
- Project spent "hours" removing system message pattern
- Constitutional architecture enforced across all AI interactions
- User prompt = constitution + actual prompt

**Implementation**:
```python
def _vision_extract(self, media: Media, prompt: str):
    constitution = self.ai_handler._load_constitution()
    full_prompt = f"{constitution}\n\n{prompt}" if constitution else prompt
    # NO system message in messages array
```

**Impact on Future Phases**:
- Document Analyzer must follow same pattern
- Any AI calls must prepend constitution to user content
- System message should NEVER be used

---

#### 4. AI Self-Assessment for Quality

**Decision**: Let AI self-assess extraction quality instead of using arbitrary heuristics

**Original Approach** (rejected):
- Text length > 100 chars = "good"
- Text length 10-100 = "fair"  
- Text length < 10 = "poor"

**Final Approach**:
```python
prompt = (
    "Extract all text from this image. "
    "After extraction, assess your confidence level (high/medium/low) "
    "Format: TEXT:\n[text]\nCONFIDENCE: [high/medium/low]\nNOTES: [issues]"
)
```

**Rationale**:
- Text length doesn't indicate accuracy (short text can be perfect)
- AI knows when image is blurry, text is unclear, or confidence is low
- More accurate quality assessment
- Provides reasoning in NOTES field

**Impact on Future Phases**:
- Document analysis can use similar confidence self-assessment
- Quality warnings can reference AI's notes
- No need for arbitrary thresholds

---

#### 5. PDF Per-Page Array Results

**Decision**: Return per-page arrays instead of concatenated text

**Implementation**:
```python
{
    "extracted_text": ["page 1 text", "page 2 text", "page 3 text"],
    "extraction_quality": ["high", "medium", "high"],
    "warnings": [[], ["blur detected"], []],
    "model_used": "gpt-4o"  # Single value (same model)
}
```

**Rationale**:
- Preserves page-level granularity
- Caller can decide how to aggregate
- Quality issues can be traced to specific pages
- Easier debugging of multi-page PDFs

**Impact on Future Phases**:
- Document Analyzer will receive per-page data
- Media Handler can display page-specific warnings
- Future: Could enable "extract only pages 2-5" feature

---

#### 6. DOCX Uses python-docx Only (No AI)

**Decision**: DOCX extraction is deterministic (no AI model needed)

**Implementation**:
```python
class DOCXExtractor:
    def extract_text(self, media: Media) -> Dict:
        doc = Document(io.BytesIO(media.data))
        # Extract paragraphs and tables
        return {
            "extracted_text": str,      # Single string
            "warnings": List[str],
            "model_used": "python-docx"  # Library, not AI model
        }
```

**Rationale**:
- DOCX is structured XML (no OCR needed)
- python-docx provides clean text extraction
- No AI cost for simple text files
- Reserves AI for actual document analysis (Phase 4)

**Impact on Future Phases**:
- Phase 4 will use AI to ANALYZE extracted text (not extract it)
- Consistent with original decision (DOCX uses ai_model, not ai_vision_model)
- Cost optimization: Only pay for AI when needed

---

#### 7. No Hardcoded Model Names

**Decision**: Always use config values for model names

**Enforcement**:
```python
# ❌ WRONG
self.vision_model = "gpt-4o"

# ✅ CORRECT
self.vision_model = self.config.ai_vision_model
```

**Rationale**:
- User discovered hardcoded "gpt-4o" during implementation
- Config is single source of truth (CONSTITUTION.md §I)
- Enables easy model switching in production
- Testing can use different models

**Impact on Future Phases**:
- Document Analyzer must use `config.ai_model`
- Media Handler uses config for all AI calls
- NO hardcoded model references anywhere

---

#### 8. Test Data Strategy: Mocks Only

**Decision**: Use mocks for extractor tests, no real image fixtures

**Rationale**:
- Unit tests should test logic, not external APIs
- Real fixtures increase repository size
- Mocks enable testing edge cases (corrupted files, etc.)
- Faster test execution

**Implementation**:
```python
def create_docx_media(*paragraphs) -> Media:
    doc = Document()
    for para_text in paragraphs:
        doc.add_paragraph(para_text)
    # Return in-memory Media object
```

**Impact on Future Phases**:
- Integration tests will use real files
- Unit tests always mock Media objects
- Test fixtures in separate directory if needed

---

### Updated Technical Constraints

Based on Phase 3 implementation:

1. **All extractors MUST**:
   - Accept `Media` objects (not file paths)
   - Use DeniDin context for initialization
   - Prepend constitution to user prompts (no system messages)
   - Use config values for model names (no hardcoding)

2. **Future components MUST**:
   - Follow established patterns (DeniDin context, Media model)
   - No system messages (constitution in user prompt)
   - Use AI self-assessment where applicable
   - Mock external dependencies in unit tests

3. **Configuration Source**:
   - `ai_vision_model` for Image/PDF extractors
   - `ai_model` for Document Analyzer (Phase 4)
   - All config from `config/config.json` (NO environment variables)

---

### Files Created in Phase 3

1. `src/models/media.py` - Media model (10 tests)
2. `src/utils/extractors/image_extractor.py` - Image text extraction (7 tests)
3. `src/utils/extractors/pdf_extractor.py` - PDF page processing (6 tests)
4. `src/utils/extractors/docx_extractor.py` - DOCX text extraction (7 tests)
5. `src/utils/extractors/__init__.py` - Package init
6. `tests/unit/test_media.py` - Media model tests
7. `tests/unit/test_image_extractor.py` - Image extractor tests
8. `tests/unit/test_pdf_extractor.py` - PDF extractor tests
9. `tests/unit/test_docx_extractor.py` - DOCX extractor tests

**Total Lines Added**: 1,233 insertions  

---

## Phase 4 Implementation Decision: Enhanced Extractors

**Date**: January 24, 2026  
**Decision**: Merge document analysis into extractors (single AI call)

### Problem with Original Phase 4 Plan
Original plan had separate DocumentAnalyzer that would:
1. Receive extracted text from Phase 3 extractors
2. Make a SECOND AI call to analyze document type and extract metadata
3. Return analysis results

**Issues**:
- 🔴 **Inefficient**: Two AI calls per document (extraction, then analysis)
- 🔴 **Cost**: Double the API costs
- 🔴 **Quality**: Analysis on text-only loses visual context (layout, formatting, signatures)
- 🔴 **Latency**: Sequential API calls increase processing time

### New Approach: Enhanced Extractors

**For ImageExtractor & PDFExtractor** (already using Vision API):
- Enhance prompt to request text + document analysis in ONE call
- AI sees the actual image/PDF and provides richer analysis
- Return: `{extracted_text, document_analysis: {type, summary, key_points}}`

**For DOCXExtractor** (python-docx, no AI):
- Keep fast text-only extraction as default
- Add optional `analyze=True` parameter for AI analysis when needed
- Return: `{extracted_text, document_analysis: {...}}` (if analyze=True)

### Benefits
- ✅ **50% cost reduction**: One AI call instead of two
- ✅ **Faster**: Single API call, no waiting for sequential processing
- ✅ **Better quality**: AI analyzes visual document, not just text
- ✅ **Flexible**: DOCX can skip AI for simple text extraction

### Implementation Changes

**Enhanced Return Format**:
```python
{
    "extracted_text": str | List[str],  # Text content
    "document_analysis": {               # NEW - from same AI call
        "document_type": str,            # AI-determined: contract, receipt, invoice, court, generic
        "summary": str,                  # Natural language summary
        "key_points": List[str]          # Bullet points of important details
    },
    "extraction_quality": str,
    "warnings": List[str],
    "model_used": str
}
```

**Enhanced Prompt Example** (ImageExtractor):
```
Extract all text from this image AND analyze the document:

1. TEXT EXTRACTION:
   - Extract all text preserving layout and structure
   - Maintain RTL for Hebrew text
   
2. DOCUMENT ANALYSIS:
   - Identify document type: contract, receipt, invoice, court_resolution, or generic
   - Provide natural language summary
   - List key points (names, amounts, dates, etc.)

Return as JSON:
{
  "extracted_text": "...",
  "document_type": "contract",
  "summary": "Service agreement between...",
  "key_points": ["Client: David Cohen", "Amount: ₪50,000", ...]
}
```

### Phase 4 Tasks (Revised)

1. **TASK-014**: Write tests for enhanced ImageExtractor
2. **TASK-015**: Implement enhanced ImageExtractor (text + analysis)
3. **TASK-016**: Write tests for enhanced PDFExtractor
4. **TASK-017**: Implement enhanced PDFExtractor (text + analysis)
5. **TASK-018**: Write tests for enhanced DOCXExtractor (optional analysis)
6. **TASK-019**: Implement enhanced DOCXExtractor (optional analysis)
7. **TASK-020**: Update Media model to store document_analysis
8. **TASK-021**: Integration testing

**Original Phase 4** (Document Analyzer) - **CANCELLED**  
Merged into extractor enhancements for better efficiency and quality.
**Test Coverage**: 30/30 tests passing

---

## Phase 5 Architecture Clarification

**Date**: January 24, 2026  
**Clarification**: MediaHandler does NOT need DocumentAnalyzer component

### Background
The original plan.md (written before Phase 4) described a `DocumentAnalyzer` component that would:
1. Receive extracted text from extractors
2. Call AI to analyze document type and extract metadata  
3. Format user-facing summary

### Why DocumentAnalyzer is NOT Needed

**Phase 4 already provides everything**:
- Extractors return `document_analysis` with type, summary, and key_points
- Analysis happens in the SAME AI call as text extraction (cost-efficient)
- AI sees the actual visual document (better quality than text-only analysis)

### Simplified Phase 5 Architecture

**MediaHandler responsibilities**:
1. Coordinate workflow (download, validate, store, extract)
2. Route to appropriate extractor based on file type
3. Format extractor's `document_analysis` into user-friendly summary
4. Create MediaAttachment from results
5. Handle errors gracefully

**Example flow**:
```python
# MediaHandler.process_media_message()
extraction_result = self.image_extractor.extract_text(media)
# extraction_result already contains document_analysis!

summary = self._format_summary(extraction_result["document_analysis"])
# Just format the analysis that's already there

return {
    "success": True,
    "summary": summary,
    "document_metadata": extraction_result["document_analysis"]
}
```

**Benefits**:
- ✅ Simpler architecture - one less component
- ✅ No additional AI calls - extractors already did the work
- ✅ Consistent with Phase 4 design - use what's already built
- ✅ Easier testing - mock extractors, they return full results

---

