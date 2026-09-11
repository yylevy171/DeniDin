# Handoff Spec & Implementation Prompt: DeniDin Interactive Client Resolution & Aging Dashboard

**From:** Rapaport (Senior Business & Operations Analyst)  
**To:** Pamela (Lead Product Spec Owner)  
**cc:** Genadi (PM), Engineering Team  
**Subject:** Spec Request: Productizing the Interactive Client Resolution & Ledger Engine into the Core UI

---

### 1. Executive Summary & Value Proposition
During our ledger audit and revenue reconciliation across WhatsApp agreements, Morning Green-Invoice docs, and the production event store, we developed an operational tool: the **Interactive Client Resolution Engine** (`reports/mapping_server.py`). 

It provided immediate, high-value visibility to the CEO by resolving billing discrepancies, matching alias names, and calculating true net balance across 300+ clients in real time. 

The CEO has requested that we make this capability an integral part of the main web application UI.

---

### 2. What the Feature Does (Core Functional Requirements)

1. **Unified Client Ledger & Aging Grid:**
   * Displays every official client with aggregated metrics:
     * **Agreed (₪):** Sum of signed retainer / fee agreement milestones (source_type `הסכם`).
     * **Paid Invoices (₪):** Net paid invoices (Docs 320, 400 PLUS; 300, 305, 330 IGNORED).
     * **Balance (₪):** `Invoices - Agreed`.
     * **Status Indicator:**
       * 🟢 **Green:** Fully resolved / paid up (`Invoices == Agreed`).
       * 🔴 **Red:** Balance mismatch / overdue balance (`Invoices < Agreed`).
       * 🟡 **Yellow:** Unmapped / pending review.
     * **Last Activity:** Chronologically most recent transaction or milestone date.
     * **Operational Comments & Notes:** Inline editable commentary field with instant persistence.

2. **Unmatched / Alias Resolution Workbench:**
   * Surfaces Morning document records or WhatsApp names that could not be automatically mapped to the master client list.
   * Provides auto-suggested fuzzy matching (Levenshtein/difflib) against official clients.
   * Allows one-click linking of alias names to official client identities, immediately recalculating ledger balances upon save.

3. **Inline Actions & Instant Sync:**
   * Async REST API endpoints to save manual mappings, client comments, and resolution notes without full page reloads.

---

### 3. Architecture & Existing Reference Code

We already have a fully functioning backend service, aggregation logic, and responsive Glassmorphism UI running locally:

* **Backend Data Aggregation & Logic:**  
  [`teammate5/reports/generate_client_status.py`](file:///Users/yaron/Projects/DeniDin/teammate5/reports/generate_client_status.py)  
  * Implements `get_report_data()`, multi-source ledger merging, name normalization, and formula definitions (Docs 320, 400, 300, 305, 330).
* **Interactive Web Server & UI Layout:**  
  [`teammate5/reports/mapping_server.py`](file:///Users/yaron/Projects/DeniDin/teammate5/reports/mapping_server.py)  
  * Contains the HTML template, responsive CSS styling, and POST endpoints (`/save-mapping`, `/save-notes`, `/save-comment`).
* **Active Data Models & State Files:**  
  * Mappings: `client_mapping.json`
  * Client Comments: `client_comments.json`
  * Notes: `mapping_notes.json`

---

### 4. Implementation Prompt for Engineering Team

```markdown
### Task for Frontend/Fullstack Engineer:
Embed the "Client Resolution & Aging Ledger Dashboard" into the DeniDin web application UI (`apps/webapp`).

#### Scope:
1. **API Integration:**
   * Port the data aggregation logic from `teammate5/reports/generate_client_status.py` into a backend service / API route in `apps/webapp/backend` (e.g. `GET /api/reports/client-status`).
   * Provide endpoints to update client comments and alias mappings (`POST /api/reports/client-mapping`, `POST /api/reports/client-comment`).

2. **UI Component:**
   * Convert the frontend in `teammate5/reports/mapping_server.py` into a React/Next.js/web component under the main app navigation (e.g. `/reports/reconciliation` or `/ledger/resolution`).
   * Preserve the UX features:
     - Color-coded balance badges (Green for equal, Red for underpaid).
     - Search and status filter (All, Mismatches Only, Unmapped Only).
     - Live inline editing of client comments with asynchronous save.
     - Unmapped entities panel with suggested client matching.
```
