"""
DOCX Text Extractor (Feature 003 Phase 3.3)
Extract text from Word documents using python-docx library.

CHK Requirements:
- CHK005: Graceful handling of corrupted files
- CHK006-010: Hebrew text extraction with UTF-8 encoding
- CHK078: Empty document handling with warnings
- CHK081: Track changes and comments handling
"""
from typing import Dict, List
from docx import Document


class DOCXExtractor:
    """Extract text from DOCX files using python-docx."""
    
    def extract_text(self, docx_path: str) -> Dict:
        """
        Extract text from DOCX (text-only, no vision API needed).
        CHK006-010: Hebrew support via UTF-8.
        
        Args:
            docx_path: Path to DOCX file
            
        Returns:
            {
                "extracted_text": str,
                "warnings": List[str],
                "model_used": "python-docx"
            }
        """
        warnings: List[str] = []
        
        try:
            doc = Document(docx_path)
            
            # Extract all paragraph text
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)
            
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
            # CHK005: Corrupted file handling - graceful failure
            return {
                "extracted_text": "",
                "warnings": [f"DOCX processing failed: {str(e)}"],
                "model_used": "python-docx"
            }
