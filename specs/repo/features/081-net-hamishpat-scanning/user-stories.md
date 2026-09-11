# User Stories: Net Hamishpat Scanning

## Stories

### User Story 1 - Direct Case Scanning (Priority: P1)
**Given** a Godfather/Admin provides a case number (מספר הליך)
**When** the bot processes the request
**Then** it MUST query or scan Net Hamishpat for updates or decisions on that case
**And** report the findings back in the Customer Engagement context.
**Integration Requirement**: Requires a new MCP tool or scraping integration for Net Hamishpat.

### User Story 2 - Automated Decision Parsing (Priority: P2)
**Given** the bot scans a new court resolution document
**When** the document is fetched
**Then** the AI MUST parse the key dates, entities, and outcomes using the existing Document Analysis Format.
