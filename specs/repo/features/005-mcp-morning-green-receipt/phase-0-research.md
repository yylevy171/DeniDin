# Phase 0 Research: Morning API Investigation

**Date**: February 3, 2026
**Status**: IN PROGRESS
**Researcher**: AI Agent

## Findings

### 1. Company & Service Identification

- **Company**: Morning (מורנינג) / GreenInvoice (חשבונית ירוקה)
- **Website**: https://www.greeninvoice.co.il/ (morning.co.il redirects here)
- **Service**: Israeli digital invoicing and receipt management system
- **Market Position**: 165,000+ business users

### 2. API Existence: ✅ CONFIRMED

**Evidence**:
- API endpoint discovered: `https://api.greeninvoice.co.il/api/v1/`
- API version: GI-Core-API 2.38.18 (as of Feb 3, 2026)
- Page source references API documentation: "דוקומנטציית API ליצירת חיבורים מותאמים אישית עם מערכות חיצוניות"
- Link exists on website: https://www.greeninvoice.co.il/api-docs/

### 3. API Access Status: ⚠️ REQUIRES INVESTIGATION

**Current Status**:
- Public API documentation page exists but content not accessible via web scraping
- API endpoints respond (404 for /docs, suggests authentication required)
- Access-Control headers present, indicating CORS-enabled API

**Next Steps Required**:
1. Contact Morning/GreenInvoice developer support to request API documentation
2. Determine if API access requires:
   - Paid account tier
   - Developer registration
   - Business partnership
3. Obtain:
   - API authentication method (API key, OAuth2, etc.)
   - Available endpoints
   - Rate limits
   - Pricing/costs
   - Test/sandbox environment

### 4. Contact Information

- Website: https://www.greeninvoice.co.il/contact/
- Developer section exists: https://www.greeninvoice.co.il/api-docs/
- WhatsApp support mentioned on website

## Recommendations

**BLOCKER STATUS**: Phase 0 remains blocked until we:
1. ✅ Confirm API exists (DONE)
2. ❌ Obtain API documentation
3. ❌ Get test credentials
4. ❌ Verify available endpoints match our requirements

**Action Required**: Contact GreenInvoice developer support to request API access and documentation.

**Risk Assessment**:
- **LOW RISK**: API clearly exists and is in production use
- **MEDIUM RISK**: Documentation access method unclear
- **UNKNOWN**: API capabilities may not cover all planned features

## Questions for Support

1. How do we access the API documentation?
2. What authentication method is used (API key, OAuth2)?
3. Is there a sandbox/test environment?
4. What are the rate limits?
5. What is the pricing model for API access?
6. Are webhooks supported for real-time updates?
7. Does the API support Hebrew language responses?
8. Can invoices be sent via WhatsApp through the API?
