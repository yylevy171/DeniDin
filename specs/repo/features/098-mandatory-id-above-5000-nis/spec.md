# Feature 098: Mandatory Client ID for Transactions > 5000 NIS

**Feature Branch**: `feature/098-mandatory-id-above-5000-nis`
**Status**: Backlog

## 1. Business & Architectural Goals

The Israeli Tax Authority (רשות המסים) requires an Allocation Number (מספר הקצאה) for any tax invoice exceeding 5,000 NIS. To obtain this allocation number via the Morning API, the client profile must contain a valid Israeli ID (תעודת זהות) or Company ID (ח.פ). 
Currently, if DeniDin attempts to generate a document > 5,000 NIS without an ID on file, it will either fail or generate a non-compliant document. We must enforce this at the AI boundary before the API call is made.

## 2. PM Requirements (Functional)

- **REQ-098-01 (Threshold Check)**: Whenever the user requests the generation of a Tax Invoice (300) or Tax Invoice/Receipt (320), the system must check the total transaction amount.
- **REQ-098-02 (ID Validation)**: If the amount is strictly greater than 5,000 NIS (or >= 5000 depending on exact Morning API thresholds, Dev to verify), the system must verify that the `client_id` associated with the request has a populated, valid 9-digit ID/Company ID.
- **REQ-098-03 (Conversational Block)**: If the ID is missing, the AI Agent MUST halt the document creation process and prompt the human: "The amount exceeds 5,000 NIS. Please provide the client's ID/Company ID for tax allocation (מספר הקצאה) before I can generate the invoice."
- **REQ-098-04 (Update & Proceed)**: Once the human provides the ID, the AI updates the client profile (via `update_client` capabilities) and seamlessly resumes generating the document.

## 3. User Acceptance Tests (UAT)

- **UAT-1 (Below Threshold)**:
  - *Given* a client with no ID on file,
  - *When* the user requests a 320 for 4,500 NIS,
  - *Then* the system generates the document successfully without prompting for an ID.
- **UAT-2 (Above Threshold)**:
  - *Given* a client with no ID on file,
  - *When* the user requests a 320 for 12,000 NIS,
  - *Then* the system refuses to generate the document immediately and asks the user for the ID.
- **UAT-3 (Completion)**:
  - *Given* the system just asked for the ID for a 12,000 NIS invoice,
  - *When* the user replies "511223344",
  - *Then* the system updates the client and successfully generates the 320 with the allocation number.

## 4. Complexity & Open Questions

- Does Morning API handle the allocation number (מספר הקצאה) automatically as long as the ID is present, or do we need to pass a specific flag in the API payload? (Dev to verify with Morning docs).
