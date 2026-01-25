# Implementation Plan: Media & Document Processing

**Feature ID**: 003-media-document-processing  
**Created**: January 22, 2026  
**Updated**: January 25, 2026  
**Status**: Phase 6 Complete - WhatsApp Integration | Phase 7 Ready (Use Cases Revised)  
**Approach**: Test-Driven Development (TDD)  
**Dependencies**: Feature 002 (Chat Sessions)

---

## Overview

This plan implements media file processing for WhatsApp messages using a **TDD-first approach**. All code will be written following Red-Green-Refactor cycles.

**Core Philosophy**:
1. Write failing test first (Red)
2. Write minimal code to pass test (Green)
3. Refactor for quality (Refactor)
4. Repeat

**⚠️ CRITICAL REQUIREMENTS**:
- **Hebrew Language Default**: ALL bot responses MUST be in Hebrew unless user explicitly uses another language
- **Use Case Focus**: Implementation validates 10 real-world business scenarios (UC1-UC10)
- **Contextual Q&A**: Users can ask follow-up questions about document metadata (UC3 - Most Important)
- **Metadata Correction**: Users can correct bot errors, corrections become authoritative (UC4)
- **Proactive Prompts**: Bot asks for missing client identification (UC5)

---

## Architecture

### Component Hierarchy

```
src/
├── handlers/
│   ├── media_handler.py          # NEW: Orchestrates media processing flow
│   └── whatsapp_handler.py       # MODIFY: Add media message detection
├── models/
│   ├── message.py                # MODIFY: Add MediaAttachment class
│   └── document.py               # NEW: Document type & metadata models
├── utils/
│   ├── media_manager.py          # NEW: File download, storage, validation
│   ├── extractors/
│   │   ├── image_extractor.py    # NEW: GPT-4o vision for images
│   │   ├── pdf_extractor.py      # NEW: PDF → images → GPT-4o
│   │   └── docx_extractor.py     # NEW: python-docx + GPT-4o-mini
│   └── ai_client.py              # MODIFY: Add vision API support
└── config/
    └── media_config.py           # NEW: Media processing constants

tests/
├── unit/
│   ├── test_media_handler.py
│   ├── test_media_manager.py
│   ├── test_image_extractor.py
│   ├── test_pdf_extractor.py
│   ├── test_docx_extractor.py
│   └── test_document_models.py
└── integration/
    └── test_media_flow_integration.py
```

---

## TDD Implementation Phases

### Phase 1: Foundation & Models (TDD)

**Goal**: Data models and configuration with 100% test coverage

#### 1.1 Document Models (TDD)
**Test First**: `tests/unit/test_document_models.py`

```python
# Test cases to write FIRST:
- test_media_attachment_creation()
- test_media_attachment_validation()
- test_document_metadata_contract()
- test_document_metadata_receipt()
- test_document_metadata_invoice()
- test_document_metadata_court_resolution()
- test_document_metadata_generic()
- test_document_type_enum_values()
```

**Then Implement**: `src/models/document.py`

```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, List

class DocumentType(Enum):
    CONTRACT = "contract"
    RECEIPT = "receipt"
    INVOICE = "invoice"
    COURT_RESOLUTION = "court_resolution"
    GENERIC = "generic"

@dataclass
class DocumentMetadata:
    """Type-specific metadata extracted from documents."""
    document_type: DocumentType
    summary: str
    metadata_fields: Dict[str, str]  # Dynamic fields per document type
    confidence_notes: Optional[str] = None  # Quality warnings for ambiguous docs

@dataclass
class MediaAttachment:
    """Media file metadata for WhatsApp messages."""
    media_type: str          # 'image', 'pdf', 'docx'
    file_url: str            # Green API download URL
    file_path: str           # Local storage path
    raw_text_path: str       # Path to .rawtext file
    mime_type: str           # 'image/jpeg', 'application/pdf', etc.
    file_size: int           # Bytes
    page_count: Optional[int] = None  # PDFs only
    caption: str = ""        # WhatsApp message text (user's question/comment)
    
    def validate(self) -> None:
        """Validate attachment meets requirements."""
        # CHK001-002: File size validation
        max_size = 10 * 1024 * 1024  # 10MB
        if self.file_size > max_size:
            raise ValueError(f"File too large: {self.file_size} bytes (max {max_size})")
        
        # CHK003-004: Page count validation for PDFs
        if self.media_type == 'pdf' and self.page_count and self.page_count > 10:
            raise ValueError(f"PDF has {self.page_count} pages (max 10)")
```

**TDD Cycle**:
1. Write test for DocumentType enum → Run (fails) → Implement enum → Run (passes)
2. Write test for MediaAttachment creation → Run (fails) → Implement class → Run (passes)
3. Write test for file size validation → Run (fails) → Implement validate() → Run (passes)
4. Write test for PDF page count validation → Run (fails) → Enhance validate() → Run (passes)

#### 1.2 Media Configuration (TDD)
**Test First**: `tests/unit/test_media_config.py`

```python
# Test cases:
- test_supported_formats_defined()
- test_max_file_size_constant()
- test_max_pdf_pages_constant()
- test_dpi_setting_for_pdf_conversion()
- test_storage_base_path()
```

