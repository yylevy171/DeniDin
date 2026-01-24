# Implementation Tasks: Media & Document Processing

**Feature ID**: 003-media-document-processing  
**Created**: January 22, 2026  
**Updated**: January 25, 2026  
**Status**: Phase 5 Complete (373 tests passing)  
**Approach**: Test-Driven Development (TDD)  
**Estimated Duration**: 13-20 days

---

## How to Use This File

Each task follows the **Red-Green-Refactor** TDD cycle:
1. **Red**: Write failing test first
2. **Green**: Write minimal code to pass test  
3. **Refactor**: Clean up code while keeping tests green

**CRITICAL - Human Approval Gates (per METHODOLOGY.md §VI)**:
- ⚠️ **TEST tasks MUST be reviewed and approved by human before proceeding to CODE task**
- ⚠️ **Once approved, tests are IMMUTABLE without explicit human re-approval**
- This ensures alignment on acceptance criteria before implementation begins

**Task Format**:
- **Task ID**: Unique identifier
- **Phase**: Which implementation phase
- **Type**: TEST or CODE
- **Dependencies**: Must complete these tasks first
- **Estimate**: Time in hours
- **CHK References**: Checklist requirements addressed

**Workflow**:
- Mark task as `[ ]` (not started), `[~]` (in progress), `[x]` (complete)
- Always complete TEST task before corresponding CODE task
- **PAUSE after TEST task completion for human review/approval**
- Run all tests after each CODE task completion

---

## Git/GitHub Workflow for Every Task

**IMPORTANT**: Follow this workflow for EVERY task or phase completion:

### Step-by-Step Git Process

```bash
# 1. CREATE FEATURE BRANCH (at start of phase/task group)
git checkout -b feature/003-media-processing-phaseX
# Example: feature/003-media-processing-phase1

# 2. WORK ON TASKS (write tests, implement code)
# ... complete TASK-00X, TASK-00Y, etc. ...

# 3. STAGE CHANGES (selective staging)
git add denidin-app/src/path/to/new_file.py
git add denidin-app/tests/unit/test_new_file.py
git add denidin-app/requirements.txt
git add specs/in-progress/003-media-document-processing/

# 4. COMMIT WITH DETAILED MESSAGE
git commit -m "feat: Phase X - Description (CHK###-###)

Implements Feature 003 Phase X using TDD:
- Key change 1
- Key change 2
- Test results: X tests, Y% coverage

CHK Requirements: CHK###-###
Tasks: TASK-00X to TASK-00Y complete"

# 5. PUSH TO REMOTE
git push -u origin feature/003-media-processing-phaseX

# 6. CREATE PULL REQUEST
gh pr create --title "Feature 003 Phase X: Description" --body "## Summary
Brief description

## Tasks Completed
- TASK-00X: Description
- TASK-00Y: Description

## Test Results
- X tests passing
- Y% coverage

## CHK Requirements
- CHK###: Description

## Next Steps
- Next phase tasks" --base master

# 7. MERGE PR (via GitHub web OR locally)
# Via web: Click "Merge pull request" button
# OR locally:
git checkout master
git merge --no-ff feature/003-media-processing-phaseX -m "Merge pull request #X

Feature 003 Phase X: Description"
git push origin master

# 8. CLEAN UP BRANCHES
git branch -d feature/003-media-processing-phaseX
```

### Commit Message Template

```
feat: Phase X - Short Description (CHK###-###)

Detailed description of what was implemented:
- Bullet point 1
- Bullet point 2
- Test results and coverage

Implementation:
- File 1: What it does
- File 2: What it does

Testing:
- test_file.py: X tests (Y% coverage)

CHK Requirements Validated:
- CHK###-###: Description

Tasks Completed: TASK-00X through TASK-00Y (Phase X: A/B = C%)
```

### When to Commit

**Per Phase**: Create one feature branch and one PR per phase
- Phase 1: 5 tasks → 1 branch, 1 commit, 1 PR
- Phase 2: 2 tasks → 1 branch, 1 commit, 1 PR
- etc.

**Guidelines**:
- Commit when all tasks in a phase are complete
- All tests must pass before committing
- 100% coverage achieved before committing
- Code quality verified (pylint, mypy) before committing

---

## Phase 1: Foundation & Models (Days 1-2)

### TASK-001: Setup Test Infrastructure
- **Type**: CODE
- **Dependencies**: None
- **Estimate**: 2h
- **Status**: [ ]

**Actions**:
```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Create test structure
mkdir -p denidin-app/tests/unit
mkdir -p denidin-app/tests/integration
mkdir -p denidin-app/tests/fixtures

# Verify conftest.py works
pytest --collect-only
```

**Acceptance**:
- Test discovery works
- Logging configured for tests
- Coverage reporting enabled

---

### TASK-002: Create Document Models Test File
- **Type**: TEST
- **Dependencies**: TASK-001
- **Estimate**: 3h
- **Status**: [ ]
- **CHK References**: CHK001-004 (validation), CHK012-018 (document types)

**File**: `denidin-app/tests/unit/test_document_models.py`

