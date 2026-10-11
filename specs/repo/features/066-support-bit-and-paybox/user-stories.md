# User Stories: Support Bit, PayBox, Checks, and Cash (Feature 066)

## Business Goal
Empower DeniDin to seamlessly handle the 4 most common alternative payment methods in Israel (Bit, PayBox, Checks, and Cash) by unifying them under a robust, highly-extensible `deposit` data model.

---

## User Acceptance Testing (UAT)

### UAT 1: The Data Model Migration (Priority: P1)
**Given** the production ledger contains hundreds of historical events structured as `type="bank", subtype="deposit"`
**When** the engineering data-migration script is executed
**Then** all historical deposit events MUST be rewritten to `type="deposit", subtype="bank"`
**And** the WebApp UI dashboard MUST load successfully and display the historical deposits correctly without any crashes.

### UAT 2: Capturing Bit and PayBox (Priority: P1)
**Given** the system receives an image of a Bit or PayBox transfer confirmation
**When** the AI processes the image
**Then** a new ledger event MUST be created with `type="deposit"` and subtype of `bit` or `paybox`
**And** the event MUST contain the correct amount and sender details extracted from the image.

### UAT 3: Capturing Checks and Cash (Priority: P1)
**Given** the system receives an image of a bank check OR a text message stating "Received 500 NIS cash from David"
**When** the AI processes the input
**Then** a new ledger event MUST be created with `type="deposit"` and subtype of `check` or `cash`
**And** for checks, the event MUST include the check number and bank details.

### UAT 4: Morning Document Generation (Priority: P1)
**Given** a `deposit` ledger event for `bit`, `paybox`, `check`, or `cash` is ready for invoicing
**When** the AI attempts to generate a Receipt (Type 320) or a Combo Document (Type 400) via the Morning API
**Then** the document MUST be successfully created in Morning
**And** the final PDF MUST correctly reflect the specific payment method used, rather than defaulting to "Bank Transfer".
