# Session log — EDF-148

## Approach rationale
- **Issue:** #148
- **Approach chosen:** `apply_labels` takes an issue ref; one `tracker.py view` + one `tracker.py edit` (all adds/removes) for the issue, `gh label create` only on GitHub, PR labels through new `_tracker_github.set_pr_labels` (REST, moved verbatim). Feature ID via `_feature_id.resolve_feature_id`.
- **LLD deviations:** none. `set_pr_labels` takes the stale-removal list computed by the caller (from `gh pr view`), as the LLD signature `(pr, add, remove)` implies.
- **Pressure:** standard — ~60 src lines across 2 source files (1 new test file).

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-11-17T17:50:16Z | $0.63 | 2,754 in / 14,708 out | pressure: standard — ~60 src lines, 2 src files [models: claude-sonnet-5-5 $0.63, claude-haiku-5-5 $0.00] |
| 3c | 2026-11-17T17:50:20Z | $0.63 | 2,754 in / 14,708 out | pressure: standard — ~60 src lines, 2 src files [models: claude-sonnet-5-5 $0.63, claude-haiku-5-5 $0.00] |
| 5 | 2026-11-17T17:51:40Z | $0.69 | 2,760 in / 16,728 out | green on attempt 1 (2034 passed); e2e skip; lint/diag/sonar tools unavailable (uv missing) [models: claude-sonnet-5-5 $0.69, claude-haiku-5-5 $0.00] |
| 8 | 2026-11-17T17:52:07Z | $0.73 | 2,764 in / 17,841 out | [PR #158](https://github.com/mironyx/engineering-delivery-framework/pull/158) [models: claude-sonnet-5-5 $0.73, claude-haiku-5-5 $0.00] |
| 9 | 2026-11-17T17:53:06Z | $1.05 | 2,795 in / 22,745 out | review: 2 warnings fixed (best-effort guards) [models: claude-sonnet-5-5 $1.05, claude-haiku-5-5 $0.00] |
| 10 | 2026-11-17T17:53:18Z | $1.09 | 2,797 in / 23,408 out | report done; review warnings fixed; ci: none [models: claude-sonnet-5-5 $1.09, claude-haiku-5-5 $0.00] |

## Concerns & Deferred Items
- `edf:test-author` agent type is not registered in this session; tests written by the main agent after implementation (no independent author). Tests assert LLD §1.1 behaviours.
- pr-review (2 warnings, both fixed): `apply_labels` could raise on bad Jira config (`query-feature-cost.py` active_backend) and `_fetch_pr_labels` had unguarded JSON parsing. Fix ~8 src lines — self-checked, skipped re-review.

## Work completed
- [PR #158](https://github.com/mironyx/engineering-delivery-framework/pull/158): `query-feature-cost.py` routes issue labels through `tracker.py` (one `view`, one `edit`); `gh label create` GitHub-only.
- `_tracker_github.set_pr_labels` added (REST, moved verbatim); resolver supplies the feature ID.
- 20 tests in `tests/test_query_feature_cost.py`; plugin 0.10.85.

## Decisions made
- `set_pr_labels` takes the caller's `remove` list, computed from `gh pr view`; see Concerns for the test-author gap.
- Bad backend config returns from `apply_labels` silently (best-effort policy).

## Review feedback addressed
- [bug] query-feature-cost.py:259 — fixed in 9ad01ee (config error guarded)
- [bug] query-feature-cost.py:207 — fixed in 9ad01ee (PR-label JSON guarded)

## LLD Sync report
## LLD Sync — Issue #148: Route cost labels through the tracker and GitHub backend

### Corrections (spec was wrong)
- None.

### Additions (not in spec)
- `_tracker` / `_stale` helpers and the bad-config guard: recorded in §1.1 Cost labels.

### Omissions (in spec but not built)
- None.

### Confirmations (notable)
- `set_pr_labels` signature and the single `view` + `edit` per run built as specified.

### LLD updated
File: plugins/edf/docs/design/v3/lld-v3-e3-3-pipeline-call-sites.md §1.1 Cost labels
Version: 0.4 → 0.5

## Cost retrospective
| Bucket | Cost |
|--------|------|
| 3c → 5 (design, implementation, tests) | $0.06 |
| 5 → 8 (commit, PR) | $0.04 |
| 8 → 9 (review + fixes) | $0.32 |
Final: $1.30 (PR creation $0.73).
- Review round was the biggest driver: two small robustness warnings cost a full agent run plus a fix commit. Next time guard best-effort paths up front.

## Next steps
- #149 (parallel Wave 2); Task 8 guard test depends on this.
