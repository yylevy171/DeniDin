"""
DOCX Text Extractor (Feature 003 Phase 3.3)
Extract text from Word documents using python-docx library.

CHK Requirements:
- CHK005: Graceful handling of corrupted files
- CHK006: Hebrew text extraction with UTF-8 encoding
- CHK007: Graceful degradation on failures
- CHK010: Layout/structure preservation
- CHK078: Empty document handling
"""
import io
from typing import Dict, List
from docx import Document
from src.models.media import Media


class DOCXExtractor:
    """Extract text from DOCX files using python-docx."""
    
    def __init__(self, denidin_context):
        """
        Initialize with DeniDin global context.
        
        Args:
            denidin_context: DeniDin instance with config
        """
        self.context = denidin_context
        self.config = denidin_context.config
    
    def extract_text(self, media: Media) -> Dict:
        """
        Extract text from DOCX (text-only, no AI needed).
        CHK006: Hebrew support via UTF-8.
        CHK010: Preserve paragraph structure.
        
        Args:
            media: Media object containing DOCX data in memory
            
        Returns:
            {
                "extracted_text": str,
                "warnings": List[str],
                "model_used": "python-docx"
            }
        """
        warnings: List[str] = []
        
        try:
            # Open DOCX from in-memory bytes
            docx_stream = io.BytesIO(media.data)
            doc = Document(docx_stream)
            
            # Extract all paragraph text
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        if cell_text and cell_text not in paragraphs:
                            paragraphs.append(cell_text)
            
            # CHK010: Preserve paragraph structure with double newlines
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
            # CHK005, CHK007: Graceful failure on corrupted/invalid files
            return {
                "extracted_text": "",
                "warnings": [f"DOCX extraction failed: {str(e)}"],
                "model_used": "python-docx"
            }

