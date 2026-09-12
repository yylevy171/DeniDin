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

## User Experience Testing Scenarios (UAT)

To ensure smooth operation and strict adherence to the anti-hallucination constraints, developers must manually verify the following scenarios:

### Scenario A: Zero-Turn Direct Generation
**Goal**: Verify the AI can fulfill a complete request without unnecessarily nagging the user.
- **T=0**: User texts: *"Create a retainer agreement for NewCo Ltd. Fee is 5,000 NIS monthly for general consulting."*
- **T+1**: AI recognizes all mandatory fields are present. It selects the "Retainer" template variant based on historical prod media.
- **T+X**: AI generates and dispatches the `.docx` file natively in WhatsApp.
- **Expectation**: No clarifying questions are asked. The file is downloadable directly from the WhatsApp chat.

### Scenario B: Anti-Hallucination Guardrail (Missing Data)
**Goal**: Verify the AI refuses to guess financial or legal terms when information is missing.
- **T=0**: User texts: *"Generate a standard fee agreement for Yossi."*
- **T+1**: AI identifies Yossi in the ledger but sees the fee and scope are missing. 
- **T+X**: AI replies: *"מצאתי את יוסי, אבל חסר לי סכום העסקה ומה בדיוק תיאור העבודה. מה הסכום ומה השירות?"* (or similar).
- **Expectation**: The AI **must not** generate a placeholder document or hallucinate a default fee. It must wait for the user's reply. Once the user replies with the missing data, the document is generated.

### Scenario C: Formatting Integrity Verification
**Goal**: Verify the Python backend generating the Word document doesn't destroy the template's branding.
- **Step 1**: Trigger Scenario A or B to receive a `.docx` file.
- **Step 2**: Open the received file in MS Word or Google Docs.
- **Expectation**: Company logos are intact, bold/italic text styles surrounding the placeholders remain correct, bullet points are unbroken, and paragraph justification matches the baseline variant perfectly.
