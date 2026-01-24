"""
Image Text Extractor (Feature 003 Phase 3.1)
Extract text from images using GPT-4o Vision API.

CHK Requirements:
- CHK006: Hebrew text extraction required
- CHK007: Graceful degradation on extraction failures
- CHK008: Mixed Hebrew/English support
- CHK010: Layout/structure preservation
- CHK027: Specific prompt (not just example)
- CHK078: Empty document handling
"""
from typing import Dict, List
from src.models.media import Media


class ImageExtractor:
    """Extract text from images using GPT-4o Vision."""
    
    def __init__(self, denidin_context):
        """
        Initialize with DeniDin global context.
        
        Args:
            denidin_context: DeniDin instance with ai_handler and config
        """
        self.context = denidin_context
        self.ai_handler = denidin_context.ai_handler
        self.config = denidin_context.config
        self.vision_model = self.config.ai_vision_model
    
    def extract_text(self, media: Media) -> Dict:
        """
        Extract text from image with Hebrew support.
        CHK006-011: Hebrew text extraction with layout preservation.
        
        Args:
            media: Media object containing image data in memory
            
        Returns:
            {
                "extracted_text": str,
                "extraction_quality": str,  # "high", "medium", "low", "failed"
                "warnings": List[str],
                "model_used": str  # e.g. "gpt-4o"
            }
        """
        try:
            # CHK027: Use specific prompt with quality self-assessment
            prompt = (
                "Extract all text from this image. "
                "Preserve layout, paragraphs, and line breaks. "
                "Maintain RTL direction for Hebrew text. "
                "After extraction, assess your confidence level (high/medium/low) "
                "based on image clarity, text legibility, and OCR certainty. "
                "Format your response as:\n"
                "TEXT:\n[extracted text here]\n"
                "CONFIDENCE: [high/medium/low]\n"
                "NOTES: [any issues or uncertainties]"
            )
            
            # Call Vision API with in-memory media
            response = self._vision_extract(media, prompt)
            
            # Parse structured response from AI
            response_text = response.get("text", "")
            extracted_text, confidence, ai_notes = self._parse_ai_response(response_text)
            
            # CHK007: Collect warnings
            warnings: List[str] = []
            
            # Add AI's own notes as warnings if present
            if ai_notes:
                warnings.append(f"AI notes: {ai_notes}")
            
            return {
                "extracted_text": extracted_text,
                "extraction_quality": confidence,  # Use AI confidence directly
                "warnings": warnings,
                "model_used": self.vision_model
            }
            
        except Exception as e:
            # CHK007: Fail gracefully
            return {
                "extracted_text": "",
                "extraction_quality": "failed",
                "warnings": [f"Extraction failed: {str(e)}"],
                "model_used": self.vision_model
            }
    
    def _vision_extract(self, media: Media, prompt: str) -> dict:
        """
        Extract text from image using GPT-4o Vision with constitution context.
        
        Args:
            media: Media object containing image data
            prompt: Extraction prompt (will be prepended with constitution)
            
        Returns:
            {"text": str} - Extracted text response from vision model
        """
        # Load constitution for context
        constitution = self.ai_handler._load_constitution()
        
        # Prepend constitution to user prompt (NO system message!)
        full_prompt = f"{constitution}\n\n{prompt}" if constitution else prompt
        
        # Call OpenAI Vision API with in-memory data URL
        response = self.ai_handler.client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": media.get_data_url()  # Use Media's data URL method
                            }
                        }
                    ]
                }
            ],
            max_tokens=self.config.ai_reply_max_tokens
        )
        
        return {"text": response.choices[0].message.content}
    
    def _parse_ai_response(self, response_text: str) -> tuple[str, str, str]:
        """
        Parse structured AI response into text, confidence, and notes.
        
        Expected format:
            TEXT:
            [extracted text]
            CONFIDENCE: high/medium/low
            NOTES: [optional notes]
        
        Args:
            response_text: Raw response from AI
            
        Returns:
            (extracted_text, confidence_level, notes)
        """
        # Default values if parsing fails
        extracted_text = response_text
        confidence = "medium"
        notes = ""
        
        try:
            # Split by section markers
            parts = response_text.split("CONFIDENCE:")
            if len(parts) == 2:
                # Extract text section
                text_section = parts[0].replace("TEXT:", "").strip()
                extracted_text = text_section
                
                # Extract confidence and notes
                remaining = parts[1]
                if "NOTES:" in remaining:
                    conf_part, notes_part = remaining.split("NOTES:", 1)
                    confidence = conf_part.strip().lower()
                    notes = notes_part.strip()
                else:
                    confidence = remaining.strip().lower()
        except Exception:
            # If parsing fails, return raw text with medium confidence
            pass
        
        return extracted_text, confidence, notes
