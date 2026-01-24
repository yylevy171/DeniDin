"""
Image Text Extractor (Feature 003 Phase 3.1 + Phase 4 Enhancement)
Extract text from images AND analyze documents using GPT-4o Vision API.

Phase 4 Enhancement: Single AI call returns text + document analysis.

CHK Requirements:
- CHK006: Hebrew text extraction required
- CHK007: Graceful degradation on extraction failures
- CHK008: Mixed Hebrew/English support
- CHK010: Layout/structure preservation
- CHK027: Specific prompt (not just example)
- CHK078: Empty document handling
"""
from typing import Dict, List
from pathlib import Path
from src.models.media import Media
from src.handlers.extractors.base import MediaExtractor


class ImageExtractor(MediaExtractor):
    """
    Extract text and analyze documents from images using GPT-4o Vision.
    
    Phase 4: Enhanced to return text + document analysis in single AI call.
    """
    
    def __init__(self, denidin_context):
        """
        Initialize with DeniDin global context.
        
        Args:
            denidin_context: DeniDin instance with ai_handler and config
        """
        super().__init__(denidin_context)
        self.ai_handler = denidin_context.ai_handler
        self.vision_model = self.config.ai_vision_model
    
    def extract_text(self, media: Media, caption: str = "") -> Dict:
        """
        Extract text AND analyze document from image (Phase 4 enhancement).
        
        Single AI call returns:
        - Extracted text with Hebrew support and layout preservation
        - Document analysis (type, summary, key points)
        - Quality assessment
        
        CHK006-011: Hebrew text extraction with layout preservation.
        
        Args:
            media: Media object containing image data in memory
            caption: User's message/question sent with the image (optional)
            
        Returns:
            {
                "extracted_text": str,
                "document_analysis": {
                    "document_type": str,
                    "summary": str,
                    "key_points": List[str]
                },
                "extraction_quality": str,  # "high", "medium", "low", "failed"
                "warnings": List[str],
                "model_used": str  # e.g. "gpt-4o"
            }
        """
        try:
            # Load prompt template from external file
            prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / "image_analysis.txt"
            prompt_template = prompt_path.read_text(encoding='utf-8')
            
            # CHK027: Enhanced prompt for text extraction + document analysis
            # Include user's caption/question for context
            user_context = f"\n\nUser's question/message: {caption}" if caption else ""
            addressing_note = " addressing the user's question" if caption else ""
            focusing_note = ", focusing on what the user asked about" if caption else ""
            
            # Format the prompt with context
            prompt = prompt_template.format(
                user_context=user_context,
                addressing_note=addressing_note,
                focusing_note=focusing_note
            )
            
            # Call Vision API with in-memory media (constitution prepended in _vision_extract)
            response = self._vision_extract(media, prompt)
            
            # Parse enhanced response from AI
            response_text = response.get("text", "")
            result = self._parse_enhanced_response(response_text)
            
            # CHK007: Collect warnings
            warnings: List[str] = []
            if result["ai_notes"]:
                warnings.append(f"AI notes: {result['ai_notes']}")
            
            return {
                "extracted_text": result["extracted_text"],
                "document_analysis": {
                    "document_type": result["document_type"],
                    "summary": result["summary"],
                    "key_points": result["key_points"]
                },
                "extraction_quality": result["confidence"],
                "warnings": warnings,
                "model_used": self.vision_model
            }
            
        except Exception as e:
            # CHK007: Fail gracefully
            return {
                "extracted_text": "",
                "document_analysis": {
                    "document_type": "generic",
                    "summary": "Analysis failed",
                    "key_points": []
                },
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
    
    def _parse_enhanced_response(self, response_text: str) -> dict:
        """
        Parse enhanced AI response with text + document analysis.
        
        Expected format:
            TEXT:
            [extracted text]
            
            DOCUMENT_TYPE: [type]
            SUMMARY: [summary]
            KEY_POINTS:
            - [point 1]
            - [point 2]
            
            CONFIDENCE: high/medium/low
            NOTES: [optional notes]
        
        Args:
            response_text: Raw response from AI
            
        Returns:
            {
                "extracted_text": str,
                "document_type": str,
                "summary": str,
                "key_points": List[str],
                "confidence": str,
                "ai_notes": str
            }
        """
        # Default values
        result = {
            "extracted_text": response_text,
            "document_type": "generic",
            "summary": "",
            "key_points": [],
            "confidence": "medium",
            "ai_notes": ""
        }
        
        try:
            lines = response_text.split("\n")
            current_section = None
            text_lines = []
            key_points = []
            
            for line in lines:
                line_stripped = line.strip()
                
                if line_stripped.startswith("TEXT:"):
                    current_section = "text"
                    continue
                elif line_stripped.startswith("DOCUMENT_TYPE:"):
                    current_section = "doc_type"
                    doc_type = line_stripped.replace("DOCUMENT_TYPE:", "").strip().lower()
                    result["document_type"] = doc_type if doc_type else "generic"
                    continue
                elif line_stripped.startswith("SUMMARY:"):
                    current_section = "summary"
                    summary = line_stripped.replace("SUMMARY:", "").strip()
                    result["summary"] = summary
                    continue
                elif line_stripped.startswith("KEY_POINTS:"):
                    current_section = "key_points"
                    continue
                elif line_stripped.startswith("CONFIDENCE:"):
                    current_section = "confidence"
                    conf = line_stripped.replace("CONFIDENCE:", "").strip().lower()
                    result["confidence"] = conf if conf in ["high", "medium", "low"] else "medium"
                    continue
                elif line_stripped.startswith("NOTES:"):
                    current_section = "notes"
                    notes = line_stripped.replace("NOTES:", "").strip()
                    result["ai_notes"] = notes
                    continue
                
                # Accumulate content for current section
                if current_section == "text":
                    # Preserve empty lines for layout
                    text_lines.append(line)
                elif current_section == "summary" and line_stripped:
                    # Handle multi-line summary
                    if result["summary"]:
                        result["summary"] += " " + line_stripped
                    else:
                        result["summary"] = line_stripped
                elif current_section == "key_points":
                    if line_stripped.startswith("-") or line_stripped.startswith("•"):
                        point = line_stripped.lstrip("-•").strip()
                        if point:
                            key_points.append(point)
                elif current_section == "notes" and line_stripped:
                    # Handle multi-line notes
                    if result["ai_notes"]:
                        result["ai_notes"] += " " + line_stripped
                    else:
                        result["ai_notes"] = line_stripped
            
            # Set extracted text
            if text_lines:
                result["extracted_text"] = "\n".join(text_lines).strip()
            
            # Set key points
            if key_points:
                result["key_points"] = key_points
                
        except Exception:
            # If parsing fails, use defaults with raw text
            pass
        
        return result
    
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
