"""
PDF Text Extractor (Feature 003 Phase 3.2)
Extract text from PDFs by converting pages to images and using ImageExtractor.

CHK Requirements:
- CHK006: Hebrew text extraction required
- CHK007: Graceful degradation on extraction failures
- CHK008: Mixed Hebrew/English support
- CHK010: Layout/structure preservation
- CHK078: Empty document handling
"""
from typing import Dict, List
import io
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from src.models.media import Media
from src.utils.extractors.image_extractor import ImageExtractor


class PDFExtractor:
    """Extract text from PDFs by converting pages to images."""
    
    def __init__(self, denidin_context):
        """
        Initialize with DeniDin global context.
        
        Args:
            denidin_context: DeniDin instance with ai_handler and config
        """
        self.context = denidin_context
        self.config = denidin_context.config
        self.vision_model = self.config.ai_vision_model
        
        # Create ImageExtractor for page processing
        self.image_extractor = ImageExtractor(denidin_context)
    
    def extract_text(self, media: Media) -> Dict:
        """
        Extract text from PDF with Hebrew support.
        Converts each page to image and delegates to ImageExtractor.
        
        Args:
            media: Media object containing PDF data in memory
            
        Returns:
            {
                "extracted_text": List[str],  # Per-page text
                "extraction_quality": List[str],  # Per-page quality
                "warnings": List[List[str]],  # Per-page warnings
                "model_used": str  # Same model for all pages
            }
        """
        try:
            # CHK007: Check if PyMuPDF is available
            if fitz is None:
                return {
                    "extracted_text": [],
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
                    "extracted_text": [],
                    "extraction_quality": [],
                    "warnings": [],
                    "model_used": self.vision_model
                }
            
            # Process each page
            extracted_texts = []
            extraction_qualities = []
            warnings_list = []
            
            for page_num, page in enumerate(pdf_document):
                try:
                    # Convert page to image (PNG format)
                    pixmap = page.get_pixmap()
                    png_bytes = pixmap.tobytes(output="png")
                    
                    # Create Media object for the page image
                    page_media = Media.from_bytes(
                        data=png_bytes,
                        mime_type="image/png",
                        filename=f"page_{page_num + 1}.png"
                    )
                    
                    # Delegate to ImageExtractor
                    page_result = self.image_extractor.extract_text(page_media)
                    
                    # Collect per-page results
                    extracted_texts.append(page_result["extracted_text"])
                    extraction_qualities.append(page_result["extraction_quality"])
                    warnings_list.append(page_result["warnings"])
                    
                except Exception as e:
                    # CHK007: Handle per-page failures gracefully
                    extracted_texts.append("")
                    extraction_qualities.append("failed")
                    warnings_list.append([f"Page {page_num + 1} failed: {str(e)}"])
            
            pdf_document.close()
            
            return {
                "extracted_text": extracted_texts,
                "extraction_quality": extraction_qualities,
                "warnings": warnings_list,
                "model_used": self.vision_model
            }
            
        except Exception as e:
            # CHK007: Fail gracefully on PDF-level errors
            return {
                "extracted_text": [],
                "extraction_quality": [],
                "warnings": [[f"PDF extraction failed: {str(e)}"]],
                "model_used": self.vision_model
            }