**Then Implement**: `src/config/media_config.py`

```python
from pathlib import Path

class MediaConfig:
    """Media processing configuration (CHK decisions integrated)."""
    
    # CHK039-041: Supported formats
    SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png']
    SUPPORTED_DOCUMENT_FORMATS = ['pdf', 'docx']
    
    # CHK002: File size limit
    MAX_FILE_SIZE_MB = 10
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    
    # CHK003-004: PDF page limits
    MAX_PDF_PAGES = 10
    
    # CHK011: DPI for PDF-to-image conversion
    PDF_DPI = 150  # Optimal for GPT-4o vision API
    
    # CHK042: Storage path
    STORAGE_BASE = Path("data/images")
    
    # AI Models
    VISION_MODEL = "gpt-4o"           # Images, PDFs
    TEXT_MODEL = "gpt-4o-mini"        # DOCX, document analysis
    
    # CHK048: Retry logic
    MAX_DOWNLOAD_RETRIES = 1
    
    # CHK023: File encoding
    RAWTEXT_ENCODING = "utf-8"  # Hebrew support
```

---

### Phase 2: File Management (TDD)

**Goal**: Download, store, validate files with 100% test coverage

#### 2.1 Media Manager (TDD)
**Test First**: `tests/unit/test_media_manager.py`

```python
# Test cases to write FIRST:
- test_download_file_success()
- test_download_file_retry_on_failure()  # CHK048: 1 retry max
- test_download_file_max_retries_exceeded()
- test_validate_file_size_under_limit()
- test_validate_file_size_over_limit()
- test_validate_file_size_exactly_10mb()  # CHK076: Boundary
- test_validate_supported_format_jpg()
- test_validate_supported_format_png()
- test_validate_supported_format_pdf()
- test_validate_supported_format_docx()
- test_validate_unsupported_format_gif()  # CHK040
- test_validate_unsupported_format_txt()  # CHK041
- test_create_storage_folder_utc_timestamp()  # CHK019
- test_storage_timestamp_microsecond_precision()  # CHK019
- test_save_file_to_storage()
- test_save_rawtext_utf8_encoding()  # CHK023
- test_save_rawtext_hebrew_content()
- test_handle_corrupted_file()  # CHK005
- test_handle_zero_byte_file()  # CHK075
```

**Then Implement**: `src/utils/media_manager.py`

```python
import os
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Tuple
from src.config.media_config import MediaConfig

class MediaManager:
    """Handles file download, storage, and validation."""
    
    def __init__(self):
        self.config = MediaConfig()
    
    def download_file(self, file_url: str) -> Tuple[bytes, bool]:
        """
        Download file from Green API with retry logic.
        
        Returns: (file_content, success)
        CHK048: Max 1 retry
        """
        for attempt in range(self.config.MAX_DOWNLOAD_RETRIES + 1):
            try:
                response = requests.get(file_url, timeout=30)
                response.raise_for_status()
                return (response.content, True)
            except requests.RequestException as e:
                if attempt == self.config.MAX_DOWNLOAD_RETRIES:
                    return (b"", False)
                continue
        return (b"", False)
    
    def validate_file_size(self, file_size: int) -> None:
        """CHK001-002, CHK076: Validate file size."""
        if file_size == 0:
            raise ValueError("File is empty (0 bytes)")  # CHK075
        if file_size > self.config.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File too large: {file_size} bytes "
                f"(max {self.config.MAX_FILE_SIZE_BYTES})"
            )
    
    def validate_format(self, filename: str, mime_type: str) -> str:
        """
        CHK039-041: Validate file format is supported.
        Returns: media_type ('image', 'pdf', 'docx')
        """
        ext = Path(filename).suffix.lower().lstrip('.')
        
        if ext in self.config.SUPPORTED_IMAGE_FORMATS:
            return 'image'
        elif ext == 'pdf':
            return 'pdf'
        elif ext == 'docx':
            return 'docx'
        else:
            raise ValueError(
                f"Unsupported format: {ext}. "
                f"Supported: JPG, PNG, PDF, DOCX"
            )
    
    def create_storage_path(self) -> Path:
        """
        CHK019: Create storage folder with UTC timestamp.
        Returns: Path like data/images/2026-01-22/image-1737561234.567890/
        """
        now_utc = datetime.now(timezone.utc)
        date_str = now_utc.strftime("%Y-%m-%d")
        timestamp = now_utc.timestamp()  # Microsecond precision
        
        folder = self.config.STORAGE_BASE / date_str / f"image-{timestamp}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder
    
    def save_file(self, content: bytes, folder: Path, filename: str) -> Path:
        """Save file to storage folder."""
        file_path = folder / filename
        with open(file_path, 'wb') as f:
            f.write(content)
        return file_path
    
    def save_rawtext(self, text: str, folder: Path, filename: str) -> Path:
        """
        CHK023: Save extracted text as UTF-8 .rawtext file.
        CHK006-010: Supports Hebrew content.
        """
        rawtext_path = folder / f"{filename}.rawtext"
        with open(rawtext_path, 'w', encoding=self.config.RAWTEXT_ENCODING) as f:
            f.write(text)
        return rawtext_path
```

**TDD Cycle**: Each test written before corresponding implementation method.

