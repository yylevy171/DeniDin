# Feature Spec: MCP Integration with Morning Green Receipt

**Feature ID**: 005-mcp-morning-green-receipt
**Priority**: P2 (Medium)
**Status**: Planning
**Created**: January 17, 2026

## Problem Statement

Users want to interact with Morning's Green Receipt (חשבונית ירוקה) service through natural language via WhatsApp or other MCP clients. This includes creating invoices, checking invoice status, retrieving client information, and managing receipts.

**Desired Capabilities:**
- "Create an invoice for John Smith for 5000 NIS"
- "Show me all unpaid invoices this month"
- "What's the status of invoice #12345?"
- "Send invoice to client ABC Ltd"
- "Get my total revenue for Q4"

## Use Cases

1. **Invoice Creation**: "Create an invoice for consulting services, 3000 NIS for Acme Corp"
2. **Invoice Query**: "Show me all invoices from last week"
3. **Payment Tracking**: "Which invoices are still unpaid?"
4. **Client Management**: "Add a new client named Tech Solutions Ltd"
5. **Financial Reports**: "What's my total income for December 2025?"
6. **Document Retrieval**: "Get me the PDF for invoice #789"
7. **Status Updates**: "Did invoice #456 get paid?"
8. **Bulk Operations**: "Mark all invoices from November as paid"

## Background: Morning Green Receipt Service

