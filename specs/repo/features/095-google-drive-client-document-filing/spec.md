# Feature 095: Client Document Filing to Google Drive

**Feature Branch**: `feature/095-google-drive-client-document-filing`
**Status**: Backlog
**Dependency**: Blocked by Feature 063 (Dynamic Capability Backbone) and requires Google Drive Integration.

## 1. Business & Architectural Goals

Users frequently receive case-related documents via WhatsApp (evidence, ID cards, court rulings, letters) that are NOT fee agreements. Currently, DeniDin focuses exclusively on invoicing and financial ledgers.

**The Goal**: Allow the user to forward a document to the DeniDin WhatsApp bot with a message like "File this under [Client Name]", and have the bot automatically upload the document to a dedicated Google Drive folder for that client/case.

**Value**: Transforms DeniDin from a pure financial/ledger bot into a broader legal practice management and document routing assistant, saving massive administrative overhead.

## 2. PM Requirements (Functional)

- **REQ-095-01 (Drive Integration)**: Establish a secure connection to the Google Drive API (either natively or via an MCP server). The bot must have permissions to create folders and upload files.
- **REQ-095-02 (Folder Mapping)**: The system must map DeniDin `client_id` or resolved client names to specific Google Drive Folder IDs. If a client folder does not exist, the system MUST create it automatically under a master "DeniDin Clients" root folder.
- **REQ-095-03 (Media Handling)**: The system must successfully download the media payload from the WhatsApp API (handling various MIME types like PDF, JPEG, DOCX) and stream it to the Google Drive API without corrupting the file.
- **REQ-095-04 (Capability Backbone)**: This must be implemented as a new Capability Plugin (`document_filing_capability`) in the Feature 063 Backbone architecture. It should only load into the prompt when the user explicitly expresses intent to file or save a document.

## 3. User Acceptance Tests (UAT)

- **UAT-1 (Auto-Create Folder & File)**:
  - *Given* a client named "Avi Cohen" who does not yet have a Google Drive folder,
  - *When* the user forwards a PDF and says "File this to Avi Cohen's case",
  - *Then* the bot resolves the client, creates an "Avi Cohen" folder in Drive, uploads the PDF, and replies with a success confirmation and a link to the file.
- **UAT-2 (Existing Folder Routing)**:
  - *Given* a client named "Sarah Levi" who already has a mapped Drive folder,
  - *When* the user sends an image and says "Add this to Sarah's file",
  - *Then* the bot uploads the image directly to the existing folder without creating duplicates.
- **UAT-3 (Clarification Prompt)**:
  - *Given* the user sends a document with no caption,
  - *When* the bot processes the media,
  - *Then* the bot asks "What would you like me to do with this document? Are we filing it, or is it an agreement?"

## 4. Complexity & Open Questions

- **Google Drive Auth**: Are we using a Service Account (easier for backend scripts) or OAuth on behalf of the user? Service Accounts are highly recommended here to avoid token expiration issues, provided the Service Account shares the folder with the human lawyers.
- **File Naming**: Should the bot auto-rename the file based on the WhatsApp caption or content? (e.g., `whatsapp_image_123.jpg` vs `Avi_Cohen_ID_Card.jpg`). Auto-renaming adds significant value but requires vision/LLM extraction on the document itself.