---

### Phase 3: Text Extraction (TDD)

**Goal**: Extract text from all file types with 100% test coverage

#### 3.1 Image Extractor (TDD)
**Test First**: `tests/unit/test_image_extractor.py`

```python
# Test cases:
- test_extract_text_from_simple_image()
- test_extract_text_from_hebrew_image()  # CHK006
- test_extract_mixed_hebrew_english()  # CHK008
- test_extract_with_layout_preservation()  # CHK010
- test_handle_empty_image()  # CHK078
- test_handle_garbled_text_extraction()  # CHK007
- test_handle_low_resolution_image()  # CHK083
- test_handle_extreme_aspect_ratio()  # CHK082
- test_handle_vision_api_error()
```

**Then Implement**: `src/utils/extractors/image_extractor.py`

```python
from typing import Dict
from src.utils.ai_client import AIClient

class ImageExtractor:
    """Extract text from images using GPT-4o vision."""
    
    def __init__(self, ai_client: AIClient):
        self.ai_client = ai_client
    
    def extract_text(self, image_path: str) -> Dict:
        """
        CHK006-011: Extract text from image with Hebrew support.
        
        Returns:
            {
                "extracted_text": str,
                "extraction_quality": str,  # "good", "fair", "poor"
                "warnings": List[str],      # Quality issues
                "model_used": "gpt-4o-vision"
            }
        """
        try:
            # CHK027: Use specific prompt (not just example)
            prompt = (
                "Extract all text from this image. "
                "Preserve layout, paragraphs, and line breaks. "
                "Maintain RTL direction for Hebrew text. "
                "If text is unclear or garbled, note it in your response."
            )
            
            response = self.ai_client.vision_extract(
                image_path=image_path,
                prompt=prompt,
                model="gpt-4o"
            )
            
            # CHK007: Handle garbled/failed extraction
            extracted_text = response.get("text", "")
            warnings = []
            
            if not extracted_text or len(extracted_text.strip()) < 10:
                warnings.append("Minimal or no text detected")
            
            return {
                "extracted_text": extracted_text,
                "extraction_quality": self._assess_quality(extracted_text),
                "warnings": warnings,
                "model_used": "gpt-4o"
            }
            
        except Exception as e:
            # CHK007: Fail gracefully
            return {
                "extracted_text": "",
                "extraction_quality": "failed",
                "warnings": [f"Extraction failed: {str(e)}"],
                "model_used": "gpt-4o"
            }
    
    def _assess_quality(self, text: str) -> str:
        """CHK018: Assess extraction quality for ambiguous documents."""
        if not text:
            return "poor"
        if len(text) < 50:
            return "fair"
        return "good"
```

#### 3.2 PDF Extractor (TDD)
**Test First**: `tests/unit/test_pdf_extractor.py`

```python
# Test cases:
- test_extract_text_from_single_page_pdf()
- test_extract_text_from_10_page_pdf()  # CHK077: Boundary
- test_reject_11_page_pdf()  # CHK004
- test_extract_hebrew_text_from_pdf()
- test_pdf_to_image_conversion_150dpi()  # CHK011
- test_extract_from_scanned_pdf()
- test_extract_from_text_based_pdf()
- test_handle_password_protected_pdf()  # CHK079
- test_handle_embedded_images_with_text()  # CHK080
- test_handle_corrupted_pdf()  # CHK005
```

**Then Implement**: `src/utils/extractors/pdf_extractor.py`

```python
import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, List
from src.config.media_config import MediaConfig
from src.utils.extractors.image_extractor import ImageExtractor

class PDFExtractor:
    """Extract text from PDFs via image conversion + GPT-4o vision."""
    
    def __init__(self, image_extractor: ImageExtractor):
        self.image_extractor = image_extractor
        self.config = MediaConfig()
    
    def extract_text(self, pdf_path: str) -> Dict:
        """
        CHK004, CHK077: Extract text from PDF (max 10 pages).
        CHK011: Convert at 150 DPI for optimal quality.
        
        Returns:
            {
                "extracted_text": str,
                "page_count": int,
                "warnings": List[str],
                "model_used": "gpt-4o-vision"
            }
        """
        warnings = []
        
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            
            # CHK004: Validate page count
            if page_count > self.config.MAX_PDF_PAGES:
                raise ValueError(
                    f"PDF has {page_count} pages (max {self.config.MAX_PDF_PAGES})"
                )
            
            # Convert each page to image and extract text
            all_text = []
            for page_num in range(page_count):
                page = doc[page_num]
                
                # CHK011: 150 DPI conversion
                pix = page.get_pixmap(dpi=self.config.PDF_DPI)
                img_path = f"/tmp/pdf_page_{page_num}.png"
                pix.save(img_path)
                
                # Extract text from page image
                result = self.image_extractor.extract_text(img_path)
                all_text.append(result["extracted_text"])
                warnings.extend(result.get("warnings", []))
                
                # Cleanup temp image
                Path(img_path).unlink(missing_ok=True)
            
            doc.close()
            
            return {
                "extracted_text": "\n\n".join(all_text),
                "page_count": page_count,
                "warnings": warnings,
                "model_used": "gpt-4o"
            }
            
        except Exception as e:
            # CHK005, CHK079: Handle corrupted/protected PDFs
            return {
                "extracted_text": "",
                "page_count": 0,
                "warnings": [f"PDF processing failed: {str(e)}"],
                "model_used": "gpt-4o"
            }
```

