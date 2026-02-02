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
import logging
from src.models.media import Media
from src.handlers.extractors.base import MediaExtractor

logger = logging.getLogger(__name__)


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
    
    def analyze_media(self, media: Media, caption: str = "") -> Dict:
        """
        Analyze image using GPT-4o Vision (Phase 4 enhancement).
        
        Single AI call returns AI-generated analysis with:
        - Document summary (סיכום:)
        - Key points (נקודות חשובות:)
        - Document type and confidence
        - Full response formatted per prompt requirements
        
        CHK006-011: Hebrew text extraction with layout preservation.
        
        Args:
            media: Media object containing image data in memory
            caption: User's message/question sent with the image (optional)
            
        Returns:
            {
                "raw_response": str,  # Full unmodified AI response
                "extraction_quality": str,  # "high", "medium", "low", "failed"
                "warnings": List[str],
                "model_used": str  # e.g. "gpt-4o"
            }
        """
        try:
            # Load prompt template from external file
            prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / "image_analysis.txt"
            prompt_template = prompt_path.read_text(encoding='utf-8')
            
            # CHK027: Enhanced prompt for document analysis
            # Include user's caption/question for context (only if provided)
            user_context = f"\n\nUser's question/message: {caption}" if caption else ""
            addressing_note = " addressing the user's question" if caption else ""
            focusing_note = ", focusing on what the user asked about" if caption else ""
            
            # Format the prompt with context
            prompt = prompt_template.format(
                user_context=user_context,
                addressing_note=addressing_note,
                focusing_note=focusing_note
            )
            
            logger.info(f"[ImageExtractor.analyze_media] Exact prompt being sent ({len(prompt)} chars):")
            logger.info(f"[ImageExtractor.analyze_media] {prompt}")
            
            # Call Vision API with in-memory media (constitution prepended in _vision_extract)
            response = self._vision_extract(media, prompt)
            
            # Get raw response from AI - no parsing, pass it through as-is
            response_text = response.get("text", "")
            
            logger.info(f"[ImageExtractor.extract] Raw AI response ({len(response_text)} chars):")
            logger.info(f"[ImageExtractor.extract] {response_text}")
            
            return {
                "raw_response": response_text,
                "extraction_quality": "high",
                "warnings": [],
                "model_used": self.vision_model
            }
            
        except Exception as e:
            # CHK007: Fail gracefully
            return {
                "raw_response": "",
                "extraction_quality": "failed",
                "warnings": [f"Analysis failed: {str(e)}"],
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
        
        logger.debug(f"[ImageExtractor._vision_extract] Full prompt length: {len(full_prompt)} chars")
        logger.debug(f"[ImageExtractor._vision_extract] Constitution loaded: {bool(constitution)}")
        logger.debug(f"[ImageExtractor._vision_extract] Constitution preview: {constitution[:200] if constitution else 'NONE'}")
        
        # Get the data URL
        data_url = media.get_data_url()
        logger.info(f"[ImageExtractor._vision_extract] Media data URL length: {len(data_url)} chars")
        logger.info(f"[ImageExtractor._vision_extract] Media data URL preview: {data_url[:100]}...")
        logger.info(f"[ImageExtractor._vision_extract] Media file size: {media.size} bytes, MIME type: {media.mime_type}")
        
        # Call OpenAI Vision API with in-memory data URL
        logger.info(f"[ImageExtractor._vision_extract] Sending request to OpenAI Vision API")
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
                                "url": data_url
                            }
                        }
                    ]
                }
            ],
            max_tokens=self.config.ai_reply_max_tokens
        )
        
        raw_response = response.choices[0].message.content
        logger.info(f"[ImageExtractor._vision_extract] Raw OpenAI response ({len(raw_response)} chars):")
        logger.info(f"[ImageExtractor._vision_extract] {raw_response}")
        
        return {"text": raw_response}
    