**Test Cases to Write** (all should FAIL initially):
```python
import pytest
from src.models.document import DocumentType, DocumentMetadata, MediaAttachment

class TestDocumentType:
    def test_document_type_enum_has_all_types(self):
        """CHK012: Five document types defined."""
        assert DocumentType.CONTRACT.value == "contract"
        assert DocumentType.RECEIPT.value == "receipt"
        assert DocumentType.INVOICE.value == "invoice"
        assert DocumentType.COURT_RESOLUTION.value == "court_resolution"
        assert DocumentType.GENERIC.value == "generic"

class TestMediaAttachment:
    def test_create_media_attachment_with_required_fields(self):
        """Basic creation test."""
        attachment = MediaAttachment(
            media_type='image',
            file_url='https://example.com/file.jpg',
            file_path='/data/media/DD-972501234567-a3f4e8d2-1c9b-4e6a-8f2d-9b7c5e4d3a2b.jpg',
            raw_text_path='/data/media/DD-972501234567-a3f4e8d2-1c9b-4e6a-8f2d-9b7c5e4d3a2b.jpg.rawtext',
            mime_type='image/jpeg',
            file_size=1024
        )
        assert attachment.media_type == 'image'
    
    def test_validate_file_size_under_limit(self):
        """CHK001-002: File size validation."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf',
            raw_text_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf.rawtext',
            mime_type='application/pdf',
            file_size=5 * 1024 * 1024  # 5MB
        )
        attachment.validate()  # Should not raise
    
    def test_validate_file_size_over_limit(self):
        """CHK001-002: Reject files > 10MB."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf',
            raw_text_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf.rawtext',
            mime_type='application/pdf',
            file_size=15 * 1024 * 1024  # 15MB
        )
        with pytest.raises(ValueError, match="File too large"):
            attachment.validate()
    
    def test_validate_file_size_exactly_10mb(self):
        """CHK076: Boundary condition - exactly 10MB should pass."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf',
            raw_text_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf.rawtext',
            mime_type='application/pdf',
            file_size=10 * 1024 * 1024  # Exactly 10MB
        )
        attachment.validate()  # Should not raise
    
    def test_validate_pdf_page_count_within_limit(self):
        """CHK003-004: PDF page count validation."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf',
            raw_text_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf.rawtext',
            mime_type='application/pdf',
            file_size=1024,
            page_count=8
        )
        attachment.validate()  # Should not raise
    
    def test_validate_pdf_exactly_10_pages(self):
        """CHK077: Boundary - exactly 10 pages should pass."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf',
            raw_text_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf.rawtext',
            mime_type='application/pdf',
            file_size=1024,
            page_count=10
        )
        attachment.validate()  # Should not raise
    
    def test_validate_pdf_over_10_pages(self):
        """CHK004: Reject PDFs > 10 pages."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf',
            raw_text_path='/data/media/DD-972501234567-b2c3d4e5-6f7a-8b9c-0d1e-2f3a4b5c6d7e.pdf.rawtext',
            mime_type='application/pdf',
            file_size=1024,
            page_count=11
        )
        with pytest.raises(ValueError, match="pages \\(max 10\\)"):
            attachment.validate()
    
    def test_caption_field_is_whatsapp_message_text(self):
        """CHK111: Caption is WhatsApp message text, not file metadata."""
        attachment = MediaAttachment(
            media_type='image',
            file_url='https://example.com/img.jpg',
            file_path='/data/media/DD-972501234567-c1d2e3f4-5a6b-7c8d-9e0f-1a2b3c4d5e6f.jpg',
            raw_text_path='/data/media/DD-972501234567-c1d2e3f4-5a6b-7c8d-9e0f-1a2b3c4d5e6f.jpg.rawtext',
            mime_type='image/jpeg',
            file_size=1024,
            caption="What's in this photo?"
        )
        assert attachment.caption == "What's in this photo?"

class TestDocumentMetadata:
    def test_create_contract_metadata(self):
        """CHK016: Contract metadata structure."""
        metadata = DocumentMetadata(
            document_type=DocumentType.CONTRACT,
            summary="Service agreement with client",
            metadata_fields={
                "client_name": "David Cohen",
                "contract_type": "Service Agreement",
                "amount": "₪50,000"
            }
        )
        assert metadata.document_type == DocumentType.CONTRACT
        assert "David Cohen" in metadata.metadata_fields["client_name"]
    
    def test_create_generic_metadata_as_fallback(self):
        """CHK013, CHK114: Generic type as fallback."""
        metadata = DocumentMetadata(
            document_type=DocumentType.GENERIC,
            summary="Miscellaneous document",
            metadata_fields={}
        )
        assert metadata.document_type == DocumentType.GENERIC
    
    def test_metadata_fields_are_optional(self):
        """CHK017: All metadata fields are optional."""
        metadata = DocumentMetadata(
            document_type=DocumentType.RECEIPT,
            summary="Receipt with minimal info",
            metadata_fields={}  # Empty - all fields optional
        )
        assert metadata.metadata_fields == {}
    
    def test_confidence_notes_for_ambiguous_documents(self):
        """CHK018: Quality warnings for ambiguous docs."""
        metadata = DocumentMetadata(
            document_type=DocumentType.GENERIC,
            summary="Partially readable document",
            metadata_fields={},
            confidence_notes="Handwritten text, poor quality"
        )
        assert "Handwritten" in metadata.confidence_notes
```