#### 3.3 DOCX Extractor (TDD)
**Test First**: `tests/unit/test_docx_extractor.py`

```python
# Test cases:
- test_extract_text_from_simple_docx()
- test_extract_hebrew_text_from_docx()
- test_extract_with_formatting_preserved()
- test_handle_track_changes_in_docx()  # CHK081
- test_handle_comments_in_docx()  # CHK081
- test_handle_corrupted_docx()  # CHK005
- test_handle_empty_docx()  # CHK078
```

**Then Implement**: `src/utils/extractors/docx_extractor.py`

```python
from docx import Document
from typing import Dict

class DOCXExtractor:
    """Extract text from DOCX files using python-docx."""
    
    def extract_text(self, docx_path: str) -> Dict:
        """
        Extract text from DOCX (text-only, no vision API needed).
        CHK006-010: Hebrew support via UTF-8.
        
        Returns:
            {
                "extracted_text": str,
                "warnings": List[str],
                "model_used": "python-docx-library"
            }
        """
        warnings = []
        
        try:
            doc = Document(docx_path)
            
            # Extract all paragraph text
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)
            
            extracted_text = "\n\n".join(paragraphs)
            
            # CHK078: Empty document handling
            if not extracted_text:
                warnings.append("Document appears empty")
            
            return {
                "extracted_text": extracted_text,
                "warnings": warnings,
                "model_used": "python-docx"
            }
            
        except Exception as e:
            # CHK005: Corrupted file handling
            return {
                "extracted_text": "",
                "warnings": [f"DOCX processing failed: {str(e)}"],
                "model_used": "python-docx"
            }
```

---

### Phase 4: Document Analysis (TDD)

**Goal**: AI-driven document type detection and metadata extraction

#### 4.1 Document Analyzer (TDD)
**Test First**: `tests/unit/test_document_analyzer.py`

```python
# Test cases:
- test_detect_contract_type()  # CHK012
- test_detect_receipt_type()
- test_detect_invoice_type()
- test_detect_court_resolution_type()
- test_detect_generic_type_fallback()  # CHK013, CHK114
- test_extract_contract_metadata()  # CHK016
- test_extract_receipt_metadata()
- test_extract_invoice_metadata()
- test_extract_court_metadata()
- test_handle_missing_metadata_fields()  # CHK017
- test_handle_multi_type_document()  # CHK015
- test_handle_ambiguous_document()  # CHK018
- test_no_confidence_threshold_required()  # CHK014
```

**Then Implement**: `src/utils/document_analyzer.py`

```python
from typing import Dict
from src.models.document import DocumentType, DocumentMetadata
from src.utils.ai_client import AIClient

class DocumentAnalyzer:
    """AI-driven document type detection and metadata extraction."""
    
    def __init__(self, ai_client: AIClient):
        self.ai_client = ai_client
    
    def analyze_document(self, raw_text: str, user_context: str = "") -> DocumentMetadata:
        """
        CHK012-018: Analyze document and extract type-specific metadata.
        
        Args:
            raw_text: Extracted text from document
            user_context: Caption/question from user (can influence classification)
        
        Returns: DocumentMetadata with type and extracted fields
        """
        # CHK026: Document the exact prompt as requirement
        system_prompt = """
        Analyze this document and:
        1. Identify document type: contract, receipt, invoice, court_resolution, or generic
        2. Extract relevant metadata based on type
        3. Generate natural language summary with bullet points
        
        Document Type Metadata (all fields optional):
        - contract: client_name, contract_type, amount, start_date, end_date, deliverables
        - receipt: merchant, date, total_amount, payment_method, items
        - invoice: vendor, invoice_number, invoice_date, due_date, total_amount, line_items
        - court_resolution: case_number, date, parties, ruling, next_steps
        - generic: summary only
        
        If document is ambiguous or has poor quality, note warnings in confidence_notes.
        CHK013: Default to "generic" when uncertain (no confidence threshold).
        CHK015: For multi-type documents, choose best-fit based on primary purpose.
        CHK017: Omit fields if not found (all fields are optional).
        """
        
        user_prompt = f"""
        Document text:
        {raw_text}
        
        User context: {user_context if user_context else "None provided"}
        """
        
        try:
            response = self.ai_client.chat_completion(
                model="gpt-4o-mini",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format="json"
            )
            
            # Parse AI response
            result = response.get("parsed_json", {})
            
            doc_type = DocumentType(result.get("document_type", "generic"))
            summary = result.get("summary", "")
            metadata_fields = result.get("metadata_fields", {})
            confidence_notes = result.get("confidence_notes")
            
            return DocumentMetadata(
                document_type=doc_type,
                summary=summary,
                metadata_fields=metadata_fields,
                confidence_notes=confidence_notes
            )
            
        except Exception as e:
            # CHK013: Fallback to generic on error
            return DocumentMetadata(
                document_type=DocumentType.GENERIC,
                summary="Document analysis failed",
                metadata_fields={},
                confidence_notes=f"Error: {str(e)}"
            )
    
    def format_summary_bullets(self, metadata: DocumentMetadata) -> str:
        """
        CHK036: Format metadata as bullet points for user display.
        CHK037: Include currency symbols (₪) for amounts.
        """
        bullets = [metadata.summary, ""]  # Summary + blank line
        
        for key, value in metadata.metadata_fields.items():
            # Format key as title case with spaces
            display_key = key.replace('_', ' ').title()
            bullets.append(f"• {display_key}: {value}")
        
        if metadata.confidence_notes:
            bullets.append(f"\nNote: {metadata.confidence_notes}")
        
        return "\n".join(bullets)
```

