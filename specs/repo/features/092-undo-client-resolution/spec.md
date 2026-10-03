# Feature 092: Undo Client Name Resolution

**Status**: Backlog  
**Category**: Capability  

## Issue
The webapp allows users to resolve raw, unmapped client names (aliases) to canonical Morning client names. However, if a user makes a mistake and maps an alias to the wrong client, the action is permanent within the UI. The user currently has to manually edit the backend JSON/data files to fix the mistake.

## Business Value
Reduces operational friction and data corruption by allowing non-technical users to self-correct mapping mistakes directly in the UI.

## Requirements

1. **Unlink Action in UI**: 
   Within the Webapp's Client Profile view (or wherever aliases are currently listed for a client), there MUST be an explicit "Undo" or "Unlink" button next to each resolved alias string.
2. **Backend Unlinking**: 
   Triggering this action MUST immediately remove the alias string from the canonical client's resolution mapping in the backend data store.
3. **Queue Restoration**: 
   Once unlinked, the raw alias string MUST automatically reappear in the system's "Needs Resolution" queue, returning to the exact state it was in prior to the mistaken resolution.

## User Acceptance Tests (UAT)
1. **UAT 1**: User resolves the unknown name "Yisrael I" to the canonical client "Israel Israeli". The user then goes to Israel Israeli's profile, sees the alias "Yisrael I", and clicks "Unlink".
   - **Expectation**: The alias is removed from Israel Israeli's profile immediately. If the user navigates back to the "Needs Resolution" view, "Yisrael I" is visible again awaiting a new resolution.