**Acceptance**:
- All tests written
- All tests FAIL (Red)
- Test file runs with pytest

---

### TASK-003: Implement Document Models
- **Type**: CODE
- **Dependencies**: TASK-002
- **Estimate**: 2h
- **Status**: [ ]
- **CHK References**: CHK001-004, CHK012-018, CHK111

**File**: `denidin-app/src/models/document.py`

**Implementation**:
```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional

class DocumentType(Enum):
    """CHK012: Five document types."""
    CONTRACT = "contract"
    RECEIPT = "receipt"
    INVOICE = "invoice"
    COURT_RESOLUTION = "court_resolution"
    GENERIC = "generic"

@dataclass
class DocumentMetadata:
    """
    Document type and extracted metadata.
    CHK016-017: All metadata fields are optional.
    CHK018: Confidence notes for ambiguous documents.
    """
    document_type: DocumentType
    summary: str
    metadata_fields: Dict[str, str]
    confidence_notes: Optional[str] = None

@dataclass
class MediaAttachment:
    """
    Media file metadata for WhatsApp messages.
    CHK111: Caption is WhatsApp message text, not file metadata.
    """
    media_type: str
    file_url: str
    file_path: str
    raw_text_path: str
    mime_type: str
    file_size: int
    page_count: Optional[int] = None
    caption: str = ""
    
    def validate(self) -> None:
        """
        CHK001-004, CHK076-077: Validate file size and page count.
        """
        # CHK001-002, CHK076: File size validation (10MB max)
        max_size = 10 * 1024 * 1024
        if self.file_size > max_size:
            raise ValueError(
                f"File too large: {self.file_size} bytes (max {max_size})"
            )
        
        # CHK003-004, CHK077: PDF page count validation
        if self.media_type == 'pdf' and self.page_count:
            if self.page_count > 10:
                raise ValueError(
                    f"PDF has {self.page_count} pages (max 10)"
                )
```

**TDD Actions**:
```bash
# Run tests - should now PASS (Green)
pytest denidin-app/tests/unit/test_document_models.py -v

# Check coverage
pytest denidin-app/tests/unit/test_document_models.py --cov=src/models/document --cov-report=term-missing

# Refactor if needed while keeping tests green
```

**Acceptance**:
- All TASK-002 tests pass (Green)
- 100% code coverage
- No pylint/mypy errors

---

### TASK-004: Create Media Config Test File
- **Type**: TEST
- **Dependencies**: TASK-001
- **Estimate**: 1h
- **Status**: [ ]
- **CHK References**: CHK002, CHK011, CHK039-041, CHK042, CHK048

**File**: `denidin-app/tests/unit/test_media_config.py`

**Test Cases** (all FAIL initially):
```python
import pytest
from pathlib import Path
from src.config.media_config import MediaConfig

class TestMediaConfig:
    def test_supported_image_formats(self):
        """CHK039: JPG, JPEG, PNG only (no GIF)."""
        config = MediaConfig()
        assert 'jpg' in config.SUPPORTED_IMAGE_FORMATS
        assert 'jpeg' in config.SUPPORTED_IMAGE_FORMATS
        assert 'png' in config.SUPPORTED_IMAGE_FORMATS
        assert 'gif' not in config.SUPPORTED_IMAGE_FORMATS
    
    def test_supported_document_formats(self):
        """CHK040-041: PDF and DOCX only (no TXT)."""
        config = MediaConfig()
        assert 'pdf' in config.SUPPORTED_DOCUMENT_FORMATS
        assert 'docx' in config.SUPPORTED_DOCUMENT_FORMATS
        assert 'txt' not in config.SUPPORTED_DOCUMENT_FORMATS
    
    def test_max_file_size_10mb(self):
        """CHK002: 10MB file size limit."""
        config = MediaConfig()
        assert config.MAX_FILE_SIZE_MB == 10
        assert config.MAX_FILE_SIZE_BYTES == 10 * 1024 * 1024
    
    def test_max_pdf_pages_10(self):
        """CHK003-004: 10 pages max for PDFs."""
        config = MediaConfig()
        assert config.MAX_PDF_PAGES == 10
    
    def test_pdf_dpi_150(self):
        """CHK011: 150 DPI for PDF-to-image conversion."""
        config = MediaConfig()
        assert config.PDF_DPI == 150
    
    def test_storage_base_path(self):
        """CHK042: Storage at {data_root}/media/."""
        config = MediaConfig()
        # Should use configurable data_root + media subdirectory
        assert config.STORAGE_BASE == Path("data") / "media"
    
    def test_ai_model_names(self):
        """CHK044-046: Model consistency."""
        config = MediaConfig()
        assert config.VISION_MODEL == "gpt-4o"
        assert config.TEXT_MODEL == "gpt-4o-mini"
    
    def test_max_download_retries(self):
        """CHK048: 1 retry max."""
        config = MediaConfig()
        assert config.MAX_DOWNLOAD_RETRIES == 1
    
    def test_rawtext_encoding_utf8(self):
        """CHK023: UTF-8 encoding for Hebrew support."""
        config = MediaConfig()
        assert config.RAWTEXT_ENCODING == "utf-8"
```

**Acceptance**:
- All tests written
- All tests FAIL (Red)