---

### Phase 5: Media Handler Orchestration (TDD)

**Goal**: Coordinate entire media processing workflow

#### 5.1 Media Handler (TDD)
**Test First**: `tests/unit/test_media_handler.py`

```python
# Test cases (integration-style unit tests):
- test_process_image_message_complete_flow()
- test_process_pdf_message_complete_flow()
- test_process_docx_message_complete_flow()
- test_handle_file_too_large_error()
- test_handle_unsupported_format_error()
- test_handle_download_failure_with_retry()
- test_handle_extraction_failure()
- test_handle_network_timeout()  # CHK064
- test_handle_malformed_url()  # CHK065
- test_handle_ai_api_rate_limit()  # CHK066
- test_handle_filesystem_error()  # CHK067
- test_approval_workflow_iterative_refinement()  # CHK030, CHK112
- test_message_without_caption()  # CHK060
- test_message_with_multi_sentence_caption()  # CHK061
```

**Then Implement**: `src/handlers/media_handler.py`

```python
from typing import Dict, Optional
from src.models.message import Message, MediaAttachment
from src.models.document import DocumentMetadata
from src.utils.media_manager import MediaManager
from src.utils.extractors.image_extractor import ImageExtractor
from src.utils.extractors.pdf_extractor import PDFExtractor
from src.utils.extractors.docx_extractor import DOCXExtractor
from src.utils.document_analyzer import DocumentAnalyzer

class MediaHandler:
    """Orchestrates complete media processing workflow."""
    
    def __init__(
        self,
        media_manager: MediaManager,
        image_extractor: ImageExtractor,
        pdf_extractor: PDFExtractor,
        docx_extractor: DOCXExtractor,
        document_analyzer: DocumentAnalyzer
    ):
        self.media_manager = media_manager
        self.image_extractor = image_extractor
        self.pdf_extractor = pdf_extractor
        self.docx_extractor = docx_extractor
        self.document_analyzer = document_analyzer
    
    def process_media_message(
        self,
        file_url: str,
        filename: str,
        mime_type: str,
        file_size: int,
        caption: str = ""
    ) -> Dict:
        """
        Complete media processing workflow following spec flow diagram.
        
        Returns:
            {
                "success": bool,
                "summary": str,              # User-facing summary
                "media_attachment": MediaAttachment,
                "document_metadata": DocumentMetadata,
                "error_message": Optional[str]
            }
        """
        try:
            # Step 1: Validate file size
            self.media_manager.validate_file_size(file_size)
            
            # Step 2: Download file (CHK048: 1 retry max)
            content, success = self.media_manager.download_file(file_url)
            if not success:
                return self._error_response(
                    "Unable to download this file. Please try sending it again."
                )
            
            # Step 3: Create storage folder (CHK019: UTC timestamps)
            storage_folder = self.media_manager.create_storage_path()
            
            # Step 4: Validate format and determine media type
            media_type = self.media_manager.validate_format(filename, mime_type)
            
            # Step 5: Save file
            file_path = self.media_manager.save_file(content, storage_folder, filename)
            
            # Step 6: Extract text based on file type
            extraction_result = self._extract_text(media_type, str(file_path))
            
            if not extraction_result["extracted_text"]:
                return self._error_response(
                    "Unable to extract text from this file. "
                    "It might be empty or corrupted."
                )
            
            # Step 7: Save raw text (CHK023: UTF-8 encoding)
            rawtext_path = self.media_manager.save_rawtext(
                extraction_result["extracted_text"],
                storage_folder,
                filename
            )
            
            # Step 8: Analyze document and detect type (CHK012-018)
            doc_metadata = self.document_analyzer.analyze_document(
                extraction_result["extracted_text"],
                user_context=caption
            )
            
            # Step 9: Generate user-facing summary
            summary = self.document_analyzer.format_summary_bullets(doc_metadata)
            
            # Step 10: Create MediaAttachment model
            attachment = MediaAttachment(
                media_type=media_type,
                file_url=file_url,
                file_path=str(file_path),
                raw_text_path=str(rawtext_path),
                mime_type=mime_type,
                file_size=file_size,
                page_count=extraction_result.get("page_count"),
                caption=caption
            )
            
            return {
                "success": True,
                "summary": summary,
                "media_attachment": attachment,
                "document_metadata": doc_metadata,
                "error_message": None
            }
            
        except ValueError as e:
            # Validation errors (file size, format, page count)
            return self._error_response(str(e))
        except Exception as e:
            # Unexpected errors
            return self._error_response(
                "Unable to process this file. Please try again or use a different format."
            )
    
    def _extract_text(self, media_type: str, file_path: str) -> Dict:
        """Route to appropriate extractor based on media type."""
        if media_type == 'image':
            return self.image_extractor.extract_text(file_path)
        elif media_type == 'pdf':
            return self.pdf_extractor.extract_text(file_path)
        elif media_type == 'docx':
            return self.docx_extractor.extract_text(file_path)
        else:
            raise ValueError(f"Unknown media type: {media_type}")
    
    def _error_response(self, message: str) -> Dict:
        """Standard error response format."""
        return {
            "success": False,
            "summary": "",
            "media_attachment": None,
            "document_metadata": None,
            "error_message": message
        }
```

