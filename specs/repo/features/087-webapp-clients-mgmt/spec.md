# Feature Specification: Clients Management UI in Webapp

**Feature ID**: 087  
**Feature Branch**: `feature/087-webapp-clients-mgmt`  
**Created**: 2026-09-17  
**Status**: Backlog  
**Category**: Capability  
**Domain**: Webapp / CRM & Client Operations  

---

## Executive Summary

Currently, client status auditing, name mapping, reconciliation notes, and Morning integration monitoring exist only as an analyst CLI script and internal prototype built by Rapaport (`reports/mapping_tool/`). 

To operationalize client relationship management and give law firm partners immediate visibility and editing capabilities without touching scripts or files, this feature integrates Rapaport's client management and status mapping workflow into the official DeniDin Webapp (`apps/webapp`). Users will have a dedicated, authenticated "Clients" view alongside the Ledger view, complete with client status summaries, Morning/ledger sync states, client comments/notes editing, and manual alias mapping.

---

## Requirements

### Functional Requirements

- **REQ-087-01: Dedicated Clients Navigation in Webapp**  
  The webapp frontend (`apps/webapp/frontend`) MUST provide a primary top-level navigation tab/view for **Clients Management** (`/clients`), maintaining seamless visual parity, theme, and authentication with the existing Ledger UI.

- **REQ-087-02: Client Status & Mapping Backend API**  
  The webapp backend (`apps/webapp/backend`) MUST expose RESTful endpoints to query and update client management data:
  - `GET /api/clients`: Returns all clients with their reconciled Morning/Ledger status, payment health, total billed vs received, active aliases, and comments.
  - `POST /api/clients/{client_id}/comments`: Updates operator comments or follow-up notes for a specific client.
  - `POST /api/clients/mapping`: Updates or establishes a manual mapping/alias between WhatsApp contact names and Morning client profiles.

- **REQ-087-03: Rapaport Mapping Engine Porting**  
  The backend MUST integrate the core business logic of Rapaport's client status generator (`reports/mapping_tool/generate_client_status.py`) into clean, maintainable backend service modules, reading real-time data from `{data_root}/clients` and the active ledger.

- **REQ-087-04: Operator Comments & Status Overrides**  
  The UI MUST allow partners/operators to inline-edit operational comments (e.g. "Agreed on delayed payment until Oct 1st") and persist them in durable storage (`{data_root}/clients/client_comments.json`).

- **REQ-087-05: Real-time Search, Filtering & Health Badges**  
  The Clients table MUST support instant client-side filtering by:
  - Status badge: Active, Debt/Overdue, Prospective, Inactive.
  - Name, phone number, and Morning client ID.

---

## User Acceptance Tests (UAT)

### UAT-1: Viewing Client Status Dashboard
- **Given** an authenticated user logged into the webapp,
- **When** the user clicks on the "לקוחות" (Clients) tab in the navigation bar,
- **Then** the page displays a tabular list of all known clients, showing client name, phone number, Morning status, total billed/paid balance, and operational status badge.

### UAT-2: Updating Client Comments
- **Given** the user is on the Clients management page viewing client "ישראל ישראלי",
- **When** the user clicks the comments icon/field, types "סוכם תשלום ב-24 לחודש", and submits,
- **Then** the comment is saved to the backend and immediately reflected in the row without page reload.

### UAT-3: Aliasing Unresolved Morning Client
- **Given** an incoming payment or ledger entry with an unresolved client name,
- **When** the operator uses the client mapping interface to link the contact name to an existing Morning client profile,
- **Then** the alias mapping is persisted, and subsequent ledger queries reflect the resolved client profile.
