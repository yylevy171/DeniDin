# Bugfix 073: Client Resolution Robustness (Levenshtein Rescue Hatch)

**Status:** Done - implemented and tested, merging to master

## Problem Description
In the current client resolution mechanism (`resolve_client_by_name`), perfectly viable and highly relevant candidates are occasionally dropped due to a hardcoded threshold (`_COMMON_WORD_DISCOVERY_CAP = 10`) combined with strict exact-match intersection rules.

This was observed in production during the "מור פלומבו" incident (see `reports/prod_trace_2218.md`):
1. The operator searched for "מור פלומבו", intending to find "מור פלימבו" (a typo).
2. The independent discovery loop checked "מור". The Morning API returned 15 results (which correctly included "מור פלימבו").
3. Because `15 > _COMMON_WORD_DISCOVERY_CAP` (10), the system categorized "מור" as a non-identifying common word and **discarded all 15 results**, meaning "מור פלימבו" was dropped from the candidate pool.
4. The system checked "פלומבו" letter by letter. At "פל", it found "מור פלימבו". However, progressing to "פלו" caused it to drop "מור פלימבו" because of the typo ('ו' instead of 'י').
5. The intersection chain did find "מור פלימבו", but dropped it because it was not an exact, bag-equal match to the query.
6. The candidate pool remained empty, and `resolve_client_name` returned `{"found": false}`, completely missing an almost perfect match (Levenshtein distance = 1).

A similar issue with redundant or dropped resolutions was noted in the dev logs for "יהושע רביבו" vs "יוסי יהושע" (see `reports/dev_trace_yehoshua.md`, which contains 210 redundant tool calls to `resolve_client_name`).

## Proposed Fix
Introduce a **Levenshtein Distance Rescue Hatch** into the candidate filtering process.

Currently, Levenshtein distance is only used as a final *sorting* mechanism on candidates that survive the filters. The proposed change applies a distance check *before* discarding any candidates from the independent discovery or intersection phases.

1. Define a strict distance threshold (e.g., `distance <= 2`, appropriately scaled for short strings).
2. Before discarding a candidate list (e.g., when a word returns `> _COMMON_WORD_DISCOVERY_CAP` results, or when a prefix transition like "פל" -> "פלו" causes candidates to drop), calculate the Levenshtein distance between each candidate's name and the full original query.
3. If a candidate falls within the strict distance threshold, **rescue it** and add it unconditionally to a safelist.
4. Merge the safelist with the standard `candidates` pool before the final sort.

This ensures that extremely relevant matches (like "מור פלימבו", which has a distance of 1 from "מור פלומבו") are preserved and surfaced to the operator, regardless of upstream deterministic filters like the common-word cap.

## References
- `reports/prod_trace_2218.md`
- `reports/dev_trace_yehoshua.md`