**✅ Phase 5 Implementation Status (January 25, 2026)**

**Completed:**
- ✅ MediaHandler orchestration (14 tests passing)
- ✅ MediaFileManager for file operations (19 tests)
- ✅ Flat storage structure: `{data_root}/media/DD-{phone}-{uuid}.{ext}`
- ✅ Constitution/caption validation tests (8 tests)
- ✅ **BONUS**: Externalized AI prompts to `prompts/` directory
  - `prompts/docx_analysis.txt` - DOCX document analysis prompt
  - `prompts/image_analysis.txt` - Image text extraction + analysis prompt
  - Removed 35+ lines of hardcoded prompts from extractors

**Architecture Changes:**
- MediaManager → MediaFileManager (renamed for clarity)
- MediaHandler = orchestration layer (download → validate → extract → store)
- MediaFileManager = file operations only
- External prompt templates with dynamic context variables

**Test Results:**
- 373 tests passing (365 core + 8 constitution/caption)
- All extractors load prompts from external files
- Constitution architecture verified across all AI calls

**Pull Requests:**
- PR #66: Phase 5 MediaHandler + Prompt Externalization (merged)
- PR #67: Remove empty src/config directory (merged)

---

### Phase 6: WhatsApp Integration (TDD)

**Goal**: Integrate media processing into WhatsApp message flow

#### 6.1 WhatsApp Handler Enhancement (TDD)
**Test First**: `tests/unit/test_whatsapp_handler_media.py`

```python
# Test cases:
- test_detect_image_message()
- test_detect_document_message()
- test_ignore_video_message_future()
- test_ignore_audio_message_future()
- test_route_media_to_media_handler()
- test_send_summary_for_approval()
- test_handle_user_approval_informal()  # CHK112
- test_handle_user_rejection_refinement()
- test_add_approved_media_to_context()
```

**Then Implement**: Modifications to `src/handlers/whatsapp_handler.py`

```python
# Add to WhatsAppHandler class:

def handle_media_message(self, message_data: Dict) -> None:
    """
    Process WhatsApp media messages (images, documents).
    CHK111: Caption is WhatsApp message text, not file metadata.
    """
    message_type = message_data.get("type")
    
    if message_type not in ["imageMessage", "documentMessage"]:
        return  # Not a supported media type
    
    # Extract media information from Green API webhook
    file_url = message_data.get("downloadUrl")
    filename = message_data.get("fileName", "unknown")
    mime_type = message_data.get("mimeType", "")
    file_size = message_data.get("fileSize", 0)
    caption = message_data.get("caption", "")  # CHK111
    
    # Process media
    result = self.media_handler.process_media_message(
        file_url=file_url,
        filename=filename,
        mime_type=mime_type,
        file_size=file_size,
        caption=caption
    )
    
    if not result["success"]:
        # Send error message to user
        self.send_message(result["error_message"])
        return
    
    # Send summary for approval (CHK112: informal approval)
    approval_message = (
        f"I've processed this {result['document_metadata'].document_type.value}:\n\n"
        f"{result['summary']}\n\n"
        f"Should I remember this for future reference?"
    )
    self.send_message(approval_message)
    
    # Store pending approval state
    # (User's next message will be checked for approval phrases)
    self._store_pending_media(result["media_attachment"], result["document_metadata"])

def check_for_media_approval(self, user_message: str) -> bool:
    """
    CHK112: Check if user message indicates informal approval.
    Approval = any positive response: "yes", "looks good", "thanks", "ok", etc.
    """
    approval_phrases = [
        "yes", "yeah", "yep", "sure", "ok", "okay",
        "looks good", "perfect", "correct", "right",
        "thanks", "thank you", "great"
    ]
    
    user_lower = user_message.lower().strip()
    return any(phrase in user_lower for phrase in approval_phrases)
```

---

### Phase 7: Integration Testing (TDD)

**Goal**: End-to-end workflow validation for all 10 use cases

#### 7.1 Integration Tests
**Test**: `tests/integration/test_media_flow_integration.py`

