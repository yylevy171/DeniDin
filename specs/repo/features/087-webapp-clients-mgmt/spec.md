# Feature Specification: Clients Management UI in Webapp

**Feature ID**: 087  
**Feature Branch**: `feature/087-webapp-clients-mgmt`  
**Created**: 2026-09-17  
**Status**: In Progress  
**Category**: Capability  
**Domain**: Webapp / CRM & Client Operations  

---

## Executive Summary

Currently, client status auditing, name mapping, reconciliation notes, and Morning integration monitoring exist only as an analyst CLI script and internal prototype built by Rapaport (`reports/mapping_tool/`). 

To operationalize client relationship management and give law firm partners immediate visibility and editing capabilities without touching scripts or files, this feature integrates Rapaport's client management and status mapping workflow into the official DeniDin Webapp (`apps/webapp`). Users will have a dedicated, authenticated "Clients" view alongside the Ledger view, complete with client status summaries, Morning/ledger sync states, client comments/notes editing, and manual alias mapping.

---

## Clarifications

### Session 2026-09-17

- Q: `generate_client_status.py` hardcodes `EVENTS_DIR` to the Mac's sshfs prod mount and reads two CSVs (official client list, Morning doc history) that no longer exist in this repo. What should the productized backend use instead? → A: Ledger/Morning-derived events (agreements, deposits, invoices) continue to come from the same source as the existing Ledger tab (`LedgerEventManager` via `apps/webapp/backend`'s existing loader pattern — environment-scoped `{data_root}/events`, not the hardcoded sshfs path). The official client list itself is fetched fresh from Morning on each page load/reload (one-time full list per request — no local CSV, no caching beyond the request lifecycle).
- Q: Should the Hebrew free-text-comment-driven business rules (regex keyword scanning for `לסגור`/`לבדוק`/`לאחד`/etc.) be ported as-is? → A: Yes, port as-is, unchanged — this logic is trusted and working; only its hosting (script → importable backend service function) changes, not its behavior.
- Q: `generate_client_status.py`'s `get_report_data()` currently overwrites `removed_clients.json`/`new_morning_clients.json` as a side effect of every read. Should `GET /api/clients` keep doing this? → A: Yes — preserve this exact current behavior, including the write-on-every-read side effect. Do not change it to a read-only/explicit-save model.
- Q: Where do `client_mapping.json`/`client_comments.json`/`mapping_notes.json`/`removed_clients.json`/`new_morning_clients.json` live for the productized version? → A: Environment-scoped under `{data_root}/clients/`, per REQ-087-04 (replacing the current flat, unscoped `reports/mapping_tool/*.json` location) — dev and prod get their own independent copies, consistent with how every other app-managed state is environment-scoped.
- Q: What should the two webapp tabs be named and what does Tab 1 depend on? → A: Tab 1 = "ארועים" (today's existing Ledger view, unchanged functionally except it must be running on top of bugfix-064's fix so it no longer serves a stale in-memory snapshot). Tab 2 = "לקוחות" (this feature, the mapping tool ported in). `speckit.plan`/`speckit.tasks` for 087 should note the Tab 1 relabel/re-mount as in-scope UI work here, while the actual data-freshness fix is bugfix-064's own separate deliverable.
- Q: Visual theme for Tab 2? → A: Adopt the webapp's existing theme/chrome (surface/border/background tokens from `theme.ts`) as the base for layout, nav, and containers. Within Tab 2's own content (status badges, section headings, flagged amounts), preserve the mapping tool's distinctive **text** colors only — never its row-background tints — re-expressed as text/badge colors layered over the webapp's own surface. Concretely: settled/paid text `#10b981`, open-debt text `#ef4444`, inferred/missing-agreement text `#eab308`, overridden-amount text `#888`, active-client/follow-up accent text `#38bdf8`/`#3b82f6`.

## Requirements

### Functional Requirements

- **REQ-087-01: Two Top-Level Tabs in Webapp**  
  The webapp frontend (`apps/webapp/frontend`) MUST introduce top-level tab navigation with exactly two tabs, replacing today's single-page mount: **"ארועים"** (Events — today's existing Ledger view, unchanged functionally, relabeled and re-mounted under this tab) and **"לקוחות"** (Clients — this feature). Both tabs share the same theme, auth session, and app chrome. Tab 2 adopts the webapp's existing theme (`theme.ts` tokens) for its layout/containers, while preserving the mapping tool's distinctive **text** colors (not backgrounds) for status/badge semantics — see Clarifications for exact values.

- **REQ-087-02: Client Status & Mapping Backend API**  
  The webapp backend (`apps/webapp/backend`) MUST expose RESTful endpoints to query and update client management data:
  - `GET /api/clients`: Returns all clients with their reconciled Morning/Ledger status, payment health, total billed vs received, active aliases, and comments. Fetches the official client list fresh from Morning on each call (no local CSV, no caching beyond the request); derives agreements/deposits/invoices from the same ledger-event source the Events tab uses (environment-scoped `{data_root}/events`, not any hardcoded path).
  - `POST /api/clients/{client_id}/comments`: Updates operator comments or follow-up notes for a specific client.
  - `POST /api/clients/mapping`: Updates or establishes a manual mapping/alias between WhatsApp contact names and Morning client profiles.

- **REQ-087-03: Rapaport Mapping Engine Porting**  
  The backend MUST port the core business logic of Rapaport's client status generator (`reports/mapping_tool/generate_client_status.py`) into an importable backend service module, preserving its behavior as-is — including the Hebrew free-text-comment-driven status rules (regex/keyword scanning) and the existing side effect of recomputing/persisting `removed_clients.json`/`new_morning_clients.json` on every `GET /api/clients` call. Only the data-source plumbing changes (see REQ-087-02); the aggregation/matching/status logic itself does not.

- **REQ-087-04: Operator Comments & Status Overrides**  
  The UI MUST allow partners/operators to inline-edit operational comments (e.g. "Agreed on delayed payment until Oct 1st") and persist them in durable, environment-scoped storage under `{data_root}/clients/` (`client_comments.json`, `client_mapping.json`, `mapping_notes.json`, `removed_clients.json`, `new_morning_clients.json`) — replacing the analyst tool's current flat, environment-unscoped location under `reports/mapping_tool/`.

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
