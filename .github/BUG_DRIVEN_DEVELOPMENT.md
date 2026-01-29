# Bug-Driven Development (BDD) Methodology for Bug Fixes

## Overview
This methodology must be followed for every bug fix. Each step is mandatory and must be tracked in the bug's todo list. Human approval gates (🚨) are required at critical points.

## Steps

1. Analyze logs and code for root cause
2. 🚨 Human approval: root cause analysis
3. Analyze why tests did not catch bug
4. Document root cause in bugfix spec
5. Describe test proposal for bug reproduction
6. 🚨 Human approval: test proposal
7. Add failing test for real file-empty scenario (or relevant bug scenario)
8. Implement fix for the bug
9. Verify fix with real-life scenario
10. Ensure no regression in related functionality
11. Update bugfix spec and close bug

## Notes
- All steps must be completed and checked off for every bug fix.
- Human approval gates are mandatory and must be explicitly recorded.
- Test gap analysis is required after root cause analysis.
- The test proposal must be described and approved before implementation.
- The process is tracked in the bug's todo list and referenced in the bugfix spec.

## References
- `.github/CONSTITUTION.md`
- `.github/METHODOLOGY.md`
- `specs/bugfixes/README.md`