**Company**: Morning (https://morning.co.il/)
**Product**: Green Receipt (חשבונית ירוקה)
**Purpose**: Israeli digital invoicing and receipt management system

**Key Features**:
- Digital invoice/receipt creation
- Client management
- Payment tracking
- Tax reporting (Israeli tax compliance)
- Document generation (PDF receipts)
- Business analytics

**API Access (canonical)**: See `endpoints.md` for canonical sandbox and production endpoints, file-upload endpoints, and caching APIs.

**Authentication**: JWT Bearer Token (obtained via API key)
**Rate Limit**: ~3 requests/second (429 status if exceeded) — clarify scope (per API key) and define client retry/backoff in implementation plan
**Webhook Support**: Yes - POST to callback URLs for async operations
**Language**: Full Hebrew support (error messages, fields, documentation all in Hebrew)

## Configuration

Per the project Constitution, ALL runtime configuration MUST be supplied via `config/config.json`. Do NOT use environment variables for application configuration or secrets. The implementation MUST read the configuration file at startup and validate it against the canonical schema in `specs/in-definition/005-mcp-morning-green-receipt/artifacts/config.schema.json`.

Example `config/config.json` (development/test template; never commit live secrets):

```json
{
    "morning": {
        "api_key_id": "PASTE_YOUR_TEST_API_KEY_ID_HERE",
        "api_key_secret": "PASTE_YOUR_TEST_API_KEY_SECRET_HERE",
        "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1/",
        "default_currency": "ILS",
        "default_vat_rate": 0.17,
        "token_ttl_seconds": 3600,
        "refresh_before_seconds": 300
    }
}
```

Security note: For CI and deployment, inject `config/config.json` from your organization's secret manager at deploy time; do not commit live secrets to the repository. DO NOT use environment variables for runtime configuration or secret storage — this repository's Constitution mandates all runtime config be supplied via `config/config.json`.


<!-- Duplicate Problem Statement and Use Cases removed to avoid drift. The canonical Problem Statement and Use Cases are maintained earlier in this file; if you need the original snapshot it was moved to `specs/archive/005-mcp-morning-green-receipt/merged_from_specs_005.md`. -->

## Background: Morning Green Receipt Service

**Company**: Morning (https://morning.co.il/)  
**Product**: Green Receipt (חשבונית ירוקה)  
**Purpose**: Israeli digital invoicing and receipt management system

**Key Features**:
- Digital invoice/receipt creation
- Client management
- Payment tracking
- Tax reporting (Israeli tax compliance)
- Document generation (PDF receipts)
- Business analytics

**API Access**: ✅ **CONFIRMED** - Morning provides REST API via Green Invoice
- **Status**: Public REST API exists and documented (https://greeninvoice.docs.apiary.io/)
- **Base URL**: https://api.greeninvoice.co.il/api/v1/
- **Sandbox URL**: https://sandbox.d.greeninvoice.co.il/api/v1/
- **Authentication**: JWT Bearer Token (obtained via API key)
- **Rate Limit**: ~3 requests/second (429 status if exceeded)
- **Webhook Support**: Yes - POST to callback URLs for async operations
- **Webhook Support (implementation decision)**: Deferred for initial rollout. We will NOT implement webhook handlers in Phase 1; instead, the MCP server will poll Morning endpoints for status updates. This simplifies deployment and avoids exposing callback URLs until webhook security and operations are validated.
- **Language**: Full Hebrew support (error messages, fields, documentation all in Hebrew)

- **Spec sections added / clarified**: appended this Checklist Resolution section and created clear TODO anchors in the spec for the following areas: auth/token refresh strategy (CHK001, CHK006, CHK042), rate limit and retry/backoff (CHK003, CHK038), webhook signature verification (CHK048) (DEFERRED), file upload flow and presigned URLs (CHK004), WhatsApp delivery behavior (CHK065-CHK071), testing requirements (CHK075-CHK085), and security requirements (CHK049-CHK054).
## Architecture

5. Defer webhook signature verification and webhook handler implementation to Phase 2; in Phase 1 implement polling for document status and webhook-like state (poll interval configurable in `config/config.json`).
6. Create `specs/in-definition/005-mcp-morning-green-receipt/test-plan.md` with detailed sandbox setup steps and sample test data to address CHK075-CHK084.
MCP Client (Claude Desktop, WhatsApp via DeniDin, etc.)
    ↓
MCP Protocol
    ↓
DeniDin MCP Server (Morning Integration)
    ↓
Morning API Client
    ↓
Morning Green Receipt API
    ↓
Morning Platform
```

## Technical Design

### 1. MCP Server Structure

```
denidin-mcp-morning/
├── pyproject.toml
├── README.md
├── src/
│   └── denidin_mcp_morning/
│       ├── __init__.py
│       ├── server.py           # Main MCP server
│       ├── tools.py            # MCP tool definitions
│       ├── morning_client.py   # Morning API client
│       ├── models.py           # Data models (Invoice, Client, etc.)
│       └── formatters.py       # Response formatting
└── tests/
    └── test_server.py
```

### 2. MCP Tools (Proposed)

#### Tool 1: `create_invoice`

```python
{
    "name": "create_invoice",
    "description": "Create a new invoice/receipt in Morning Green Receipt system",
    "inputSchema": {
        "type": "object",
        "properties": {
            "client_name": {
                "type": "string",
                "description": "Client name or ID"
            },
            "amount": {
                "type": "number",
                "description": "Invoice amount in NIS"
            },
            "description": {
                "type": "string",
                "description": "Service/product description"
            },
            "due_date": {
                "type": "string",
                "description": "Payment due date (YYYY-MM-DD)",
                "format": "date"
            },
            "vat_included": {
                "type": "boolean",
                "description": "Whether VAT is included in amount",
                "default": true
            }
        },
        "required": ["client_name", "amount", "description"]
    }
}
```

#### Tool 2: `list_invoices`

```python
{
    "name": "list_invoices",
    "description": "List invoices with optional filters",
    "inputSchema": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["paid", "unpaid", "overdue", "all"],
                "description": "Filter by payment status"
            },
            "from_date": {
                "type": "string",
                "format": "date",
                "description": "Start date (YYYY-MM-DD)"
            },
            "to_date": {
                "type": "string",
                "format": "date",
                "description": "End date (YYYY-MM-DD)"
            },
            "client_name": {
                "type": "string",
                "description": "Filter by client name"
            }
        }
    }
}
```

#### Tool 3: `get_invoice_details`

```python
{
    "name": "get_invoice_details",
    "description": "Get detailed information about a specific invoice",
    "inputSchema": {
        "type": "object",
        "properties": {
            "invoice_id": {
                "type": "string",
                "description": "Invoice ID or number"
            }
        },
        "required": ["invoice_id"]
    }
}
```

#### Tool 4: `update_invoice_status`

```python
{
    "name": "update_invoice_status",
    "description": "Update invoice payment status",
    "inputSchema": {
        "type": "object",
        "properties": {
            "invoice_id": {
                "type": "string",
                "description": "Invoice ID"
            },
            "status": {
                "type": "string",
                "enum": ["paid", "unpaid", "cancelled"],
                "description": "New status"
            },
            "payment_date": {
                "type": "string",
                "format": "date",
                "description": "Date payment was received"
            }
        },
        "required": ["invoice_id", "status"]
    }
}
```

#### Tool 5: `add_client`

```python
{
    "name": "add_client",
    "description": "Add a new client to Morning system",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Client/company name"
            },
            "email": {
                "type": "string",
                "format": "email",
                "description": "Client email"
            },
            "phone": {
                "type": "string",
                "description": "Client phone number"
            },
            "tax_id": {
                "type": "string",
                "description": "Israeli business tax ID (ע\"מ)"
            },
            "address": {
                "type": "string",
                "description": "Client address"
            }
        },
        "required": ["name"]
    }
}
```

#### Tool 6: `get_financial_summary`

```python
{
    "name": "get_financial_summary",
    "description": "Get financial summary and reports",
    "inputSchema": {
        "type": "object",
        "properties": {
            "period": {
                "type": "string",
                "enum": ["month", "quarter", "year", "custom"],
                "description": "Reporting period"
            },
            "from_date": {
                "type": "string",
                "format": "date",
                "description": "Start date for custom period"
            },
            "to_date": {
                "type": "string",
                "format": "date",
                "description": "End date for custom period"
            }
        },
        "required": ["period"]
    }
}
```

#### Tool 7: `send_invoice`

```python
{
    "name": "send_invoice",
    "description": "Send invoice to client via WhatsApp",
    "inputSchema": {
        "type": "object",
        "properties": {
            "invoice_id": {
                "type": "string",
                "description": "Invoice ID"
            },
            "phone_number": {
                "type": "string",
                "description": "Recipient phone number (optional if client has phone)"
            },
            "message": {
                "type": "string",
                "description": "Optional message to include"
            }
        },
        "required": ["invoice_id"]
    }
}
```

#### Tool 8: `download_invoice_pdf`

```python
{
    "name": "download_invoice_pdf",
    "description": "Get PDF download URL for an invoice",
    "inputSchema": {
        "type": "object",
        "properties": {
            "invoice_id": {
                "type": "string",
                "description": "Invoice ID"
            }
        },
        "required": ["invoice_id"]
    }
}
```

### 3. Morning API Client

```python
# src/denidin_mcp_morning/morning_client.py