```python
# Integration test cases (10 tests for UC1-UC10):

# UC1: Media without caption
- test_uc1_media_without_caption_automatic_analysis()
  # Send image/PDF/DOCX with no caption
  # Verify automatic metadata extraction
  # Verify Hebrew response

# UC2: Unsupported media rejection  
- test_uc2_unsupported_media_rejection()
  # Send audio/video/GIF/TXT
  # Verify rejection with Hebrew error
  # Verify supported formats listed

# UC3: Document analysis + contextual Q&A
- test_uc3a_pdf_contract_contextual_qa()
  # Send contract PDF
  # Extract: Peter Adam, 20,000 NIS, Jan 29
  # Ask: "מתי הסכום מפיטר צריך להתקבל?"
  # Verify: "29 בינואר, בעוד 3 ימים"
  # Ask: "כמה פיטר חייב?"
  # Verify: "20,000 ש\"ח לפי החוזה"

- test_uc3b_docx_document_qa()
  # Send DOCX, ask questions about metadata
  
- test_uc3c_image_receipt_qa()
  # Send receipt image, ask about items/total

# UC4: Metadata correction
- test_uc4_metadata_correction_flow()
  # Bot extracts metadata
  # User: "הסכום הוא 25,000 לא 20,000"
  # Verify bot accepts and updates
  # Verify future answers use corrected value

# UC5: Missing identification prompt
- test_uc5_missing_identification_prompt()
  # Document with no client info
  # Verify bot asks for identification in Hebrew
  # User provides name/phone
  # Verify added to metadata

# UC6-9: Business document processing
- test_uc6_contract_processing()
- test_uc7_receipt_management()
- test_uc8_invoice_processing()
- test_uc9_court_document_tracking()

# UC10: Document retrieval
- test_uc10_document_retrieval()
  # Store documents
  # Ask: "הראה לי את החוזה של דוד"
  # Verify correct document retrieved
```

#### 7.2 Language Requirement Testing
**CRITICAL**: All tests must verify Hebrew language responses

```python
def verify_hebrew_response(response_text):
    """Verify response is in Hebrew"""
    # Check for Hebrew characters
    assert any('\u05d0' <= c <= '\u05ea' for c in response_text)
    # Verify no English-only responses
    assert not response_text.strip().replace(' ', '').isascii()
```

**Language Test Requirements:**
- Every use case test MUST verify Hebrew responses
- Error messages MUST be in Hebrew (default language)
- All prompts to user MUST be in Hebrew
- Metadata summaries MUST be in Hebrew
- Only exception: If user explicitly uses English, respond in English

---

## Integration Contracts

### WhatsAppHandler ↔ MediaHandler Contract

**WhatsAppHandler MUST**:
- Call `media_handler.process_media(message)` for all messages with `media` field
- Pass complete `WhatsAppMessage` object with valid `media.file_url`
- Handle `MediaProcessingError` exceptions and send user-friendly error messages
- Not modify media files directly - delegate all processing to `MediaHandler`

**MediaHandler PROVIDES**:
- `process_media(message: WhatsAppMessage) -> DocumentMetadata` 
- Validates file format and size before processing
- Returns structured `DocumentMetadata` with `document_type`, `summary`, `metadata_fields`
- Raises `MediaProcessingError` with user-readable message on failure

