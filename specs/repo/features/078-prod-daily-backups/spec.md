# Feature Specification: Automated Daily Prod Backups

**Feature Branch**: `feature/setup-073-and-078` (Targeting 078 scope)
**Status**: DRAFT
**Input**: CEO requirement for a zero-downtime daily backup of the entire production data folder at 03:00 AM, stored locally on the Windows server and pulled/pushed to the Mac.

---

## 1. Business & Operational Goals

DeniDin's production state (ChromaDB memory, ledger events, sessions, media, and reminders) lives on a single Windows machine. Currently, there is no automated backup. A hardware failure, accidental deletion, or a botched migration would result in an unrecoverable catastrophic loss of business data. 

**The Goal**: Establish a rock-solid, automated daily backup pipeline that captures the entire `data/` folder, configuration, and logs, compressing them into a secure snapshot (`.tgz`). This pipeline must operate completely externally to the core DeniDin application without causing any downtime.

---

## 2. PM Requirements (Functional)

- **REQ-078-01 (Scope)**: The backup MUST capture the entire `data/` folder, `logs/prod/`, and the `config/` directory.
- **REQ-078-02 (Zero Downtime / Hot Backup)**: The backup MUST execute on a live production system. The application containers MUST NOT be paused or stopped. (Engineers must ensure database consistency for SQLite/ChromaDB during a hot backup).
- **REQ-078-03 (Format & Architecture)**: The backup process MUST be external to the app container. It must compress the target folders into a single `.tgz` archive with a timestamped filename.
- **REQ-078-04 (Dual Destination)**: 
  - Destination A: A dedicated local folder on the Windows host machine (outside the Docker container).
  - Destination B: A dedicated folder on the Mac.
- **REQ-078-05 (Schedule)**: The backup MUST trigger daily at exactly **03:00 AM Israel time**, ensuring it runs *after* the Feature 070 (rolling memory) process completes at 02:00 AM.
- **REQ-078-06 (Retention Policy)**: Retain the backups for **365 days** on both the Windows box and the Mac. The system should automatically purge `.tgz` archives older than 1 year to manage disk space.

---

## 3. Success Criteria
- **SC-001**: A valid `.tgz` is successfully generated daily at 03:00 AM without any interruption to the live bot.
- **SC-002**: A manual restore test proves that the backup archive is fully consistent (no SQLite corruption) and can successfully boot a replica environment.
- **SC-003**: The Mac successfully receives its copy of the backup every night.
