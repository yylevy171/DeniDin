# User Stories: Fee Agreement Document Generation

## Stories

### User Story 1 - The "One-Shot" Generation (Priority: P1)
**Given** the user provides all necessary details in a single prompt (e.g., "Draft a fee agreement for new client Avi Levi, fee is 5000 NIS for tax consultation")
**When** the AI processes the request
**Then** the AI MUST NOT ask unnecessary clarifying questions
**And** the AI MUST immediately invoke the document generation tool and send the finalized `.docx` file back to the user in the chat.

### User Story 2 - The Clarification Flow (Priority: P1)
**Given** the user provides partial information (e.g., "I need a fee agreement for Yossi")
**When** the AI realizes that mandatory template fields (like scope of work and fee amount) are missing
**Then** the AI MUST pause the generation and text the user asking for the specific missing fields
**And** upon receiving the answers, the AI MUST resume the flow and generate the document.

### User Story 3 - Editable Direct Delivery (Priority: P1)
**Given** the document generation engine has created the finalized fee agreement
**When** the system dispatches it to the user
**Then** the user MUST receive it directly inside WhatsApp as a standard document attachment
**And** the file MUST be in `.docx` format, allowing the user to open it on their phone/PC and make manual edits before forwarding it to their client.

### User Story 4 - Formatting Preservation (Priority: P2)
**Given** the system contains a branded `fee_agreement_template.docx` with bold headers, specific fonts, and bullet points
**When** the placeholders are dynamically replaced
**Then** the resulting output file MUST perfectly retain all the original branding and formatting surrounding the injected text.
