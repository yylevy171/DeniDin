# Feature Spec: Media & Document Processing

**Feature ID**: 003-media-document-processing  
**Priority**: P1 (High)  
**Status**: Planning  
**Created**: January 17, 2026

## Problem Statement

Currently, DeniDin only processes text messages. Users cannot send images, PDFs, or Word documents for the bot to analyze, extract content from, or use as context in conversations.

**Desired Capabilities:**
- 📷 **Images**: Analyze images, answer questions about them, extract text (OCR)
- 📄 **PDFs**: Extract text, summarize content, answer questions about documents
- 📝 **Word Documents (DOCX)**: Parse content, summarize, use as context

## Use Cases

1. **Image Analysis**: "What's in this photo?" → Bot describes the image
2. **Document Q&A**: Send PDF → "Summarize this document" → Bot extracts and summarizes
3. **Visual Problem Solving**: Send whiteboard photo → "Solve this math problem"
4. **Receipt/Invoice Processing**: Send photo → "How much did I spend?"
5. **Document Translation**: Send document → "Translate this to English"
6. **Multi-modal Research**: Send image + ask questions about it in context

## Technical Design

### 1. WhatsApp Media Types

Green API supports these message types:
- `imageMessage` - Images (JPG, PNG, GIF)
- `documentMessage` - Documents (PDF, DOCX, TXT, etc.)
- `videoMessage` - Videos (future enhancement)
- `audioMessage` - Voice notes (future enhancement)

### 2. Media Processing Flow

```
WhatsApp Message (with media)
    ↓
Download media file from Green API
    ↓
Determine file type
    ↓
Process based on type:
    - Image → GPT-4 Vision API
    - PDF → Extract text → GPT API
    - DOCX → Extract text → GPT API
    ↓
Add to conversation context
    ↓
Generate AI response
    ↓
Send to WhatsApp
```

### 3. Data Model Updates

```python
# src/models/message.py - Enhancement

class MediaAttachment:
    media_type: str          # 'image', 'document', 'pdf', 'docx'
    file_url: str            # Green API download URL
    file_path: str           # Local cached path (optional)
    mime_type: str           # 'image/jpeg', 'application/pdf', etc.
    file_size: int           # Size in bytes
    caption: str             # Optional caption from user
    
class WhatsAppMessage:
    # Existing fields...
    media: Optional[MediaAttachment]  # NEW field
```

### 4. Processing Components

#### A. Image Processing

**Technology**: OpenAI GPT-4 Vision API

```python
# src/handlers/vision_handler.py

class VisionHandler:
    def analyze_image(image_url: str, prompt: str) -> str:
        """
        Send image to GPT-4 Vision for analysis.
        Supports: JPG, PNG, GIF, WebP
        """
        response = openai.chat.completions.create(
            model="gpt-4o",  # or "gpt-4-vision-preview"
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]
        )
        return response.choices[0].message.content
```

**Features**:
- Image description
- Object detection
- Text extraction (OCR)
- Visual Q&A
- Image + text context in same message

#### B. PDF Processing

**Technology**: PyPDF2 or pdfplumber

```python
# src/handlers/document_handler.py

class DocumentHandler:
    def extract_pdf_text(file_path: str) -> str:
        """Extract text from PDF file."""
        import pdfplumber
        
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        return text
```

**Features**:
- Multi-page text extraction
- Table extraction (advanced)
- Image extraction from PDF (future)
- Metadata extraction (title, author, pages)

#### C. Word Document Processing

**Technology**: python-docx

```python
def extract_docx_text(file_path: str) -> str:
    """Extract text from DOCX file."""
    from docx import Document
    
    doc = Document(file_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text
```

**Features**:
- Text extraction
- Preserve basic formatting (headings, lists)
- Extract tables (advanced)

### 5. File Management

```python
# src/utils/media_manager.py

class MediaManager:
    def download_media(file_url: str, chat_id: str) -> str:
        """Download media from Green API, return local path."""
        
    def get_mime_type(file_path: str) -> str:
        """Detect MIME type of file."""
        
    def cleanup_old_files(max_age_hours: int):
        """Delete old cached media files."""
        
    def validate_file_size(file_size: int, max_mb: int) -> bool:
        """Check if file is within size limits."""
```

**Storage Structure**:
```
media/
  ├── images/
  │   └── {chat_id}_{timestamp}_{filename}
  ├── documents/
  │   └── {chat_id}_{timestamp}_{filename}
  └── temp/
```

### 6. Integration with Chat Sessions

Media becomes part of conversation context:

```python
{
    "role": "user",
    "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "..."}}
    ]
}
```

For documents, extracted text is added to context:

```python
{
    "role": "system",
    "content": f"User uploaded a PDF document. Content:\n{extracted_text}"
}
```

## Configuration

```json
{
  "media": {
    "enabled": true,
    "storage_path": "media/",
    "max_file_size_mb": 20,
    "cleanup_after_hours": 24,
    "supported_types": {
      "images": ["jpg", "jpeg", "png", "gif", "webp"],
      "documents": ["pdf", "docx", "txt"]
    }
  },
  "vision": {
    "enabled": true,
    "model": "gpt-4o",
    "max_detail": "high"
  }
}
```

## Dependencies

```python
# requirements.txt additions
pdfplumber>=0.10.0        # PDF text extraction
python-docx>=1.0.0        # DOCX processing
python-magic>=0.4.27      # MIME type detection
Pillow>=10.0.0           # Image processing utilities
```

## Implementation Plan

### Phase 1: Image Support
- [ ] Update WhatsApp handler to detect imageMessage
- [ ] Implement media download from Green API
- [ ] Create VisionHandler for GPT-4 Vision integration
- [ ] Add media to conversation context
- [ ] Write tests for image processing
- [ ] Update config with vision settings

### Phase 2: PDF Support
- [ ] Install pdfplumber dependency
- [ ] Create DocumentHandler for PDF extraction
- [ ] Implement text extraction and chunking (for large PDFs)
- [ ] Add document context to conversations
- [ ] Write tests for PDF processing
- [ ] Handle multi-page PDFs efficiently

### Phase 3: DOCX Support
- [ ] Install python-docx dependency
- [ ] Add DOCX extraction to DocumentHandler
- [ ] Support formatted text extraction
- [ ] Write tests for DOCX processing

### Phase 4: File Management
- [ ] Implement MediaManager for downloads
- [ ] Add file size validation
- [ ] Implement cleanup for old media files
- [ ] Add error handling for download failures

### Phase 5: Advanced Features
- [ ] OCR for images without text (Tesseract)
- [ ] Table extraction from PDFs
- [ ] Multiple images in single message
- [ ] Document comparison ("compare these 2 PDFs")

## Message Flow Examples

### Example 1: Image Analysis
```
User: [sends image of sunset] "Where might this be?"
Bot: Downloads image → Sends to GPT-4 Vision
Bot: "This appears to be a sunset over a beach, possibly in a tropical location. 
      The palm trees and warm colors suggest somewhere near the equator..."
```

### Example 2: PDF Summarization
```
User: [sends research_paper.pdf] "Summarize this"
Bot: Downloads PDF → Extracts 15 pages of text → Chunks appropriately
Bot: "This research paper discusses [summary of key findings]..."
```

### Example 3: Multi-turn with Context
```
User: [sends product_spec.pdf]
Bot: "I've received the document. How can I help you with it?"
User: "What are the technical requirements?"
Bot: Uses extracted text from PDF as context
Bot: "Based on the document, the technical requirements are: 1) ..."
```

## Error Handling

| Error | Handling |
|-------|----------|
| File too large | "File exceeds 20MB limit. Please send a smaller file." |
| Unsupported format | "I can only process images (JPG, PNG), PDFs, and Word docs." |
| Download failed | Retry 3 times, then notify user |
| Corrupted file | "Unable to process this file. Please try sending it again." |
| OCR failed | "I can see the image but couldn't extract any text from it." |

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
1. Send various image types (JPG, PNG, GIF)
2. Send PDFs of different sizes (1 page, 50 pages)
3. Send DOCX documents with formatting
4. Send unsupported file types
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

- **GPT-4 Vision**: More expensive than text-only (~$0.01-0.03 per image)
- **Storage**: Minimal cost for temporary file storage
- **Bandwidth**: Download files from Green API

**Mitigation**: 
- Set daily image analysis limits per user
- Implement caching for repeated image requests
- Auto-cleanup old files

## Future Enhancements

- Video processing (extract frames, transcribe audio)
- Audio/voice note transcription (Whisper API)
- Spreadsheet processing (Excel, CSV)
- PowerPoint/presentation processing
- Image generation (DALL-E integration)
- Document comparison and diff
- Batch processing multiple files

---

**Dependencies**: 
- Feature 002 (Chat Sessions) - Media should be part of conversation context

**Next Steps**:
1. Review and approve spec
2. Create feature branch `003-media-document-processing`
3. Implement Phase 1 (Image Support) first
4. Test with real images
5. Iterate to PDF and DOCX support