class MorningClient:
    """Client for Morning Green Receipt API."""
    
    def __init__(self, api_key: str, base_url: str = "https://sandbox.d.greeninvoice.co.il/api/v1/"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
    
    def create_invoice(
        self,
        client_id: str,
        amount: float,
        description: str,
        **kwargs
    ) -> dict:
        """Create a new invoice."""
        payload = {
            "client_id": client_id,
            "amount": amount,
            "description": description,
            "currency": "ILS",
            **kwargs
        }
        response = self.session.post(f"{self.base_url}/invoices", json=payload)
        response.raise_for_status()
        return response.json()
    
    def list_invoices(
        self,
        status: str = None,
        from_date: str = None,
        to_date: str = None
    ) -> List[dict]:
        """List invoices with filters."""
        params = {}
        if status:
            params["status"] = status
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
            
        response = self.session.get(f"{self.base_url}/invoices", params=params)
        response.raise_for_status()
        return response.json()["invoices"]
    
    def get_invoice(self, invoice_id: str) -> dict:
        """Get invoice details."""
        response = self.session.get(f"{self.base_url}/invoices/{invoice_id}")
        response.raise_for_status()
        return response.json()
    
    def update_invoice_status(
        self,
        invoice_id: str,
        status: str,
        payment_date: str = None
    ) -> dict:
        """Update invoice payment status."""
        payload = {"status": status}
        if payment_date:
            payload["payment_date"] = payment_date
            
        response = self.session.patch(
            f"{self.base_url}/invoices/{invoice_id}",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def add_client(self, name: str, **kwargs) -> dict:
        """Add a new client."""
        payload = {"name": name, **kwargs}
        response = self.session.post(f"{self.base_url}/clients", json=payload)
        response.raise_for_status()
        return response.json()
    
    def search_clients(self, query: str) -> List[dict]:
        """Search for clients by name."""
        response = self.session.get(
            f"{self.base_url}/clients/search",
            params={"q": query}
        )
        response.raise_for_status()
        return response.json()["clients"]
    
    def get_financial_summary(
        self,
        from_date: str,
        to_date: str
    ) -> dict:
        """Get financial summary for period."""
        response = self.session.get(
            f"{self.base_url}/reports/summary",
            params={"from": from_date, "to": to_date}
        )
        response.raise_for_status()
        return response.json()
    
    def send_invoice_whatsapp(
        self,
        invoice_id: str,
        phone_number: str = None,
        message: str = None
    ) -> dict:
        """Send invoice to client via WhatsApp."""
        payload = {}
        if phone_number:
            payload["phone_number"] = phone_number
        if message:
            payload["message"] = message
            
        response = self.session.post(
            f"{self.base_url}/invoices/{invoice_id}/send",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_invoice_pdf_url(self, invoice_id: str) -> str:
        """Get PDF download URL."""
        response = self.session.get(
            f"{self.base_url}/invoices/{invoice_id}/pdf"
        )
        response.raise_for_status()
        return response.json()["pdf_url"]
```

### 4. Data Models

```python
# src/denidin_mcp_morning/models.py

from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class Client(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    created_at: datetime

class Invoice(BaseModel):
    id: str
    invoice_number: str
    client_id: str
    client_name: str
    amount: float
    currency: str = "ILS"
    description: str
    status: str  # 'paid', 'unpaid', 'overdue', 'cancelled' - status determined by Morning API, not locally
    issue_date: date
    due_date: Optional[date] = None
    payment_date: Optional[date] = None
    vat_amount: Optional[float] = None
    total_amount: float
    pdf_url: Optional[str] = None

class FinancialSummary(BaseModel):
    period_start: date
    period_end: date
    total_invoiced: float
    total_paid: float
    total_unpaid: float
    invoice_count: int
    paid_invoice_count: int
    unpaid_invoice_count: int
    average_invoice_amount: float
```

## Configuration

### Configuration

Per the repository Constitution, ALL runtime configuration MUST be supplied via `config/config.json`. Do not rely on environment variables for application configuration or secrets. For CI and deployment, inject `config/config.json` from your organization's secret manager at deploy time — do not commit live secrets.

Example `config/config.json` (development/test template; never commit live secrets):

```json
{
    "morning": {
        "api_key": "PASTE_YOUR_TEST_API_KEY_HERE",
        "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1/",
        "default_currency": "ILS",
        "default_vat_rate": 0.17,
        "token_ttl_seconds": 3600,
        "refresh_before_seconds": 300
    }
}
```

## Implementation Plan

### Phase 0: Research & Setup
- [ ] Research Morning API documentation
- [ ] Obtain API credentials (test account)
- [ ] Understand API authentication mechanism
- [ ] Map API endpoints to features
- [ ] Test basic API calls

### Phase 1: Core Invoice Operations
- [ ] Set up MCP server project
- [ ] Implement `create_invoice` tool
- [ ] Implement `list_invoices` tool
- [ ] Implement `get_invoice_details` tool
- [ ] Test invoice creation and retrieval

### Phase 2: Invoice Management
- [ ] Implement `update_invoice_status` tool
- [ ] Implement `send_invoice` tool (WhatsApp delivery via phone number)
- [ ] Implement `download_invoice_pdf` tool
- [ ] Add error handling for API failures and missing phone numbers

### Phase 3: Client Management
- [ ] Implement `add_client` tool
- [ ] Add client search/resolution with fuzzy matching
- [ ] Handle client name disambiguation - display all matches with IDs and ask user to select

### Client resolution workflow (authoritative decision)
The system MUST follow this exact workflow when resolving or creating clients. The user will never provide a `client_id`; resolutions are always by provided attributes (name, phone, email, tax_id, etc.).

- 1) Interpret user input: parse the user's free-text input and extract candidate identifiers (name, phone, email). Use the project's vector/index store (Chroma DB) to help classify the input type and normalize tokens before searching.
- 2) Search Morning: perform a fuzzy search against Morning `GET /clients/search` and local cache using a tokenized + fuzzy matching strategy (do not rely on exact match only). Combine exact and fuzzy matches, rank by confidence.
- 3) Clarify with user: if multiple plausible matches or low-confidence match, present the top N choices (with brief distinguishing fields) and ask the user to confirm by number or provide more details. Repeat until the client details are clear.
- 4) ALWAYS require user confirmation before any non-read Morning action (create, update, delete, send). The confirmation must be explicit (user types `yes`, selects a confirmation button, or replies with the chosen client ID/number).
- 5) If a match is found but missing fields needed for the requested operation (e.g., missing phone for WhatsApp delivery), ask the user to supply the missing field(s). When the user supplies new data and agrees to persist it, show an exact summary: `Update client ID 123: phone from "<old>" to "<new>"` and require explicit confirmation before calling Morning to update.
- 6) If no client exists (search returned none), show the EXACT details you will create and require confirmation: `Create new client: name="X", phone="Y", email="Z"` before calling `POST /clients`.
- 7) After any create/update action is confirmed and executed, echo the authoritative Morning `client_id` and the final canonical client record to the user.

Notes:
- Use Chroma DB to improve matching for noisy user text and to store canonical normalized tokens for local cache entries.
- Fuzzy matching must be tuned in tests; prefer human-in-the-loop confirmation instead of automatic selection when confidence < 0.9.
- Persisted updates to client records must be auditable and only executed after explicit user confirmation.

### Phase 4: Financial Reports
- [ ] Implement `get_financial_summary` tool
- [ ] Add date range helpers (this month, last quarter, etc.)
- [ ] Format financial data for readability

### Phase 5: WhatsApp Integration
- [ ] Integrate with DeniDin WhatsApp bot
- [ ] Support invoice creation via WhatsApp
- [ ] Send invoice PDFs via WhatsApp
- [ ] Invoice status notifications

## Usage Examples

### Example 1: Create Invoice
```
User (via MCP): 
"Create an invoice for Tech Corp, 5000 NIS for consulting services"

MCP Tool Call:
create_invoice(
  client_name="Tech Corp",
  amount=5000,
  description="Consulting services"
)

Response:
"✅ Invoice #INV-2026-001 created for Tech Corp
Amount: ₪5,000.00 (incl. VAT)
Status: Unpaid
PDF: [download link]"
```

### Example 2: Check Unpaid Invoices
```
User: "Show me all unpaid invoices from this month"

MCP Tool Call:
list_invoices(
  status="unpaid",
  from_date="2026-01-01",
  to_date="2026-01-31"
)

Response:
"📋 Unpaid Invoices (January 2026):
1. INV-001 - Tech Corp - ₪5,000 (due Jan 25)
2. INV-003 - ABC Ltd - ₪2,500 (due Jan 30)
Total unpaid: ₪7,500"
```

### Example 3: Financial Summary
```
User: "What's my total revenue for Q4 2025?"

MCP Tool Call:
get_financial_summary(
  period="quarter",
  from_date="2025-10-01",
  to_date="2025-12-31"
)

Response:
"💰 Q4 2025 Financial Summary:
Total Invoiced: ₪125,000
Total Paid: ₪105,000
Total Unpaid: ₪20,000
Invoices: 24 (20 paid, 4 unpaid)
Average: ₪5,208 per invoice"
```

### Example 4: Send Invoice (WhatsApp Integration)
```
User (via WhatsApp): "Send invoice #INV-001 to the client"

Bot → MCP Tool Call:
send_invoice(invoice_id="INV-001")

Response:
"✅ Invoice INV-001 sent via WhatsApp to +972-50-1234567
Client: Tech Corp
Status: Delivered"
```

## Security Considerations

- **API Key Protection**: Store in environment variables, never commit
- **Rate Limiting**: Respect Morning API rate limits
- **Data Privacy**: Handle client information securely
- **Audit Trail**: Log all invoice operations
- **Authorization**: Validate user permissions for financial operations
- **Input Validation**: Sanitize all amounts and descriptions

## Testing Strategy

### Unit Tests
- Invoice creation with various parameters
- Client search and resolution
- Date range calculations
- Amount formatting (NIS, VAT)
- Error handling

### Integration Tests
- End-to-end invoice creation via API
- Invoice status updates
- Client management operations
- Financial report generation

### Manual Testing
1. Create invoice for new client
2. Update invoice to paid status
3. Generate monthly financial report
4. Send invoice via email
5. Download invoice PDF

## Success Metrics

- ✅ Successfully create and manage invoices
- ✅ Accurate financial calculations (VAT, totals)
- ✅ <3 second response time for queries
- ✅ 95%+ API call success rate
- ✅ Proper error handling and user feedback
- ✅ 85%+ test coverage

## Error Handling

| Error | User Message |
|-------|--------------||
| API authentication failed | "❌ Morning API authentication failed. Check API key." |
| Client not found | "❌ Client 'X' not found. Would you like to add them?" |
| Multiple clients match | "❓ Multiple clients match 'X':\n1. Tech Corp Ltd (ID: 123)\n2. Tech Corp Inc (ID: 456)\nReply with the number or ID to select." |
| Client missing phone | "❌ Client has no phone number. Please provide: send invoice to [phone number]" |
| Invalid amount | "❌ Invalid amount. Please use format: 1000 or 1000.50" |
| API rate limit | "❌ Too many requests. Please try again in 1 minute." |
| Network error | "❌ Unable to connect to Morning API. Check connection." |

## Cost Implications

- **Morning API**: Check Morning's pricing for API usage
- **Storage**: Minimal (only caching client data)
- **Compute**: Minimal (MCP server runs locally)

## Hebrew Language Support

Since Morning is an Israeli service, all invoice responses will be in Hebrew:
- Support Hebrew client names (e.g., "חברת הייטק בע״מ")
- All user-facing messages in Hebrew
- Hebrew currency symbol (₪)
- Support Hebrew invoice descriptions
- Date formatting: DD/MM/YYYY (Israeli standard)
- Status messages in Hebrew (שולם, לא שולם, פג תוקף, בוטל)

```python
def format_invoice_response_hebrew(invoice: Invoice) -> str:
    return f"""
חשבונית #{invoice.invoice_number}
לקוח: {invoice.client_name}
סכום: ₪{invoice.amount:,.2f}
סטטוס: {translate_status(invoice.status)}
תאריך יעד: {invoice.due_date.strftime('%d/%m/%Y')}
"""
```

## Future Enhancements

- **Recurring Invoices**: "Create monthly invoice for Client X"
- **Expense Tracking**: Add expense management
- **Tax Reports**: Generate quarterly tax reports
- **Payment Reminders**: Auto-remind clients of overdue invoices
- **Multi-Currency**: Support USD, EUR (if Morning supports)
- **Batch Operations**: "Mark all December invoices as paid"
- **Invoice Templates**: Pre-defined templates for common services
- **Analytics Dashboard**: Visualize revenue trends
- **Integration with Accounting**: Sync with Israeli accounting software

## Dependencies on Other Features

- **Required**: Feature 004 (MCP WhatsApp Server) - For sending invoices via WhatsApp
- **Optional**: Feature 003 (Media Processing) - Attach invoice PDFs to WhatsApp

## Research Checklist

**CRITICAL - Phase 0 Blockers** (Must complete before any implementation):
- [x] Morning API documentation availability - **✅ CONFIRMED: Public REST API with full documentation**
- [x] API authentication method - **✅ JWT Bearer Token via API key**
- [x] Available endpoints and features - **✅ Documented (see api-documentation.md)**
- [x] Rate limits and quotas - **✅ ~3 requests/second**
- [x] Webhook support - **✅ Yes, for async operations**
- [x] Test/sandbox environment - **✅ Yes, separate sandbox with own API key**
- [x] API pricing/costs - **✅ Access requires "Best" subscription or higher**
- [x] Hebrew language support in API - **✅ Full Hebrew support**

**Phase 0 Status**: ✅ COMPLETE - API is production-ready and well-documented

### Key Findings from API Research

**Endpoints Mapping to MCP Tools**:
1. `create_invoice` → POST /documents (type: 305 for invoice, 320 for receipt)
2. `list_invoices` → POST /documents/search (with filters in JSON body)
3. `get_invoice_details` → GET /documents/{id}
4. `update_invoice_status` → PUT /documents/{id} (open/close)
5. `add_client` → POST /clients
6. `get_financial_summary` → POST /documents/search (aggregate results via aggregation in JSON body)
7. `send_invoice` → PUT /documents/{id} + POST to email/WhatsApp (via DeniDin integration)
8. `download_invoice_pdf` → GET /documents/{id}/preview (returns Base64 PDF)
```python
# src/denidin_mcp_morning/morning_client.py

class MorningClient:
    """Client for Morning Green Receipt API that accepts API key id+secret and exchanges them for a JWT.
    Uses POST /documents/search for document search endpoints (per Postman collection).
    """

    def __init__(self, api_key: str = None, api_key_id: str = None, api_key_secret: str = None, base_url: str = "https://sandbox.d.greeninvoice.co.il/api/v1/"):
        # Accept either a single api_key or the id/secret pair; use an Auth helper to obtain JWTs.
        self.api_key = api_key
        self.api_key_id = api_key_id
        self.api_key_secret = api_key_secret
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.auth = Auth(api_key=api_key, api_key_id=api_key_id, api_key_secret=api_key_secret, base_url=self.base_url)

    def list_invoices(self, filters: dict = None) -> dict:
        """List invoices — POSTs to /documents/search with filters in JSON body (Postman canonical).
        Returns the parsed JSON response.
        """
        url = f"{self.base_url}/documents/search"
        token = self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = filters or {}
        response = self.session.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    # Other methods should also use the token from self.auth and follow Postman shapes.
``` 

