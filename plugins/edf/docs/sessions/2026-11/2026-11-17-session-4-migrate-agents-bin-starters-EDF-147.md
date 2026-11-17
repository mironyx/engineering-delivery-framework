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

## Concerns & Deferred Items
- `edf:test-author` agent type unregistered at spawn time; used a `general-purpose` stand-in following `agents/test-author.md`.
- Pre-existing: `TestGhCreateIssue::test_dry_run_output` fails (live gh finds existing issue, prints `exists:150`); also fails on clean main. Deselected in Step 5.
- Pre-existing: `update-coverage-manifest.py` slug regex is greedy (`lld-v1-e1-2-review-feedback.md` → `v1-e1-2-review`); left untouched, out of scope.
- `uv` missing: lint/diag/audit skipped; shellcheck run directly on brief-package.sh (clean).
- Added JSON-stdin support to `--extract-epic-slug` so `/feature-end` (T7) can pipe `tracker.py view` straight in.
- Evaluator PASS WITH WARNINGS (0 adversarial tests): guard test checks only `gh issue view`/`gh project item-list` (full guard is §1.4, later PR); two silent risks accepted — `--extract-epic-slug` swallows malformed JSON like a bare body, and brief header parse has no explicit error check after tracker success.
