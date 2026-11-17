# Session log — EDF-147

## Approach rationale
- **Issue:** #147
- **Approach chosen:** `brief-package.sh` reads the issue through one `tracker.py view` call (JSON → title/body via run-python.sh), drops the numeric-only `--issue` check (refs are opaque). The two agents, `update-coverage-manifest.py` docstring and `starters/CLAUDE.md.template` swap `gh issue view` / `gh project item-list` for `tracker.py view` / `list`.
- **LLD deviations:** none
- **Pressure:** standard — ~15 src lines but 5 source files (>3), 1 test file.

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-11-17T17:32:30Z | $0.48 | 2,470 in / 5,916 out | pressure: standard — ~15 src lines, 5 src files (>3), 1 test file [models: claude-sonnet-5-5 $0.48, claude-haiku-5-5 $0.00] |
| 4bF | 2026-11-17T17:34:08Z | $0.98 | 5,317 in / 20,295 out | test-author (general-purpose stand-in) complete — 8 properties, all covered — brief: used as-is [models: claude-sonnet-5-5 $0.98, claude-haiku-5-5 $0.00] |
| 4dF | 2026-11-17T17:34:20Z | $1.03 | 5,323 in / 21,709 out | implementation complete [models: claude-sonnet-5-5 $1.02, claude-haiku-5-5 $0.00] |
| 5 | 2026-11-17T17:35:27Z | $1.07 | 5,327 in / 22,449 out | green on attempt 1 (python3 -m pytest, 1938 passed; e2e skip; test_dry_run_output pre-existing live-gh failure, deselected; uv missing so audit/lint skipped, shellcheck ok) [models: claude-sonnet-5-5 $1.07, claude-haiku-5-5 $0.00] |
| 6 | 2026-11-17T17:35:27Z | $1.07 | 5,327 in / 22,449 out | diag unavailable (uv missing); shellcheck ok; justification ok; HTTP mocking check n/a [models: claude-sonnet-5-5 $1.07, claude-haiku-5-5 $0.00] |
| 6b | 2026-11-17T17:36:19Z | $1.29 | 5,346 in / 27,006 out | evaluator: PASS WITH WARNINGS (0 adversarial tests) — brief: used as-is [models: claude-sonnet-5-5 $1.29, claude-haiku-5-5 $0.00] |
| 8 | 2026-11-17T17:36:39Z | $1.32 | 5,350 in / 27,792 out | [PR #155](https://github.com/mironyx/engineering-delivery-framework/pull/155) [models: claude-sonnet-5-5 $1.32, claude-haiku-5-5 $0.00] |
| 9 | 2026-11-17T17:37:35Z | $1.63 | 6,644 in / 33,374 out | review: 4 warnings, 3 fixed, 1 deferred (test helper dedupe) [models: claude-sonnet-5-5 $1.63, claude-haiku-5-5 $0.00] |
| 10 | 2026-11-17T17:37:46Z | $1.67 | 6,648 in / 34,000 out | report done; ci: none; PR marked ready [models: claude-sonnet-5-5 $1.67, claude-haiku-5-5 $0.00] |

## Concerns & Deferred Items
- `edf:test-author` agent type unregistered at spawn time; used a `general-purpose` stand-in following `agents/test-author.md`.
- Pre-existing: `TestGhCreateIssue::test_dry_run_output` fails (live gh finds existing issue, prints `exists:150`); also fails on clean main. Deselected in Step 5.
- Pre-existing: `update-coverage-manifest.py` slug regex is greedy (`lld-v1-e1-2-review-feedback.md` → `v1-e1-2-review`); left untouched, out of scope.
- `uv` missing: lint/diag/audit skipped; shellcheck run directly on brief-package.sh (clean).
- Added JSON-stdin support to `--extract-epic-slug` so `/feature-end` (T7) can pipe `tracker.py view` straight in.
- Evaluator PASS WITH WARNINGS (0 adversarial tests): guard test checks only `gh issue view`/`gh project item-list` (full guard is §1.4, later PR); two silent risks accepted — `--extract-epic-slug` swallows malformed JSON like a bare body, and brief header parse has no explicit error check after tracker success.
- pr-review (4 warnings): fixed filename sanitising, header-parse length check, narrowed JSON fallback in `--extract-epic-slug`. Deferred: `_run_brief` test helper to dedupe shim/env boilerplate in brief-package tests (maintainability, tests/test_shell_scripts.py).

## Work completed
- [PR #155](https://github.com/mironyx/engineering-delivery-framework/pull/155): `brief-package.sh` reads the issue via one `tracker.py view` call (opaque refs, sanitised file name).
- Agents `feature-evaluator`, `test-author` and `starters/CLAUDE.md.template` point at `tracker.py`; `update-coverage-manifest.py` accepts `view` JSON.
- Tests: 8 new/repointed in `tests/test_shell_scripts.py`; version 0.10.83.

## Decisions made
- Dropped the numeric `--issue` check rather than keeping it for GitHub: refs are opaque (LLD §1.3).
- `--extract-epic-slug` takes `view` JSON so T7 needs no extra parsing step.

## Review feedback addressed
- [silent-swallow] brief-package.sh header parse — fixed in 2179289 (length check).
- [bug] brief-package.sh output file name — fixed in 2179289 (sanitised).
- [silent-swallow] update-coverage-manifest.py JSON fallback — fixed in 2179289 (narrowed).
- [maintainability] tests/test_shell_scripts.py shim boilerplate — deferred (see Concerns).

## LLD Sync report
## LLD Sync — Issue #147: Migrate agents, bin scripts and starters template to the tracker script

### Corrections (spec was wrong)
- None.

### Additions (not in spec)
- `--extract-epic-slug` accepts `tracker.py view` JSON; `brief-package.sh` strips a leading `#` from the ref for its file name. Recorded under §1.3 area split.

### Omissions (in spec but not built)
- None.

### Confirmations (notable)
- `feature-evaluator`, `test-author`, `CLAUDE.md.template` migrated as specified.

### LLD updated
File: plugins/edf/docs/design/v3/lld-v3-e3-3-pipeline-call-sites.md §1.3
Version: 0.3 → 0.4

## Cost retrospective
| Bucket | Cost |
|--------|------|
| 3c → 5 (design, tests, implementation) | $0.59 |
| 5 → 8 (evaluator, commit/PR) | $0.25 |
| 8 → 9 (review, fixes) | $0.31 |
| Final total | $1.92 |
- Drivers: test-author stand-in ($0.50 in 3c→4bF) was the largest single step; post-PR work was small (review fixes ~$0.31).
- Next time: five source files forced Standard track for ~15 lines of change; weigh that when slicing similar migration tasks.

## Next steps
- Add `_run_brief` helper in tests/test_shell_scripts.py to dedupe shim boilerplate.
- T7 (#149) can pipe `tracker.py view` into `update-coverage-manifest.py --extract-epic-slug`.
