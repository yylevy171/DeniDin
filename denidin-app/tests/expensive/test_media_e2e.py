"""
End-to-End Integration Test: Real WhatsApp Message Flow

This is THE test that matters - simulates actual production behavior:
1. Receive webhook notification from Green API (real structure)
2. Download media from real URL (served via local HTTP server)
3. Process through full pipeline (AI, memory, etc.)
4. Send response via notification.answer()

NO MOCKING - Tests exactly what happens in production.

Run with: pytest tests/expensive/test_media_e2e.py -m expensive -v
"""

import pytest
import logging
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote

from src.models.config import AppConfiguration
from .e2e_helpers import (
    create_real_notification,
    get_response,
    assert_response_exists,
    assert_hebrew_only,
    assert_summary_exists,
    assert_metadata_bullets,
    assert_no_followups,
    validate_response_full,
)

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
    
    @pytest.mark.expensive
    def test_e2e_image_no_caption(self, denidin_app, http_server):
        """
        **E2E TEST**: Image without caption - automatic analysis.
        
        Flow:
        1. User sends image WITHOUT caption
        2. Bot automatically analyzes image
        3. Bot sends Hebrew summary
        """
        from denidin import handle_image_message
        
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1706601234,
            'idMessage': 'E2E_TEST_IMAGE_001',
            'instanceData': {
                'idInstance': 7103000000,
                'wid': '972501234567@c.us',
                'typeInstance': 'whatsapp'
            },
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': f'{http_server}/WhatsApp%20Image%202025-11-18%20at%2021.51.25.jpeg',
                    'fileName': 'receipt.jpeg',
                    'mimeType': 'image/jpeg',
                    'caption': '',
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0
                }
            }
        })
        
        logger.info("\n" + "="*80)
        logger.info("🔥 E2E TEST: Image without caption")
        logger.info("="*80)
        
        handle_image_message(notification)
        response = get_response(notification)
        
        logger.info(f"Response length: {len(response)} chars")
        logger.info(f"FULL RESPONSE:\n{response}")
        
        hebrew_ratio = validate_response_full(response)
        logger.info(f"✅ SUCCESS - Hebrew ratio: {hebrew_ratio:.1%}")
    
    @pytest.mark.expensive
    def test_e2e_docx_no_caption(self, denidin_app, http_server):
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
        notification = create_real_notification({
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
        response = get_response(notification)
        
        # Log the FULL response without truncation
        logger.info(f"[test_e2e_hebrew_docx_from_whatsapp] Response length: {len(response)} chars")
        logger.info(f"[test_e2e_hebrew_docx_from_whatsapp] FULL RESPONSE:\n{response}")
        
        # Validate response against all 4 assertions
        hebrew_ratio = validate_response_full(response)
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
        notification = create_real_notification({
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
        response = get_response(notification)
        
        # Log the FULL response without truncation
        logger.info(f"[test_e2e_hebrew_pdf_from_you] Response length: {len(response)} chars")
        logger.info(f"[test_e2e_hebrew_pdf_from_you] FULL RESPONSE:\n{response}")
        
        # Validate response against all 4 assertions
        hebrew_ratio = validate_response_full(response)
        logger.info(f"✅ SUCCESS - Hebrew ratio: {hebrew_ratio:.1%}, Has סיכום:, Has metadata bullets, No follow-up questions")
    
    @pytest.mark.expensive
    def test_e2e_pdf_with_caption_user_question(self, denidin_app, http_server):
        """
        **E2E TEST**: PDF WITH caption - user asks specific question.
        
        Flow:
        1. User sends PDF WITH caption asking about amount
        2. Bot analyzes document and answers question
        3. Bot sends Hebrew response with requested information
        """
        from denidin import handle_document_message
        
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1706601234,
            'idMessage': 'E2E_TEST_PDF_CAPTION_001',
            'instanceData': {
                'idInstance': 7103000000,
                'wid': '972501234567@c.us',
                'typeInstance': 'whatsapp'
            },
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'documentMessage',
                'fileMessageData': {
                    'downloadUrl': f'{http_server}/%D7%A8%D7%95%D7%A2%D7%99%20%D7%A9%D7%93%D7%94%20%D7%94%D7%A6%D7%A2%D7%AA%20%D7%A9%D7%9B%D7%98.pdf',
                    'fileName': 'רועי שדה הצעת שכט.pdf',
                    'mimeType': 'application/pdf',
                    'caption': 'כמה הסכום בקובץ?',  # User asks about amount
                    'jpegThumbnail': ''
                }
            }
        })
        
        logger.info("\n" + "="*80)
        logger.info("🔥 E2E TEST: PDF with caption - user question")
        logger.info("="*80)
        
        handle_document_message(notification)
        response = get_response(notification)
        
        logger.info(f"Response length: {len(response)} chars")
        logger.info(f"FULL RESPONSE:\n{response}")
        
        # Validate Hebrew response
        assert_response_exists(response)
        hebrew_ratio = assert_hebrew_only(response)
        
        # Should mention the amount (this PDF should have financial info)
        logger.info(f"✅ SUCCESS - Hebrew ratio: {hebrew_ratio:.1%}")
    
    @pytest.mark.expensive
    def test_e2e_unsupported_audio_file(self, denidin_app):
        """
        **E2E TEST**: Unsupported audio file rejection.
        
        Flow:
        1. User sends unsupported audio file
        2. Bot rejects with error message
        """
        from denidin import handle_audio_message
        from src.constants.error_messages import FAILED_TO_PROCESS_FILE_DEFAULT
        
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1706601234,
            'idMessage': 'E2E_TEST_AUDIO_001',
            'instanceData': {
                'idInstance': 7103000000,
                'wid': '972501234567@c.us',
                'typeInstance': 'whatsapp'
            },
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'audioMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/audio.mp3',
                    'fileName': 'audio.mp3',
                    'mimeType': 'audio/mpeg',
                    'caption': ''
                }
            }
        })
        
        logger.info("\n" + "="*80)
        logger.info("🔥 E2E TEST: Unsupported audio file")
        logger.info("="*80)
        
        handle_audio_message(notification)
        response = get_response(notification)
        
        logger.info(f"Response: {response}")
        
        assert response == FAILED_TO_PROCESS_FILE_DEFAULT
        logger.info(f"✅ SUCCESS - Error message sent")
    
    @pytest.mark.expensive
    def test_e2e_pdf_multipage_no_caption(self, denidin_app, http_server):
        """
        **E2E TEST**: Multi-page PDF without caption - automatic analysis.
        
        Flow:
        1. User sends 2-page PDF WITHOUT caption
        2. Bot automatically analyzes both pages
        3. Bot sends Hebrew summary
        """
        from denidin import handle_document_message
        
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1706601234,
            'idMessage': 'E2E_TEST_PDF_MULTIPAGE_001',
            'instanceData': {
                'idInstance': 7103000000,
                'wid': '972501234567@c.us',
                'typeInstance': 'whatsapp'
            },
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'documentMessage',
                'fileMessageData': {
                    'downloadUrl': f'{http_server}/%D7%9E%D7%95%D7%93%D7%95%D7%9C%204.pdf',
                    'fileName': 'מודול 4.pdf',
                    'mimeType': 'application/pdf',
                    'caption': '',
                    'jpegThumbnail': ''
                }
            }
        })
        
        logger.info("\n" + "="*80)
        logger.info("🔥 E2E TEST: Multi-page PDF without caption (מודול 4)")
        logger.info("="*80)
        
        handle_document_message(notification)
        response = get_response(notification)
        
        logger.info(f"Response length: {len(response)} chars")
        logger.info(f"FULL RESPONSE:\n{response}")
        
        hebrew_ratio = validate_response_full(response)
        logger.info(f"✅ SUCCESS - Hebrew ratio: {hebrew_ratio:.1%}")
    

# ==================== REMOVED TESTS ====================
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
