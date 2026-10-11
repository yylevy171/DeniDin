# User Stories: Google Drive Integration

## Stories

### User Story 1 - Save Document to Drive (Priority: P1)
**Given** the user sends a document or image to DeniDin
**When** the MediaHandler processes the file
**Then** the bot MUST upload the file to a designated Google Drive folder and return the Drive link.
**Integration Requirement**: Google Drive API integration required.

### User Story 2 - Retrieve from Drive (Priority: P2)
**Given** the user asks to find a past document
**When** the bot queries the semantic memory
**Then** it MUST provide the Google Drive link to the original document for easy access.
