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
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from src.models.media import Media
from src.handlers.extractors.base import MediaExtractor
from src.handlers.extractors.image_extractor import ImageExtractor


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
    
    def extract_text(self, media: Media, caption: str = "") -> Dict:
        """
        Extract text AND analyze document from PDF (Phase 4 enhancement).
        
        Converts each page to image, extracts text + analysis per page,
        then aggregates into single document analysis.
        
        Args:
            media: Media object containing PDF data
            caption: User's message/question sent with the PDF (optional)
        
        Args:
            media: Media object containing PDF data in memory
            
        Returns:
            {
                "extracted_text": List[str],  # Per-page text
                "document_analysis": {         # Aggregated from all pages
                    "document_type": str,
                    "summary": str,
                    "key_points": List[str]
                },
                "extraction_quality": List[str],  # Per-page quality
                "warnings": List[List[str]],  # Per-page warnings
                "model_used": str
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
                    "extracted_text": [],
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
            extracted_texts = []
            extraction_qualities = []
            warnings_list = []
            page_analyses = []  # Phase 4: Collect analyses from each page
            
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
                    
                    # Delegate to ImageExtractor (returns text + analysis)
                    # Pass caption to provide context for analysis
                    page_result = self.image_extractor.extract_text(page_media, caption=caption)
                    
                    # Collect per-page results
                    extracted_texts.append(page_result["extracted_text"])
                    extraction_qualities.append(page_result["extraction_quality"])
                    warnings_list.append(page_result["warnings"])
                    page_analyses.append(page_result["document_analysis"])
                    
                except Exception as e:
                    # CHK007: Handle per-page failures gracefully
                    extracted_texts.append("")
                    extraction_qualities.append("failed")
                    warnings_list.append([f"Page {page_num + 1} failed: {str(e)}"])
                    page_analyses.append(None)
            
            pdf_document.close()
            
            # Phase 4: Aggregate document analysis from all pages
            aggregated_analysis = self._aggregate_document_analysis(page_analyses)
            
            return {
                "extracted_text": extracted_texts,
                "document_analysis": aggregated_analysis,
                "extraction_quality": extraction_qualities,
                "warnings": warnings_list,
                "model_used": self.vision_model
            }
            
        except Exception as e:
            # CHK007: Fail gracefully on PDF-level errors
            return {
                "extracted_text": [],
                "document_analysis": {
                    "document_type": "generic",
                    "summary": "PDF analysis failed",
                    "key_points": []
                },
                "extraction_quality": [],
                "warnings": [[f"PDF extraction failed: {str(e)}"]],
                "model_used": self.vision_model
            }
    
    def _aggregate_document_analysis(self, page_analyses: List[Dict]) -> Dict:
        """
        Aggregate document analysis from multiple pages into single summary.
        
        Strategy:
        - document_type: Use most common type across pages
        - summary: Combine summaries from all pages
        - key_points: Merge and deduplicate key points
        
        Args:
            page_analyses: List of document_analysis dicts from each page
            
        Returns:
            Aggregated document_analysis dict
        """
        # Filter out None/failed analyses
        valid_analyses = [a for a in page_analyses if a is not None]
        
        if not valid_analyses:
            return {
                "document_type": "generic",
                "summary": "No valid analysis available",
                "key_points": []
            }
        
        # Determine document type (most common)
        doc_types = [a["document_type"] for a in valid_analyses]
        document_type = max(set(doc_types), key=doc_types.count) if doc_types else "generic"
        
        # Combine summaries
        summaries = [a["summary"] for a in valid_analyses if a["summary"]]
        if summaries:
            if len(summaries) == 1:
                summary = summaries[0]
            else:
                summary = f"Multi-page document: {' '.join(summaries)[:200]}..."  # Limit length
        else:
            summary = "PDF document"
        
        # Merge and deduplicate key points
        all_points = []
        seen_points = set()
        for analysis in valid_analyses:
            for point in analysis.get("key_points", []):
                # Simple deduplication by lowercased content
                point_lower = point.lower()
                if point_lower not in seen_points:
                    all_points.append(point)
                    seen_points.add(point_lower)
        
        return {
            "document_type": document_type,
            "summary": summary,
            "key_points": all_points
        }
