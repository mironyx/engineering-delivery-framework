# Session log — EDF-120

## Approach rationale
- **Issue:** #120
- **Approach chosen:** Implement view/list_issues/edit/comment in `_tracker_github.py` per LLD §1.3, reusing `_fetch_issue`, `_board_item`, `load_board(strict=False)` and `_gh`; `_derive_status` reads the option id from `_board_item` rather than walking fieldValues again. One new `ISSUES_QUERY` constant built from `ISSUE_FIELDS`.
- **LLD deviations:** none planned. `check-epic-checkbox.py` keeps its own parent regex until #121 absorbs it (T4 owns that shim); `parent_from_body` uses the same pattern.
- **Pressure:** standard — ~90 src lines in 1 source file (1 test file).

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-11-15T22:03:11Z | $0.73 | 2,891 in / 2,429 out | pressure: standard — ~90 src lines, 1 src file, 1 test file [models: claude-opus-5-5 $0.73, claude-haiku-5-5 $0.00] |
| 4dF | 2026-11-15T22:07:28Z | $1.85 | 4,320 in / 27,597 out | implementation complete — 52/52 new tests pass; full suite run (see 5) [models: claude-opus-5-5 $1.85, claude-haiku-5-5 $0.00] |
| 5 | 2026-11-16T01:32:28Z | $2.97 | 4,338 in / 32,277 out | green on attempt 2 — 944 passed, 18 skipped (python3 -m pytest; uv missing) [models: claude-opus-5-5 $2.97, claude-haiku-5-5 $0.00] |
| 6 | 2026-11-16T01:32:50Z | $3.31 | 4,358 in / 34,593 out | diag pass — exporter/CodeScene unavailable, Sonar no project; justification ok [models: claude-opus-5-5 $3.31, claude-haiku-5-5 $0.00] |
| 6b | 2026-11-16T01:34:43Z | $3.87 | 5,548 in / 40,852 out | evaluator: PASS WITH WARNINGS — token-scope fix + 6 tests; 1 deferred — brief: used as-is [models: claude-opus-5-5 $3.87, claude-haiku-5-5 $0.00] |
| 8 | 2026-11-16T01:35:16Z | $3.97 | 5,552 in / 42,304 out | [PR #126](https://github.com/mironyx/engineering-delivery-framework/pull/126) [models: claude-opus-5-5 $3.97, claude-haiku-5-5 $0.00] |
| 9 | 2026-11-16T01:39:24Z | $6.05 | 90,028 in / 70,361 out | review clean — 1 blocker dismissed (trailer), 2 warns fixed (test merge), 1 accepted [models: claude-opus-5-5 $6.03, claude-haiku-5-5 $0.02] |
| 10 | 2026-11-16T01:39:24Z | $6.05 | 90,028 in / 70,361 out | report done — no CI in repo; PR marked ready [models: claude-opus-5-5 $6.03, claude-haiku-5-5 $0.02] |

## Concerns & Deferred Items
- 10 #118 grammar tests in `tests/test_tracker.py` asserted the stub's `Error: not implemented` for view/list/edit/comment; rewritten to observe the gh call via fake_gh rules (as #119 did for create/status). Grammar assertions unchanged; `close` keeps the stub check until #121.
- Verification ran with `python3 -m pytest` directly (uv missing, so `run-tests.sh`/`run-lint.sh` fail); Python lint not run.
- Step 6 diag: `.diagnostics/` missing (worktree) and CodeScene MCP unavailable — both skipped. SonarQube skipped: no SonarQube project exists for this repo (only `mironyx_feature-comprehension-score`). Justification check ok; no subprocess patching in tests.
- Evaluator PASS WITH WARNINGS. Fixed: edit/comment fetched `projectItems` (needs `read:project`); now edit/comment never request board fields and view/list request them only when `project.env` exists (`_tracker_github.py` `_require_issue`, `_PLAIN_ISSUES_QUERY`); 6 tests in `TestTokenScope` (`tests/test_tracker_github.py`).
- Deferred: `list --status "in progress"` with no `project.env` returns `[]` with no warning, since every open issue derives to `todo` (LLD Open question 1, accepted behaviour). Raise at E3.3 if `/feature` relies on it.
- Deviation: added `_require_issue` (shared not-found check for view/edit/comment) and `_PLAIN_ISSUES_QUERY` (not in the LLD); both justified in code.
- PR #126 review: Agent Q blocked on the `Co-Authored-By` trailers. Dismissed: the lead's brief and the session attribution rule require it.
- PR #126 review (Q and B warn): the tests were in a new `test_tracker_github_read_edit.py` with about 10 duplicated helpers, while the LLD and issue name `test_tracker_github.py`. Merged them into `tests/test_tracker_github.py` with one superset `_node`. Fix: 0 source lines, self-checked, skipped re-review.
- `_require_issue` unspecified-function warning: it has a justification and is listed under PR Design deviations. No change.

## Work completed
- [PR #126](https://github.com/mironyx/engineering-delivery-framework/pull/126): `view`, `list`, `edit`, `comment` in `plugins/edf/bin/_tracker_github.py`.
- Tests: `tests/test_tracker_github.py` (+52 new, incl. 6 `TestTokenScope`); 10 #118 grammar tests in `tests/test_tracker.py` re-pointed at the gh call.
- Plugin version bumped in `plugin.json` and `marketplace.json`.

## Decisions made
- Board fields (`projectItems`) are requested only by view/list and only when `project.env` exists, to avoid the `read:project` scope. See Concerns & Deferred Items.
- `parent_from_body` copies the regex rather than moving it; #121 absorbs `check-epic-checkbox.py`.

## Review feedback addressed
- [blocker] `Co-Authored-By` trailers — not a defect (attribution rule requires them).
- [warn] `test_tracker_github_read_edit.py` duplicated helpers — fixed in d49a84d (merged into `test_tracker_github.py`).
- [warn] `_require_issue` unspecified — accepted, listed under PR design deviations.

## LLD Sync report
## LLD Sync — Issue #120: GitHub backend view, list, edit and comment

### Corrections (spec was wrong)
- Board fields in view/list/edit/comment: LLD always used `ISSUE_FIELDS` → built requests them only for view/list when `project.env` exists — `projectItems` needs `read:project` scope.
- `parent_from_body` "moved" from `check-epic-checkbox.py` → copied; the script keeps its own copy until #121.

### Additions (not in spec)
- `_require_issue` (shared not-found check) and `_PLAIN_ISSUES_QUERY`/`ISSUES_QUERY` constants — LLD §1.3.
- `_derive_status` reads the option id via `_board_item` instead of re-walking fieldValues.

### Omissions (in spec but not built)
- None.

### Confirmations (notable)
- Seven-key shape, one gh call for `list`, stdin-only bodies (I10–I13) built as specified.

### LLD updated
File: plugins/edf/docs/design/v3/lld-v3-e3-1-tracker-script.md §1.3 (Part B); coverage manifest entries flipped to `Revised`
Version: 0.3 → 0.4

## Cost retrospective
| Bucket | Cost |
|--------|------|
| 3c → 5 (design, tests, implementation, fix cycles) | $2.24 |
| 5 → 8 (diag, evaluator, PR) | $1.00 |
| 8 → 9 (review and fixes) | $2.08 |

- Note: the final-cost query reports $0.37 (2 sessions), well below the $6.05 checkpoint total; the checkpoint table is the reliable figure.
- Step 5 green on attempt 2 and a 3-hour wall-clock gap: the full-suite run hit a fix cycle.
- Post-PR review cost ($2.08, 52% of total) was driven by two review agents re-reading the full diff; the duplicated-helper test file was avoidable — name the LLD's test file in the test-author brief.
- Evaluator found a token-scope defect (`read:project`); add "token scopes of requested GraphQL fields" to the test-author contract checklist.

## Next steps
- #121 — GitHub `close` (absorbs `check-epic-checkbox.py`, removes the `close` stub).
- Raise the `list --status` with no `project.env` behaviour at E3.3 if `/feature` relies on it.
