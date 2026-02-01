"""
End-to-End Integration Test: Real WhatsApp Message Flow

This is THE test that matters - simulates actual production behavior:
1. Receive webhook notification from Green API (real structure)
2. Download media from real URL (served via local HTTP server)
3. Process through full pipeline (AI, memory, etc.)
4. Send response via notification.answer()

NO MOCKING - Tests exactly what happens in production.

Run with: pytest tests/integration/test_whatsapp_e2e.py -m expensive -v
"""

import pytest
import logging
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote
from whatsapp_chatbot_python import Notification

from src.models.config import AppConfiguration

# Configure logging for tests
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@pytest.mark.expensive
class TestWhatsAppE2E:
    """
    End-to-end tests simulating real WhatsApp message flow.
    
    These tests use:
    - Real webhook notification structure
    - Real media files served via local HTTP server (simulates Green API URLs)
    - Real AI API calls
    - Real notification.answer() (tracked, not called to Green API)
    """
    
    @pytest.fixture(scope="class")
    def http_server(self):
        """
        Start local HTTP server to serve test media files.
        
        This simulates Green API's file download URLs.
        Files served from tests/fixtures/media/
        Properly handles URL-encoded paths (including Hebrew characters).
        """
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "media"
        
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(fixtures_dir), **kwargs)
            
            def translate_path(self, path):
                """Override to properly handle URL-encoded paths (Hebrew chars, etc)"""
                # Decode URL-encoded characters
                decoded_path = unquote(path)
                # Let parent handle the rest
                return super().translate_path(decoded_path)
            
            def log_message(self, format, *args):
                # Suppress HTTP server logs during tests
                pass
        
        server = HTTPServer(('127.0.0.1', 8765), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        
        logger.info(f"\n🌐 Test HTTP server running at http://127.0.0.1:8765/")
        logger.info(f"   Serving files from: {fixtures_dir}")
        
        yield "http://127.0.0.1:8765"
        
        server.shutdown()
    
    @pytest.fixture
    def config(self):
        """Load production configuration."""
        config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
        
        if not config_path.exists():
            pytest.skip("config.json not found")
        
        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        # Use production data_root to access the real constitution file
        config.data_root = str(Path(__file__).parent.parent.parent / "data")
        
        return config
    
    @pytest.fixture
    def denidin_app(self, config):
        """Initialize the full denidin app - NO MOCKING."""
        import denidin
        
        if denidin.denidin_app is None:
            config_dict = {
                'green_api_instance_id': config.green_api_instance_id,
                'green_api_token': config.green_api_token,
                'ai_api_key': config.ai_api_key,
                'ai_model': config.ai_model,
                'ai_reply_max_tokens': config.ai_reply_max_tokens,
                'temperature': config.temperature,
                'log_level': config.log_level,
                'data_root': config.data_root,
                'feature_flags': config.feature_flags,
                'godfather_phone': config.godfather_phone,
                'memory': config.memory,
                'constitution_config': config.constitution_config,
                'user_roles': config.user_roles
            }
            denidin.denidin_app = denidin.initialize_app(config_dict)
        
        return denidin.denidin_app
    
    def _create_real_notification(self, event_dict):
        """
        Create real SDK Notification object (not mocked).
        
        Tracks calls to answer() without actually calling Green API.
        """
        notification = Notification.__new__(Notification)
        notification.event = event_dict
        notification._test_sent_messages = []
        
        def track_answer(message):
            """Track what would be sent to user"""
            notification._test_sent_messages.append(message)
            logger.info(f"\n📤 Would send to user: {message}...")
        
        notification.answer = track_answer
        return notification
    
    def _get_response(self, notification):
        """Get the response that was sent to user."""
        return notification._test_sent_messages[0] if notification._test_sent_messages else None
    
    def _assert_response_exists(self, response):
        """Assert 0: Response exists and is not empty."""
        assert response is not None, "CRITICAL: User got NO RESPONSE (silent drop)"
        assert len(response) > 0, "User got empty response"
        # Should NOT be an error message (file downloaded successfully)
        assert "שגיאה" not in response and "נכשל" not in response, f"Got error: {response}"
    
    def _assert_hebrew_only(self, response):
        """Assert 1: Response must be in Hebrew only (>85% Hebrew chars)."""
        hebrew_chars = sum(1 for c in response if '\u0590' <= c <= '\u05FF')
        alpha_chars = [c for c in response if c.isalpha()]
        english_chars = sum(1 for c in alpha_chars if 'a' <= c.lower() <= 'z')
        hebrew_ratio = hebrew_chars / len(alpha_chars) if len(alpha_chars) > 0 else 0
        assert hebrew_ratio > 0.85, f"Response must be Hebrew only - found {english_chars} English chars, Hebrew ratio: {hebrew_ratio:.1%}\nFull Response: {response}"
        return hebrew_ratio
    
    def _assert_summary_exists(self, response):
        """Assert 2: Summary must exist with mandatory 'סיכום:' section (required by prompt)."""
        assert "סיכום:" in response, f"Response missing 'סיכום:' section (required by prompt)\nResponse: {response}"
    
    def _assert_metadata_bullets(self, response):
        """Assert 3: Metadata bullets must be present (• or -)."""
        assert '•' in response or '-' in response, f"Response missing metadata bullets - check if extractors are returning key_points\nResponse: {response}"
    
    def _assert_no_followups(self, response):
        """Assert 4: No follow-up questions (response is informational only)."""
        question_patterns = ['?', 'מה אני יכול', 'איך אני יכול', 'רוצה ש', 'צריך עזרה', 'what can', 'how can', 'need help']
        found_questions = [p for p in question_patterns if p.lower() in response.lower()]
        assert len(found_questions) == 0, f"Response should be informational only, found questions: {found_questions}\nResponse: {response}"
    
    def _validate_response(self, response):
        """Validate response against all 4 assertions and return hebrew_ratio for logging."""
        self._assert_response_exists(response)
        hebrew_ratio = self._assert_hebrew_only(response)
        self._assert_summary_exists(response)
        self._assert_metadata_bullets(response)
        self._assert_no_followups(response)
        return hebrew_ratio
    
    @pytest.mark.expensive
    def test_e2e_image_receipt_from_whatsapp(self, denidin_app, http_server):
        """
        **THE REAL TEST**: Complete flow from WhatsApp webhook to user response.
        
        Uses REAL WhatsApp image you provided.
        
        Flow:
        1. User sends image receipt via WhatsApp
        2. Green API sends webhook to our server
        3. Bot downloads image from real URL (via local HTTP server)
        4. Bot analyzes image with AI (REAL API CALL)
        5. Bot sends Hebrew summary back to user
        
        This tests EXACTLY what happens in production.
        """
        from denidin import handle_image_message
        
        # Real webhook notification from Green API
        # Download URL points to local HTTP server serving YOUR real WhatsApp image
        notification = self._create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1706601234,
            'idMessage': 'E2E_TEST_MSG_001',
            'instanceData': {
                'idInstance': 7103000000,
                'wid': '972501234567@c.us',
                'typeInstance': 'whatsapp'
            },
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User',
                'chatName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    # YOUR real WhatsApp image
                    'downloadUrl': f'{http_server}/WhatsApp%20Image%202025-11-18%20at%2021.51.25.jpeg',
                    'fileName': 'WhatsApp Image 2025-11-18 at 21.51.25.jpeg',
                    'mimeType': 'image/jpeg',
                    'caption': '',
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0
                }
            }
        })
        
        logger.info("\n" + "="*80)
        logger.info("🔥 E2E TEST: Real WhatsApp image from you")
        logger.info(f"   Download URL: {http_server}/WhatsApp%20Image%202025-11-18%20at%2021.51.25.jpeg")
        logger.info("="*80)
        
        # Execute the REAL handler with REAL file download and REAL AI call
        handle_image_message(notification)
        
        # Verify user got a response
        response = self._get_response(notification)
        
        # Log the FULL response without truncation
        logger.info(f"[test_e2e_image_receipt_from_whatsapp] Response length: {len(response)} chars")
        logger.info(f"[test_e2e_image_receipt_from_whatsapp] FULL RESPONSE:\n{response}")
        
        # Validate response against all 4 assertions
        hebrew_ratio = self._validate_response(response)
        logger.info(f"✅ SUCCESS - Hebrew ratio: {hebrew_ratio:.1%}, Has סיכום:, Has metadata bullets, No follow-up questions")
    
    @pytest.mark.expensive
    def test_e2e_hebrew_docx_from_whatsapp(self, denidin_app, http_server):
        """
        **E2E TEST**: Hebrew document processing (יובל יעקובי.docx).
        
        Flow:
        1. User sends Hebrew Word document via WhatsApp
        2. Green API sends webhook
        3. Bot downloads DOCX from real URL (via local HTTP server)
        4. Bot extracts text and analyzes with AI (REAL API CALL)
        5. Bot sends Hebrew summary
        """
        from denidin import handle_document_message
        
        # Real webhook notification
        notification = self._create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1706601234,
            'idMessage': 'E2E_TEST_MSG_002',
            'instanceData': {
                'idInstance': 7103000000,
                'wid': '972501234567@c.us',
                'typeInstance': 'whatsapp'
            },
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User',
                'chatName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'documentMessage',
                'fileMessageData': {
                    # YOUR real Hebrew document
                    'downloadUrl': f'{http_server}/%D7%99%D7%95%D7%91%D7%9C%20%D7%99%D7%A2%D7%A7%D7%95%D7%91%D7%99.docx',
                    'fileName': 'יובל יעקובי.docx',
                    'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'caption': '',
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0
                }
            }
        })
        
        logger.info("\n" + "="*80)
        logger.info("🔥 E2E TEST: Your Hebrew DOCX document (יובל יעקובי)")
        logger.info(f"   Download URL: {http_server}/יובל יעקובי.docx")
        logger.info("="*80)
        
        # Execute the REAL handler with REAL file download and REAL AI call
        handle_document_message(notification)
        
        # Verify user got a response
        response = self._get_response(notification)
        
        # Log the FULL response without truncation
        logger.info(f"[test_e2e_hebrew_docx_from_whatsapp] Response length: {len(response)} chars")
        logger.info(f"[test_e2e_hebrew_docx_from_whatsapp] FULL RESPONSE:\n{response}")
        
        # Validate response against all 4 assertions
        hebrew_ratio = self._validate_response(response)
        logger.info(f"✅ SUCCESS - Hebrew ratio: {hebrew_ratio:.1%}, Has סיכום:, Has metadata bullets, No follow-up questions")
    
    @pytest.mark.expensive
    def test_e2e_hebrew_pdf_from_you(self, denidin_app, http_server):
        """
        **E2E TEST**: Hebrew PDF document processing (רועי שדה הצעת שכט.pdf).
        
        Flow:
        1. User sends YOUR Hebrew PDF via WhatsApp
        2. Green API sends webhook
        3. Bot downloads PDF from real URL (via local HTTP server)
        4. Bot extracts text and analyzes with AI (REAL API CALL)
        5. Bot sends Hebrew summary
        """
        from denidin import handle_document_message
        
        # Real webhook notification
        notification = self._create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1706601234,
            'idMessage': 'E2E_TEST_MSG_003',
            'instanceData': {
                'idInstance': 7103000000,
                'wid': '972501234567@c.us',
                'typeInstance': 'whatsapp'
            },
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User',
                'chatName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'documentMessage',
                'fileMessageData': {
                    # YOUR real Hebrew PDF
                    'downloadUrl': f'{http_server}/%D7%A8%D7%95%D7%A2%D7%99%20%D7%A9%D7%93%D7%94%20%D7%94%D7%A6%D7%A2%D7%AA%20%D7%A9%D7%9B%D7%98.pdf',
                    'fileName': 'רועי שדה הצעת שכט.pdf',
                    'mimeType': 'application/pdf',
                    'caption': '',
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0
                }
            }
        })
        
        logger.info("\n" + "="*80)
        logger.info("🔥 E2E TEST: Your Hebrew PDF (רועי שדה הצעת שכט)")
        logger.info(f"   Download URL: {http_server}/רועי שדה הצעת שכט.pdf")
        logger.info("="*80)
        
        # Execute the REAL handler with REAL file download and REAL AI call
        handle_document_message(notification)
        
        # Verify user got a response
        response = self._get_response(notification)
        
        # Log the FULL response without truncation
        logger.info(f"[test_e2e_hebrew_pdf_from_you] Response length: {len(response)} chars")
        logger.info(f"[test_e2e_hebrew_pdf_from_you] FULL RESPONSE:\n{response}")
        
        # Validate response against all 4 assertions
        hebrew_ratio = self._validate_response(response)
        logger.info(f"✅ SUCCESS - Hebrew ratio: {hebrew_ratio:.1%}, Has סיכום:, Has metadata bullets, No follow-up questions")
    

# ==================== USAGE ====================
#
# This is THE test that validates production behavior.
# 
# Run with:
#   pytest tests/integration/test_whatsapp_e2e.py -m expensive -v -s
#
# Tests use:
# - Local HTTP server to serve real test files (simulates Green API URLs)
# - Real SDK Notification objects (no mocking)
# - Real file downloads via HTTP
# - Real AI API calls (costs ~$0.02-0.05 per test)
# - Real handler code paths
#
# If these tests pass, the system works in production.
#
# =============================================