---

### TASK-005: Implement Media Config
- **Type**: CODE
- **Dependencies**: TASK-004
- **Estimate**: 1h
- **Status**: [ ]

**File**: `denidin-app/src/config/media_config.py`

**Implementation**: *(See plan.md Phase 1.2 for code)*

**TDD Actions**:
```bash
pytest denidin-app/tests/unit/test_media_config.py -v --cov=src/config/media_config
```

**Acceptance**:
- All TASK-004 tests pass
- 100% coverage

---

## Phase 2: File Management (Days 3-5)

### TASK-006: Create Media Manager Test File
- **Type**: TEST
- **Dependencies**: TASK-003, TASK-005
- **Estimate**: 4h
- **Status**: [ ]
- **CHK References**: CHK001-005, CHK019-024, CHK039-041, CHK048, CHK075-076

**File**: `denidin-app/tests/unit/test_media_manager.py`

**Test Cases** (18 tests - all FAIL initially):
```python
import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from datetime import datetime, timezone
from src.utils.media_manager import MediaManager

class TestMediaManagerDownload:
    def test_download_file_success(self):
        """CHK064: Successful file download."""
        manager = MediaManager()
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.content = b"file content"
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            content, success = manager.download_file("https://example.com/file.pdf")
            
            assert success is True
            assert content == b"file content"
    
    def test_download_file_retry_on_failure(self):
        """CHK048: Retry once on failure."""
        manager = MediaManager()
        with patch('requests.get') as mock_get:
            # First call fails, second succeeds
            mock_get.side_effect = [
                Exception("Network error"),
                Mock(content=b"file content", raise_for_status=Mock())
            ]
            
            content, success = manager.download_file("https://example.com/file.pdf")
            
            assert success is True
            assert mock_get.call_count == 2
    
    def test_download_file_max_retries_exceeded(self):
        """CHK048: Fail after 1 retry (2 total attempts)."""
        manager = MediaManager()
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            content, success = manager.download_file("https://example.com/file.pdf")
            
            assert success is False
            assert mock_get.call_count == 2  # Original + 1 retry

class TestMediaManagerValidation:
    def test_validate_file_size_under_limit(self):
        """CHK001-002: File under 10MB passes."""
        manager = MediaManager()
        manager.validate_file_size(5 * 1024 * 1024)  # 5MB - should not raise
    
    def test_validate_file_size_over_limit(self):
        """CHK001-002: File over 10MB fails."""
        manager = MediaManager()
        with pytest.raises(ValueError, match="File too large"):
            manager.validate_file_size(15 * 1024 * 1024)
    
    def test_validate_file_size_exactly_10mb(self):
        """CHK076: Exactly 10MB should pass."""
        manager = MediaManager()
        manager.validate_file_size(10 * 1024 * 1024)  # Should not raise
    
    def test_validate_zero_byte_file(self):
        """CHK075: Reject 0-byte files."""
        manager = MediaManager()
        with pytest.raises(ValueError, match="File is empty"):
            manager.validate_file_size(0)
    
    def test_validate_format_jpg(self):
        """CHK039: JPG is supported."""
        manager = MediaManager()
        media_type = manager.validate_format("photo.jpg", "image/jpeg")
        assert media_type == "image"
    
    def test_validate_format_jpeg(self):
        """CHK039: JPEG variant supported."""
        manager = MediaManager()
        media_type = manager.validate_format("photo.jpeg", "image/jpeg")
        assert media_type == "image"
    
    def test_validate_format_png(self):
        """CHK039: PNG is supported."""
        manager = MediaManager()
        media_type = manager.validate_format("diagram.png", "image/png")
        assert media_type == "image"
    
    def test_validate_format_pdf(self):
        """CHK039: PDF is supported."""
        manager = MediaManager()
        media_type = manager.validate_format("contract.pdf", "application/pdf")
        assert media_type == "pdf"
    
    def test_validate_format_docx(self):
        """CHK039: DOCX is supported."""
        manager = MediaManager()
        media_type = manager.validate_format("report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        assert media_type == "docx"
    
    def test_validate_format_gif_rejected(self):
        """CHK040: GIF not supported."""
        manager = MediaManager()
        with pytest.raises(ValueError, match="Unsupported format: gif"):
            manager.validate_format("animation.gif", "image/gif")
    
    def test_validate_format_txt_rejected(self):
        """CHK041: TXT not supported."""
        manager = MediaManager()
        with pytest.raises(ValueError, match="Unsupported format: txt"):
            manager.validate_format("notes.txt", "text/plain")

class TestMediaManagerStorage:
    def test_create_storage_path_utc_timestamp(self):
        """CHK019: UTC timestamp with microsecond precision."""
        manager = MediaManager()
        with patch('src.utils.media_manager.datetime') as mock_dt:
            mock_now = Mock()
            mock_now.strftime.return_value = "2026-01-22"
            mock_now.timestamp.return_value = 1737561234.567890
            mock_dt.now.return_value = mock_now
            mock_dt.timezone = timezone
            
            with patch('pathlib.Path.mkdir'):
                path = manager.create_storage_path()
            
            assert "2026-01-22" in str(path)
            assert "image-1737561234.567890" in str(path)
    
    def test_save_rawtext_utf8_encoding(self):
        """CHK023: UTF-8 encoding for .rawtext files."""
        manager = MediaManager()
        folder = Path("/tmp/test")
        text = "Hello שלום"  # Hebrew text
        
        m = mock_open()
        with patch('builtins.open', m):
            manager.save_rawtext(text, folder, "file.pdf")
        
        m.assert_called_once_with(
            folder / "file.pdf.rawtext",
            'w',
            encoding='utf-8'
        )
    
    def test_save_rawtext_hebrew_content(self):
        """CHK006-010: Hebrew text storage."""
        manager = MediaManager()
        folder = Path("/tmp/test")
        hebrew_text = "חוזה עבודה עם לקוח"
        
        m = mock_open()
        with patch('builtins.open', m):
            path = manager.save_rawtext(hebrew_text, folder, "contract.pdf")
        
        # Verify handle was obtained with UTF-8
        handle = m()
        handle.write.assert_called_once_with(hebrew_text)
```