**MediaHandler EXPECTS**:
- `message.media.file_url`: Valid Green API download URL (not None)
- `message.media.mime_type`: Valid MIME type string
- `message.whatsapp_chat`: Valid WhatsApp chat ID for session linkage
- `message.media.caption`: Optional string (user's message text with file)

---

### MediaManager ↔ Extractors Contract

**MediaManager MUST**:
- Call appropriate extractor based on `media_type` (ImageExtractor, PDFExtractor, DOCXExtractor)
- Pass absolute file path to extractor methods
- Validate file exists before calling extractor
- Save extractor output to `.rawtext` file with UTF-8 encoding

**Extractors PROVIDE**:
- `extract_text(file_path: str) -> Dict` with keys: `extracted_text`, `extraction_quality`, `warnings`, `model_used`
- `extraction_quality`: One of `good`, `fair`, `poor`, `failed`
- `warnings`: List of issues encountered (empty list if none)
- Graceful degradation - return partial results even on errors

**Extractors EXPECT**:
- `file_path`: Absolute path to existing file
- File format matches extractor type (ImageExtractor gets JPG/PNG, etc.)
- File size already validated by MediaManager
- File not corrupted (but must handle gracefully if it is)

---

### DocumentAnalyzer ↔ AI Handler Contract

**DocumentAnalyzer MUST**:
- Call `ai_handler.analyze_document(raw_text, document_hint)` with extracted text
- Pass `document_hint` if available from user's caption
- Parse AI response into structured `DocumentMetadata` object
- Default to `document_type='generic'` if AI cannot classify

**AI Handler PROVIDES**:
- `analyze_document(text: str, hint: str = None) -> Dict` with AI analysis
- Returns: `document_type`, `summary`, `metadata_fields`, `confidence_notes`
- Handles Hebrew text in prompts and responses
- Uses `TEXT_MODEL` (gpt-4o-mini) for cost efficiency

**AI Handler EXPECTS**:
- `text`: Non-empty string (DocumentAnalyzer validates this)
- `hint`: Optional context from user (e.g., "this is a contract")
- Reasonable text length (DocumentAnalyzer handles truncation if needed)

---

### MediaHandler ↔ SessionManager Contract

**MediaHandler MUST**:
- Call `session_manager.add_media_message(session_id, media_attachment, summary)` after processing
- Pass complete `MediaAttachment` object with all paths populated
- Add summary text to conversation context
- Link media to correct session using `whatsapp_chat` → `session_id` mapping

**SessionManager PROVIDES**:
- `add_media_message(session_id, media, summary) -> None`
- Stores media reference in session messages
- Includes summary in conversation history for AI context
- Persists media link to long-term memory on session expiry

**SessionManager EXPECTS**:
- `session_id`: Valid UUID for existing session
- `media.file_path`: Valid path that will remain accessible
- `summary`: Human-readable summary text (not None)

---

### MediaManager ↔ Storage System Contract

**MediaManager MUST**:
- Create storage directory structure: `data/images/{YYYY-MM-DD}/image-{timestamp}/`
- Use UTC timestamps for folder naming: `datetime.now(timezone.utc).timestamp()`
- Save original file with original extension
- Save extracted text as `{filename}.rawtext` with UTF-8 encoding
- Never delete files (permanent storage per CHK113)

**Storage System PROVIDES**:
- Persistent file storage in `data/images/` hierarchy
- Guaranteed availability of files for retrieval feature
- No automatic cleanup or expiration

**Storage System EXPECTS**:
- All paths created using `Path` objects for cross-platform compatibility
- UTF-8 encoding for all `.rawtext` files (Hebrew support)
- Unique folder names (timestamp with microsecond precision prevents collisions)

---

## Testing Strategy

### Test Coverage Goals
- **Unit Tests**: 100% coverage for all new modules
- **Integration Tests**: Cover all 10 use cases from spec
- **Edge Cases**: Dedicated tests for all CHK edge cases (CHK075-086)

### Test Data Requirements
- **Hebrew Test Documents**: PDF, DOCX, images with Hebrew text
- **Mixed Language**: Hebrew + English documents
- **Edge Cases**: 0-byte files, 10MB files, 10-page PDFs, corrupted files
- **Document Types**: Sample contracts, receipts, invoices, court resolutions

### TDD Workflow
```bash
# For each component:
1. Write test file first (all test cases)
2. Run tests → ALL FAIL (Red)
3. Implement minimal code to pass first test (Green)
4. Refactor if needed
5. Repeat for next test
6. When all tests pass → Component complete
```

---

## Dependencies

### New Python Packages
```bash
# Add to requirements.txt:
PyMuPDF>=1.23.0      # PDF processing (fitz)
python-docx>=1.0.0   # DOCX text extraction
Pillow>=10.0.0       # Image utilities
```

### Configuration Updates
```json
// config/config.json - Add media settings:
{
  "media": {
    "max_file_size_mb": 10,
    "max_pdf_pages": 10,
    "pdf_dpi": 150,
    "supported_formats": ["jpg", "jpeg", "png", "pdf", "docx"]
  }
}
```

---

## Implementation Order (TDD Phases)

1. **Phase 1**: Models + Config (Foundation) - 1-2 days
2. **Phase 2**: Media Manager (File handling) - 2-3 days
3. **Phase 3**: Extractors (Text extraction) - 3-4 days
4. **Phase 4**: Document Analyzer (AI analysis) - 2-3 days
5. **Phase 5**: Media Handler (Orchestration) - 2-3 days
6. **Phase 6**: WhatsApp Integration - 1-2 days ✅ COMPLETE
7. **Phase 7**: Integration Testing - 2-3 days

**Total Estimate**: 13-20 days (TDD process)

---

## Success Criteria

**Phase Completion:**
- [x] Phase 1-6: Complete (470 tests passing)
- [ ] Phase 7: Integration testing with 10 use cases

**Use Case Validation (Phase 7):**
- [ ] UC1: Media without caption → automatic analysis (Hebrew)
- [ ] UC2: Unsupported media → rejection with Hebrew errors
- [ ] UC3a: PDF contract → contextual Q&A (Peter Adam example)
- [ ] UC3b: DOCX → contextual Q&A
- [ ] UC3c: Image receipt → contextual Q&A  
- [ ] UC4: Metadata correction flow
- [ ] UC5: Missing identification → proactive prompts
- [ ] UC6-9: Business document processing
- [ ] UC10: Document retrieval

**Quality Gates:**
- [ ] All unit tests passing (100% coverage for new code)
- [ ] All integration tests passing (10 use cases)
- [ ] Hebrew text extraction validated with test dataset
- [ ] All CHK checklist requirements addressed in tests
- [ ] Error handling tested for all edge cases
- [ ] TDD workflow followed for all components
- [ ] **CRITICAL**: All bot messages in Hebrew (default language)
- [ ] **CRITICAL**: Contextual Q&A working (UC3 - most important)

---

## Rollout Plan

### Phase 1: Internal Testing
- Test with sample documents (Hebrew + English)
- Verify storage structure
- Validate error messages

### Phase 2: Limited Rollout
- Enable for single test user
- Monitor AI costs
- Collect feedback on summary quality

### Phase 3: Full Rollout
- Enable for all users
- Monitor storage growth
- Track processing success rates

---

## Notes

- **TDD is mandatory**: No implementation without tests first
- **CHK decisions integrated**: All 27 checklist decisions referenced in tests/code
- **Hebrew focus**: Every text extraction test must include Hebrew test case
- **Error handling**: Every component must have failure mode tests
- **Storage permanence**: CHK113 - Files stored forever (until deletion feature added)
