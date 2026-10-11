# DeniDin Client Resolution & Status Tool

## Overview
This directory contains the analyst tools developed by Rapaport for reconciling clients, agreements, payments, and operational notes across Morning Green-Invoice documents, WhatsApp fee agreements, and ledger events.

This tool is the functional reference for Feature 087 (`specs/repo/features/087-webapp-clients-mgmt/`), which productizes these capabilities directly into the DeniDin Webapp UI.

## Components
- `generate_client_status.py`: Data aggregation engine that loads production events, Morning documents, fee agreements, and manual alias mappings.
- `mapping_server.py`: Interactive local UI server allowing review and real-time editing of client comments and alias associations.
- `*.template.json`: Schema definitions for the operational state files.

## Operational Privacy & Production Data
Real customer data, PII (phone numbers, emails, bank accounts), and operational comments are excluded from git version control via `.gitignore`. 

In production or during analyst runtime, the server uses the live data files:
- `client_comments.json`
- `client_mapping.json`
- `mapping_notes.json`
- `removed_clients.json`
- `new_morning_clients.json`

These remain durable in local operations and can be injected directly into production environments without committing customer PII to git.
