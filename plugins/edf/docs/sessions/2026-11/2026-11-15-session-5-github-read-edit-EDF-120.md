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
