# User Stories: Fee Agreement Document Generation

## User Acceptance Testing (UAT) Flow

The testing for this feature is broken down into four distinct stages to ensure every part of the document generation pipeline works correctly and safely.

### Stage 1: Template Selection Accuracy
**Goal**: Verify the AI selects the correct template variant based on the user's phrasing.
- **Test 1.1**: User texts *"Create a retainer agreement for NewCo Ltd."* 
  - **Expectation**: System selects the `retainer_agreement` variant.
- **Test 1.2**: User texts *"I need a standard hourly fee agreement for consultation."*
  - **Expectation**: System selects the `hourly_consultation` variant.
- **Test 1.3**: User texts *"Draft a fixed-price contract for building a website."*
  - **Expectation**: System selects the `fixed_price_project` variant.

### Stage 2: Data Gathering & Clarification (Anti-Hallucination)
**Goal**: Verify the AI properly identifies missing required fields and asks the user for them in simple turns.
- **Scenario**: User texts *"Draft an agreement for Yossi."* (assuming Yossi is found, but terms are missing).
- **Turn 1 (AI)**: The AI MUST pause and ask a clarifying question: *"What is the fee amount and scope of work for Yossi?"*
- **Turn 2 (User)**: User replies: *"The fee is 5,000 NIS for tax consultation."*
- **Expectation**: The AI successfully collects this data without hallucinating default values and proceeds to the next stage.

### Stage 3: AI Self-Verification (QA)
**Goal**: Verify that the AI acts as its own QA engineer before releasing the document to the user.
- **Scenario**: The document generation tool has created the temporary `.docx` file.
- **Expectation**: The AI MUST invoke an internal verification tool to read the generated document's contents.
- **Validation**: The AI confirms that all placeholders (e.g., `{{FEE_AMOUNT}}`) were successfully replaced with the correct user-provided data (e.g., "5,000 NIS"). 
- **Release Gate**: The document is ONLY dispatched to the user after the AI explicitly outputs a determination that the document complies with the template and is ready for release. The test logs must show the AI performing this validation step.

### Stage 4: Successful Delivery
**Goal**: Verify the final asset is reliably delivered to the user's device.
- **Scenario**: The AI has "Released" the document.
- **Expectation (Integration Level)**: The system successfully invokes Green API's `sendFileByUpload` endpoint. The user receives an actual, editable `.docx` file in their WhatsApp chat. Formatting (fonts, logos, bullet points) is perfectly intact upon opening.