**Acceptance**:
- 18 tests written
- All tests FAIL (Red)

---

### TASK-007: Implement Media Manager
- **Type**: CODE
- **Dependencies**: TASK-006
- **Estimate**: 3h
- **Status**: [ ]

**File**: `denidin-app/src/utils/media_manager.py`

**Implementation**: *(See plan.md Phase 2.1 for code)*

**TDD Actions**:
```bash
pytest denidin-app/tests/unit/test_media_manager.py -v --cov=src/utils/media_manager
```

**Acceptance**:
- All 18 tests pass
- 100% coverage
- Handle CHK005 (corrupted files) in implementation

---

## Phase 3: Text Extraction (Days 6-9) ✅ COMPLETE

**Status**: ✅ Merged to master (PR #61)  
**Completion Date**: January 24, 2026  
**Test Results**: 30 passing tests (Media: 10, ImageExtractor: 7, PDFExtractor: 6, DOCXExtractor: 7)

**Deliverables**:
- ✅ Media model with in-memory handling (max 10MB)
- ✅ ImageExtractor using GPT-4o Vision API
- ✅ PDFExtractor with PyMuPDF page conversion
- ✅ DOCXExtractor with python-docx
- ✅ All extractors use DeniDin context pattern
- ✅ Hebrew text support across all extractors
- ✅ Graceful error handling and degradation

### TASK-008: Create Image Extractor Test File ✅
- **Type**: TEST
- **Dependencies**: TASK-007
- **Estimate**: 3h
- **Status**: [x] COMPLETE
- **CHK References**: CHK006-011, CHK027, CHK078, CHK082-083
- **Actual**: 7 tests created (simplified from original 9)

**File**: `denidin-app/tests/unit/test_image_extractor.py`

**Test Cases** (9 tests):
```python
import pytest
from unittest.mock import Mock
from src.utils.extractors.image_extractor import ImageExtractor

@pytest.fixture
def mock_ai_client():
    return Mock()

class TestImageExtractor:
    def test_extract_text_from_simple_image(self, mock_ai_client):
        """Basic text extraction."""
        mock_ai_client.vision_extract.return_value = {
            "text": "Hello World"
        }
        extractor = ImageExtractor(mock_ai_client)
        
        result = extractor.extract_text("/path/to/image.jpg")
        
        assert result["extracted_text"] == "Hello World"
        assert result["model_used"] == "gpt-4o"
    
    def test_extract_text_from_hebrew_image(self, mock_ai_client):
        """CHK006: Hebrew text extraction."""
        mock_ai_client.vision_extract.return_value = {
            "text": "שלום עולם"
        }
        extractor = ImageExtractor(mock_ai_client)
        
        result = extractor.extract_text("/path/to/hebrew.jpg")
        
        assert "שלום" in result["extracted_text"]
    
    def test_extract_mixed_hebrew_english(self, mock_ai_client):
        """CHK008: Mixed language support."""
        mock_ai_client.vision_extract.return_value = {
            "text": "Hello שלום World"
        }
        extractor = ImageExtractor(mock_ai_client)
        
        result = extractor.extract_text("/path/to/mixed.jpg")
        
        assert "Hello" in result["extracted_text"]
        assert "שלום" in result["extracted_text"]
    
    def test_extract_with_layout_preservation(self, mock_ai_client):
        """CHK010: Layout preservation."""
        mock_ai_client.vision_extract.return_value = {
            "text": "Line 1\n\nLine 2\n\nLine 3"
        }
        extractor = ImageExtractor(mock_ai_client)
        
        result = extractor.extract_text("/path/to/formatted.jpg")
        
        # Verify newlines preserved
        assert "\n\n" in result["extracted_text"]
    
    def test_handle_empty_image(self, mock_ai_client):
        """CHK078: Empty image handling."""
        mock_ai_client.vision_extract.return_value = {
            "text": ""
        }
        extractor = ImageExtractor(mock_ai_client)
        
        result = extractor.extract_text("/path/to/empty.jpg")
        
        assert result["extraction_quality"] == "poor"
        assert any("Minimal" in w for w in result["warnings"])
    
    def test_handle_garbled_text_extraction(self, mock_ai_client):
        """CHK007: Graceful failure on garbled text."""
        mock_ai_client.vision_extract.side_effect = Exception("OCR failed")
        extractor = ImageExtractor(mock_ai_client)
        
        result = extractor.extract_text("/path/to/bad.jpg")
        
        assert result["extracted_text"] == ""
        assert result["extraction_quality"] == "failed"
        assert len(result["warnings"]) > 0
    
    def test_prompt_includes_hebrew_requirements(self, mock_ai_client):
        """CHK027: Specific prompt (not just example)."""
        mock_ai_client.vision_extract.return_value = {"text": "test"}
        extractor = ImageExtractor(mock_ai_client)
        
        extractor.extract_text("/path/to/image.jpg")
        
        call_args = mock_ai_client.vision_extract.call_args
        prompt = call_args[1]["prompt"]
        assert "RTL direction" in prompt or "Hebrew" in prompt
    
    def test_assess_quality_good(self, mock_ai_client):
        """Quality assessment for long text."""
        mock_ai_client.vision_extract.return_value = {
            "text": "A" * 100  # Long text
        }
        extractor = ImageExtractor(mock_ai_client)
        
        result = extractor.extract_text("/path/to/image.jpg")
        
        assert result["extraction_quality"] == "good"
    
    def test_assess_quality_fair(self, mock_ai_client):
        """Quality assessment for short text."""
        mock_ai_client.vision_extract.return_value = {
            "text": "Short"
        }
        extractor = ImageExtractor(mock_ai_client)
        
        result = extractor.extract_text("/path/to/image.jpg")
        
        assert result["extraction_quality"] == "fair"
```

**Acceptance**:
- 7 tests written (Media model-based, simplified from original plan)
- All FAIL (Red) ✅

---

### TASK-009: Implement Image Extractor ✅
- **Type**: CODE
- **Dependencies**: TASK-008
- **Estimate**: 2h
- **Status**: [x] COMPLETE

**File**: `denidin-app/src/utils/extractors/image_extractor.py`

**Implementation Notes**:
- Uses Media model for in-memory processing
- DeniDin context pattern for ai_handler and config
- Constitution prepended to user prompt (no system message)
- AI self-assessment for quality (high/medium/low)
- Hebrew text with RTL preservation

**TDD Results**:
```bash
✅ 7/7 tests passing
✅ ImageExtractor fully implemented
```

**Acceptance**:
- All tests pass ✅
- Hebrew text extraction working ✅

---

### TASK-010: Create PDF Extractor Test File ✅
- **Type**: TEST
- **Dependencies**: TASK-009
- **Estimate**: 3h
- **Status**: [x] COMPLETE
- **CHK References**: CHK004-005, CHK011, CHK077, CHK079-080

**File**: `denidin-app/tests/unit/test_pdf_extractor.py`

**Test Cases**: 6 tests (per-page array results)

**Acceptance**:
- All tests FAIL (Red) ✅

---

### TASK-011: Implement PDF Extractor ✅
- **Type**: CODE
- **Dependencies**: TASK-010
- **Estimate**: 3h
- **Status**: [x] COMPLETE

**File**: `denidin-app/src/utils/extractors/pdf_extractor.py`

**Implementation Notes**:
- PyMuPDF (fitz) for page-to-image conversion
- Delegates to ImageExtractor for each page
- Per-page arrays for text, quality, warnings
- Single model_used field (shared)

**Acceptance**:
- All TASK-010 tests pass ✅
- 6/6 tests passing ✅

---

### TASK-012: Create DOCX Extractor Test File ✅
- **Type**: TEST
- **Dependencies**: TASK-007
- **Estimate**: 2h
- **Status**: [x] COMPLETE
- **CHK References**: CHK005, CHK078, CHK081

**File**: `denidin-app/tests/unit/test_docx_extractor.py`

**Test Cases**: 7 tests (Media-based, updated from file-path version)

**Acceptance**:
- All tests FAIL (Red) ✅

---

### TASK-013: Implement DOCX Extractor ✅
- **Type**: CODE
- **Dependencies**: TASK-012
- **Estimate**: 2h
- **Status**: [x] COMPLETE

**File**: `denidin-app/src/utils/extractors/docx_extractor.py`

**Implementation Notes**:
- python-docx library for text extraction
- Extracts paragraphs and table content
- No AI needed (deterministic extraction)
- Hebrew UTF-8 support
- Paragraph structure preservation

**Acceptance**:
- All tests pass ✅
- 7/7 tests passing ✅

---

**Phase 3 Summary**:
- Total files created: 7
- Total tests passing: 30
- Media model: 10 tests
- ImageExtractor: 7 tests  
- PDFExtractor: 6 tests
- DOCXExtractor: 7 tests
- PR #61 merged to master ✅

---

---

## Phase 4: Document Analysis (Days 10-12)

### TASK-014: Create Document Analyzer Test File
- **Type**: TEST
- **Dependencies**: TASK-003
- **Estimate**: 4h
- **Status**: [ ]
- **CHK References**: CHK012-018, CHK036-037

**File**: `denidin-app/tests/unit/test_document_analyzer.py`

**Test Cases** (13 tests - see plan.md Phase 4.1)

**Acceptance**:
- All tests FAIL (Red)

---

### TASK-015: Implement Document Analyzer
- **Type**: CODE
- **Dependencies**: TASK-014
- **Estimate**: 3h
- **Status**: [ ]

**File**: `denidin-app/src/utils/document_analyzer.py`

**Acceptance**:
- All tests pass
- 100% coverage

---

## Phase 5: Media Handler (Days 13-15)

### TASK-016: Create Media Handler Test File
- **Type**: TEST
- **Dependencies**: TASK-009, TASK-011, TASK-013, TASK-015
- **Estimate**: 4h
- **Status**: [x] COMPLETE (January 25, 2026)
- **CHK References**: CHK030, CHK060-061, CHK064-067, CHK112

**File**: `denidin-app/tests/unit/test_media_handler.py`

**Test Cases** (14 integration-style unit tests - see plan.md Phase 5.1)

**Acceptance**:
- All tests FAIL (Red)

---

### TASK-017: Implement Media Handler
- **Type**: CODE
- **Dependencies**: TASK-016
- **Estimate**: 3h
- **Status**: [x] COMPLETE (January 25, 2026)

**File**: `denidin-app/src/handlers/media_handler.py`

**Acceptance**:
- All tests pass
- 100% coverage
- End-to-end flow validated

**✅ Completion Summary (January 25, 2026)**:
- ✅ 14 MediaHandler tests implemented and passing
- ✅ MediaHandler orchestrates: download → validate → extract → store
- ✅ Flat storage: `{data_root}/media/DD-{phone}-{uuid}.{ext}`
- ✅ MediaManager renamed to MediaFileManager for clarity
- ✅ 8 constitution/caption tests verify AI architecture
- ✅ **BONUS**: Externalized prompts to `prompts/` directory
  - `prompts/docx_analysis.txt`
  - `prompts/image_analysis.txt`
- ✅ Total: 373 tests passing
- ✅ PR #66 merged, PR #67 merged (cleanup)

---

## Phase 6: WhatsApp Integration (Days 16-17)

### TASK-018: Create WhatsApp Media Integration Test File
- **Type**: TEST
- **Dependencies**: TASK-017
- **Estimate**: 3h
- **Status**: [ ]
- **CHK References**: CHK111-112

**File**: `denidin-app/tests/unit/test_whatsapp_handler_media.py`

**Test Cases** (9 tests - see plan.md Phase 6.1)

**Acceptance**:
- All tests FAIL (Red)

---

### TASK-019: Implement WhatsApp Media Integration
- **Type**: CODE
- **Dependencies**: TASK-018
- **Estimate**: 2h
- **Status**: [ ]

**File**: `denidin-app/src/handlers/whatsapp_handler.py` (modifications)

**Acceptance**:
- All tests pass
- Media messages routed correctly
- Approval flow works

---

## Phase 7: Integration Testing (Days 18-20)

### TASK-020: Create Integration Test File
- **Type**: TEST
- **Dependencies**: TASK-019
- **Estimate**: 5h
- **Status**: [ ]
- **CHK References**: All use cases UC1-UC10, CHK059, CHK062, CHK072

**File**: `denidin-app/tests/integration/test_media_flow_integration.py`

**Test Cases** (8 end-to-end tests - see plan.md Phase 7.1)

**Acceptance**:
- All tests FAIL initially (Red)

---

### TASK-021: Fix Integration Issues
- **Type**: CODE
- **Dependencies**: TASK-020
- **Estimate**: 4h
- **Status**: [ ]

**Actions**:
- Run integration tests
- Fix any cross-component issues
- Ensure all 10 use cases work

**Acceptance**:
- All integration tests pass (Green)
- All use cases validated

---

### TASK-022: Hebrew Test Data Setup
- **Type**: CODE
- **Dependencies**: None
- **Estimate**: 3h
- **Status**: [ ]
- **CHK References**: CHK009, CHK055

**Actions**:
```bash
# Create test data directory
mkdir -p denidin-app/tests/fixtures/hebrew

# Collect Hebrew test documents:
# - Hebrew contract PDF
# - Hebrew receipt image (JPG)
# - Hebrew invoice DOCX
# - Mixed Hebrew/English documents
# - Handwritten Hebrew notes (for ambiguity testing)
```

**Acceptance**:
- At least 5 Hebrew test documents
- Cover all document types
- Include edge cases

---

### TASK-023: Final Coverage & Quality Check
- **Type**: CODE
- **Dependencies**: TASK-021
- **Estimate**: 2h
- **Status**: [ ]

**Actions**:
```bash
# Run full test suite
pytest denidin-app/tests/ -v

# Check coverage
pytest denidin-app/tests/ --cov=src --cov-report=html --cov-report=term

# Verify 100% coverage for new modules
pytest denidin-app/tests/unit/ --cov=src/utils/media_manager --cov-fail-under=100
pytest denidin-app/tests/unit/ --cov=src/utils/extractors --cov-fail-under=100
pytest denidin-app/tests/unit/ --cov=src/handlers/media_handler --cov-fail-under=100

# Run linting
pylint denidin-app/src/utils/media_manager.py
pylint denidin-app/src/utils/extractors/
pylint denidin-app/src/handlers/media_handler.py

# Type checking
mypy denidin-app/src/utils/media_manager.py
mypy denidin-app/src/utils/extractors/
mypy denidin-app/src/handlers/media_handler.py
```

**Acceptance**:
- 100% unit test coverage for new code
- All integration tests pass
- No linting errors
- No type errors
- All 27 CHK requirements validated in tests

---

## Quick Reference: TDD + Git Workflow

### For Each Task Pair (TEST + CODE)

```bash
# 1. RED: Write tests (should fail)
pytest tests/unit/test_COMPONENT.py -v
# Expected: All new tests FAIL

# 2. GREEN: Implement minimal code
# ... write code ...
pytest tests/unit/test_COMPONENT.py -v
# Expected: All tests PASS

# 3. REFACTOR: Clean up code
# ... improve code quality ...
pytest tests/unit/test_COMPONENT.py -v
# Expected: Tests still PASS

# 4. Coverage check
pytest tests/unit/test_COMPONENT.py --cov=src/path/to/module --cov-report=term-missing
# Expected: 100% coverage
```

### For Each Phase Completion

```bash
# 1. STAGE: Add relevant files
git add denidin-app/src/path/to/files.py
git add denidin-app/tests/unit/test_*.py
git add denidin-app/requirements.txt  # if updated

# 2. COMMIT: Use conventional commits format
git commit -m "feat: Phase X - Description (CHK###-###)

Implementation details:
- Key change 1
- Key change 2
- Test results: X tests, Y% coverage

CHK Requirements: CHK###-###
Tasks: TASK-00X to TASK-00Y complete (Phase X: A/B)"

# 3. PUSH: To remote feature branch
git push -u origin feature/003-media-processing-phaseX

# 4. PR: Create pull request
gh pr create --title "Feature 003 Phase X: Description" \
  --body "## Summary
Detailed description

## Tests: X passing, Y% coverage
## CHK: CHK###-###
## Tasks: TASK-00X to TASK-00Y" \
  --base master

# 5. MERGE: Via GitHub web interface OR locally
# Web: Click "Merge pull request" button
# Local:
git checkout master
git merge --no-ff feature/003-media-processing-phaseX
git push origin master
git branch -d feature/003-media-processing-phaseX
```

### Complete Phase Workflow Example

```bash
# Start Phase 1
git checkout -b feature/003-media-processing-phase1

# Work through TASK-001 to TASK-005
# ... write tests, implement code, verify coverage ...

# Stage Phase 1 files
git add denidin-app/src/models/document.py
git add denidin-app/src/config/
git add denidin-app/tests/unit/test_document_models.py
git add denidin-app/tests/unit/test_media_config.py
git add denidin-app/requirements.txt

# Commit Phase 1
git commit -m "feat: Phase 1 - Document Models & Media Config (CHK001-048)

Implements Feature 003 Phase 1 using TDD:
- Document type enum (5 types)
- MediaAttachment with validation
- MediaConfig with constants
- 48 tests, 100% coverage, pylint 10/10

Implementation:
- src/models/document.py
- src/config/media_config.py

Testing:
- tests/unit/test_document_models.py: 26 tests
- tests/unit/test_media_config.py: 22 tests

CHK Requirements: CHK001-004, CHK012-018, CHK039-048, CHK075-077
Tasks: TASK-001 to TASK-005 complete (Phase 1: 5/5 = 100%)"

# Push and create PR
git push -u origin feature/003-media-processing-phase1
gh pr create --title "Feature 003 Phase 1: Document Models & Media Config" \
  --body "See CONSTITUTION.md §III for PR template" --base master

# Merge (via web or locally)
git checkout master
git merge --no-ff feature/003-media-processing-phase1 \
  -m "Merge pull request #X from user/feature/003-media-processing-phase1

Feature 003 Phase 1: Document Models & Media Config"
git push origin master
git branch -d feature/003-media-processing-phase1
```

---

## Dependencies Installation

```bash
# Add to requirements.txt:
PyMuPDF>=1.23.0      # PDF processing
python-docx>=1.0.0   # DOCX extraction
Pillow>=10.0.0       # Image utilities
pytest>=7.4.0        # Testing
pytest-cov>=4.1.0    # Coverage
pytest-mock>=3.12.0  # Mocking
```

---

## Success Criteria

**Phase Completion**:
- [ ] Phase 1: All model tests pass, 100% coverage
- [ ] Phase 2: All file management tests pass, 100% coverage
- [ ] Phase 3: All extractor tests pass, 100% coverage, Hebrew validation
- [ ] Phase 4: All analyzer tests pass, 100% coverage
- [ ] Phase 5: All handler tests pass, 100% coverage
- [ ] Phase 6: WhatsApp integration tests pass
- [ ] Phase 7: All integration tests pass, all use cases validated

**Overall**:
- [ ] 100% unit test coverage for new code
- [ ] All 27 CHK requirements tested
- [ ] All 10 use cases (UC1-UC10) validated
- [ ] Hebrew text processing verified
- [ ] TDD workflow followed for every component

---

## Tracking Progress

Update task status:
- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete

Example:
```markdown
### TASK-001: Setup Test Infrastructure
- **Status**: [x]  ← COMPLETED
```

**Current Status**: 0/23 tasks complete (0%)

---

**Next Step**: Begin with TASK-001 (Setup Test Infrastructure)
