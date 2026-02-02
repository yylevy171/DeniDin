"""
PDF Text Extractor (Feature 003 Phase 3.2 + Phase 4 Enhancement)
Extract text from PDFs AND analyze documents by converting pages to images.

Phase 4 Enhancement: Aggregates document analysis from all pages.

CHK Requirements:
- CHK006: Hebrew text extraction required
- CHK007: Graceful degradation on extraction failures
- CHK008: Mixed Hebrew/English support
- CHK010: Layout/structure preservation
- CHK078: Empty document handling
"""
from typing import Dict, List
import io
import logging
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from src.models.media import Media
from src.handlers.extractors.base import MediaExtractor
from src.handlers.extractors.image_extractor import ImageExtractor

logger = logging.getLogger(__name__)


class PDFExtractor(MediaExtractor):
    """
    Extract text and analyze documents from PDFs by converting pages to images.
    
    Phase 4: Aggregates document analysis from all pages into single summary.
    """
    
    def __init__(self, denidin_context):
        """
        Initialize with DeniDin global context.
        
        Args:
            denidin_context: DeniDin instance with ai_handler and config
        """
        super().__init__(denidin_context)
        self.vision_model = self.config.ai_vision_model
        
        # Create ImageExtractor for page processing
        self.image_extractor = ImageExtractor(denidin_context)
    
    def analyze_media(self, media: Media, caption: str = "") -> Dict:
        """
        Analyze PDF using GPT-4o Vision (Phase 4 enhancement).
        
        Multi-page PDF processing:
        1. Convert each page to image
        2. Send to Vision API for analysis
        3. Combine raw_responses from all pages
        
        Args:
            media: Media object containing PDF data in memory
            caption: User's message/question sent with the PDF (optional)
            
        Returns:
            {
                "raw_response": str,  # Combined AI responses from all pages
                "extraction_quality": List[str],  # Quality per page
                "warnings": List[List[str]],  # Warnings per page
                "model_used": str  # e.g. "gpt-4o"
            }
        """
        try:
            # CHK007: Check if PyMuPDF is available
            if fitz is None:
                return {
                    "extracted_text": [],
                    "document_analysis": {
                        "document_type": "generic",
                        "summary": "PDF processing unavailable",
                        "key_points": []
                    },
                    "extraction_quality": [],
                    "warnings": [["PyMuPDF not installed"]],
                    "model_used": self.vision_model
                }
            
            # Open PDF from in-memory bytes
            pdf_document = fitz.open(stream=media.data, filetype="pdf")
            
            # CHK078: Handle empty PDF
            page_count = len(pdf_document)
            if page_count == 0:
                pdf_document.close()
                return {
                    "raw_response": "סיכום: Empty PDF document",
                    "document_analysis": {
                        "document_type": "generic",
                        "summary": "Empty PDF document",
                        "key_points": []
                    },
                    "extraction_quality": [],
                    "warnings": [],
                    "model_used": self.vision_model
                }
            
            # Process each page
            raw_responses = []  # Collect raw_response from each page
            extraction_qualities = []
            warnings_list = []
            page_analyses = []  # Collect analyses from each page
            
            for page_num, page in enumerate(pdf_document):
                try:
                    # Convert page to image (PNG format)
                    pixmap = page.get_pixmap()
                    png_bytes = pixmap.tobytes(output="png")
                    logger.info(f"[PDFExtractor.analyze_media] Page {page_num + 1}: Converted to PNG ({len(png_bytes)} bytes, {pixmap.width}x{pixmap.height}px)")
                    
                    # Create Media object for the page image
                    page_media = Media.from_bytes(
                        data=png_bytes,
                        mime_type="image/png",
                        filename=f"page_{page_num + 1}.png"
                    )
                    
                    # Delegate to ImageExtractor (returns raw_response)
                    # Pass caption to provide context for analysis
                    logger.info(f"[PDFExtractor.analyze_media] Sending page {page_num + 1} to ImageExtractor")
                    page_result = self.image_extractor.analyze_media(page_media, caption=caption)
                    
                    # Collect per-page results
                    raw_responses.append(page_result["raw_response"])
                    extraction_qualities.append(page_result["extraction_quality"])
                    warnings_list.append(page_result["warnings"])
                    logger.info(f"[PDFExtractor.analyze_media] Page {page_num + 1} analysis complete: {len(page_result.get('raw_response', ''))} chars")
                    
                except Exception as e:
                    # CHK007: Handle per-page failures gracefully
                    logger.error(f"[PDFExtractor.analyze_media] Page {page_num + 1} failed: {e}", exc_info=True)
                    raw_responses.append("")
                    extraction_qualities.append("failed")
                    warnings_list.append([f"Page {page_num + 1} failed: {str(e)}"])
            
            pdf_document.close()
            
            # For PDFs, combine raw_responses from all pages
            combined_raw_response = "\n---\n".join([r for r in raw_responses if r])
            if not combined_raw_response:
                combined_raw_response = "סיכום: PDF analysis completed but no content extracted"
            
            return {
                "raw_response": combined_raw_response,
                "extraction_quality": extraction_qualities,
                "warnings": warnings_list,
                "model_used": self.vision_model
            }
            
        except Exception as e:
            # CHK007: Fail gracefully on PDF-level errors
            return {
                "raw_response": "",
                "extraction_quality": [],
                "warnings": [[f"PDF analysis failed: {str(e)}"]],
                "model_used": self.vision_model
            }

