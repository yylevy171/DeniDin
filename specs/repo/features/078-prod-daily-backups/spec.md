# Feature Specification: Automated Daily Prod Backups

**Feature Branch**: `feature/setup-073-and-078` (Targeting 078 scope)
**Created**: 2026-09-06
**Status**: Implemented, verified live against real prod infrastructure (2026-09-14) — PR #324
**Input**: CEO requirement for a zero-downtime daily backup of the entire production data folder at 03:00 AM, implementing a 2-Tier retention policy (Daily + Monthly) across local and redundant Mac storage.

---

## 1. Business & Operational Goals

DeniDin's production state (ChromaDB memory, ledger events, sessions, media, and reminders) currently lives on a single Windows machine without automated backups. 

**The Goal**: Establish a robust, zero-downtime, automated daily backup pipeline that captures the entire `data/`, `config/`, and `logs/prod/` directories. This pipeline must implement a Grandfather-Father-Son style retention policy to guarantee both immediate short-term rollback capabilities and long-term historical disaster recovery.

---

## 2. PM Requirements (Functional)

- **REQ-078-01 (Scope)**: The backup MUST capture the entire `data/` folder, `logs/prod/`, and the `config/` directory.
- **REQ-078-02 (Zero Downtime / Hot Backup)**: The backup MUST execute on a live production system. The application containers MUST NOT be paused or stopped. (Engineers must ensure database consistency for SQLite/ChromaDB during a hot backup).
- **REQ-078-03 (Format & Architecture)**: The backup process MUST be external to the app container. It must compress the target folders into a single `.tgz` archive with a timestamped filename (e.g., `YYYY-MM-DD`).
- **REQ-078-04 (Schedule)**: The daily backup MUST trigger daily at exactly **03:00 AM Israel time** (ensuring it runs *after* the Feature 070 memory roll completes).

### 2.1 Retention & Storage Strategy
The system must manage two distinct backup tiers to optimize disk space (~330MB per archive) while providing 3 years of coverage.

- **REQ-078-05 (Tier 1: Daily Retention)**: 
  - **Schedule**: Every day.
  - **Retention**: Keep the last **30 days** of backups. Automatically purge older archives.
  - **Storage**: Save to a dedicated `denidin daily backups` folder on the Windows host, AND successfully transfer/pull to a matching `denidin daily backups` folder on the Mac.
  
- **REQ-078-06 (Tier 2: Monthly Retention)**:
  - **Schedule**: Only the backup taken on the **1st of each month** is promoted to Tier 2.
  - **Retention**: Keep for **36 months** (3 years).
  - **Storage**: Save to a dedicated `denidin monthly backups` folder on the Windows host, AND successfully transfer/pull to a matching `denidin monthly backups` folder on the Mac. (A third undefined cloud-storage location will be managed manually for now).

---

## 3. Success Criteria
- **SC-001**: Valid `.tgz` files are successfully generated at 03:00 AM without interrupting the live bot.
- **SC-002**: A manual restore test proves that the backup archive is fully consistent (no SQLite corruption) and can successfully boot a replica environment.
- **SC-003**: The Mac successfully receives its redundant copy of both daily and monthly backups.
- **SC-004**: The system successfully purges Tier 1 backups older than 30 days.
