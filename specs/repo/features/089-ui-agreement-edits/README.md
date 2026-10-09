# Feature 089: Edit Agreements from Webapp UI & WhatsApp

Adds an Agreements DB (owned by denidin-app) as the living source of truth for fee agreements,
structured as an agreement container with fee components. The webapp's Clients tab gets a
"הסכמים" section to view, create, edit, delete and manage the lifecycle of agreements and
components; the WhatsApp bot reads and writes the same DB. Every DB write produces the matching
ledger event. Absorbs Feature 040.

- `spec.md`: requirements, clarifications, success criteria.
- `user-stories.md`: user stories and the UAT / acceptance scenarios (draft, pending approval).
