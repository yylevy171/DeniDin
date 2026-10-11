# User Stories: Automated Daily Prod Backups (Feature 078)

## Business Goal
Ensure absolute data safety and business continuity by automating zero-downtime, redundant backups of the DeniDin production state. Implement a tiered retention policy that optimizes disk space while providing 30 days of immediate high-fidelity rollback and 3 years of historical snapshots.

---

## User Acceptance Testing (UAT)

Since this is an operational infrastructure feature, the "user" is the system administrator (the CEO/Operator).

### UAT 1: Zero-Downtime Execution (Priority: P1)
**Given** the DeniDin production system is live and actively processing messages
**When** the clock strikes 03:00 AM Israel time
**Then** the external backup process MUST start automatically
**And** the DeniDin bot MUST continue responding to WhatsApp messages without any delay or downtime during the backup process.

### UAT 2: Tier 1 (Daily) Storage and Transfer (Priority: P1)
**Given** a daily backup process has completed
**When** the administrator checks the file systems
**Then** there MUST be a newly timestamped `.tgz` archive in the `denidin daily backups` folder on the Windows host
**And** there MUST be an identical `.tgz` archive successfully transferred to the `denidin daily backups` folder on the Mac.

### UAT 3: Data Consistency & Restore Integrity (Priority: P1)
**Given** a completed backup `.tgz` archive
**When** the administrator unpacks the archive into an isolated test environment and boots the `denidin-app` against it
**Then** the application MUST boot successfully without any database corruption errors (SQLite/ChromaDB)
**And** the administrator MUST be able to query the ledger and long-term memory exactly as it existed at 03:00 AM.

### UAT 4: Tier 1 Retention Sweep (Priority: P2)
**Given** the `denidin daily backups` directory contains archives older than 30 days
**When** the daily backup process finishes
**Then** the system MUST automatically delete any `.tgz` files in that folder that are strictly older than 30 days, preserving disk space on both the Windows and Mac hosts.

### UAT 5: Tier 2 (Monthly) Promotion and Retention (Priority: P2)
**Given** the backup process runs on the 1st of a new month
**When** the daily `.tgz` is generated
**Then** a copy of that archive MUST be placed into the `denidin monthly backups` folder on both the Windows host and the Mac
**And** the system MUST ensure these monthly archives are retained for exactly 36 months before being purged.
