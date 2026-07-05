# Test Media Fixtures

This directory contains real test documents for integration testing.

## Files

### Generated Test Documents (Hebrew RTL)

1. **contract_peter_adam.pdf** - Generated contract (Hebrew RTL)
   - Client: פיטר אדם (Peter Adam)
   - Amount: 20,000 ש"ח
   - Payment due: 29 בינואר 2026
   - Used for: UC1, UC3a, UC4 tests

2. **contract_peter_adam.docx** - Same contract in DOCX format
   - Used for: UC3b test

3. **document_no_client.pdf** - Generic proposal without client info
   - Used for: UC5 test (missing identification prompt)

4. **receipt_cafe.jpg** - Generated cafe receipt (Hebrew RTL)
   - Used for: UC3c test

5. **unsupported.mp3** - Audio file for rejection testing
   - Used for: UC2 test

### Real-World Documents

1. **WhatsApp Image 2025-11-18 at 21.51.25.jpeg** - Real WhatsApp image
2. **WhatsApp Image 2025-11-24 at 13.30.28.jpeg** - Real WhatsApp image  
3. **WhatsApp Image 2026-01-13 at 18.01.21.jpeg** - Real WhatsApp image
4. **יובל יעקובי.docx** - Real Hebrew DOCX document
5. **רועי שדה הצעת שכט.pdf** - Real Hebrew PDF document

These real documents can be used for additional testing and validation.

### Text Templates

- **contract_peter_adam.txt** - Source template for PDF/DOCX generation
- **document_no_client.txt** - Source template for no-client document

## Regenerating Documents

To regenerate the test documents from templates:

```bash
cd denidin-app
python3 scripts/generate_test_fixtures.py
python3 scripts/generate_receipt_image.py
```

## Notes

- All generated documents use Hebrew with proper RTL (right-to-left) layout
- Real documents added manually provide realistic test cases
- Contract dates and amounts must match test assertions in integration tests
