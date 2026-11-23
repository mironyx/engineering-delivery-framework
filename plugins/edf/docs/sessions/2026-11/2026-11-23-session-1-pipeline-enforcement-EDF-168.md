# Session log — EDF-168

## Approach rationale
- **Issue:** #168
- **Approach chosen:** Two small standalone bin scripts (`check-checkpoints.py`, `unblock-dependants.py`) with pure parsing functions + thin CLI; one-branch cost-0 guard in `query-feature-cost.py`; `flock` around `park-docs.sh land`; prose edits to feature-team/core/end skills and flowcharts.
- **LLD deviations:** `unblock-dependants.py` reads bodies from `list --status blocked` (no per-item `view`), only touches dependants whose `## Depends on` names the closed ref, treats the closed ref as done without a `view`; `park-docs.sh` runs unlocked with a warning when `flock` is absent.
- **Pressure:** standard — ~150 src lines across 4 source files (4 test files)

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-11-23T07:09:19Z | $1.17 | 2,559 in / 5,947 out | pressure: standard — ~150 src lines, 4 src files, 4 test files [models: claude-opus-5-5 $1.17, claude-haiku-5-5 $0.00] |
| 4bF | 2026-11-23T07:14:03Z | $3.68 | 13,182 in / 53,051 out | test-author complete — 23 BDD properties, all covered; ran after impl (out of order), 2 impl fixes in depends_on_refs — brief: used as-is [models: claude-opus-5-5 $3.68, claude-haiku-5-5 $0.00] |
| 4dF | 2026-11-23T07:14:03Z | $3.68 | 13,182 in / 53,051 out | implementation complete — second challenge pass: 0 additions, 2 deferred (list page bound, view-failure policy) [models: claude-opus-5-5 $3.68, claude-haiku-5-5 $0.00] |
| 5 | 2026-11-23T07:17:12Z | $4.40 | 14,719 in / 60,532 out | green on attempt 2 (2085/2085; typecheck/lint tools absent — ruff via uvx on touched files) — e2e: skip — no E2E tests; audit skipped (no pip-audit/uv) [models: claude-opus-5-5 $4.40, claude-haiku-5-5 $0.01] |
| 6 | 2026-11-23T07:17:31Z | $4.69 | 14,731 in / 62,185 out | diag pass — CodeScene MCP + SonarQube analysis tools unavailable in session, .diagnostics missing (worktree); justification: 7 comments added; mock-check clean [models: claude-opus-5-5 $4.68, claude-haiku-5-5 $0.01] |
| 6b | 2026-11-23T07:18:40Z | $5.32 | 16,099 in / 67,736 out | evaluator: PASS WITH WARNINGS — 0 adversarial; 1 silent-risk fixed (view failure reason), 2 noted — brief: used as-is [models: claude-opus-5-5 $5.32, claude-haiku-5-5 $0.01] |

## Concerns & Deferred Items
- `.env` has no `EDF_DOCS_DIR`, so scripts default to the gitignored root `docs/`; this session exports `EDF_DOCS_DIR=plugins/edf/docs` per call. Machine setup gap, not fixed here.
- Step order deviation: production code for all four units was written while test-author (4bF) was still running, not after (4cF). Test-author's tests are the contract — failures are fixed in the implementation; any test change must contradict an AC and is listed in the PR body.
- test-author caught 2 impl defects in `depends_on_refs` (same-line duplicate refs; "None — … #9" yielding refs) — fixed in impl, tests unchanged.
- `unblock-dependants.py` inherits `tracker.py list`'s 100-issue page (GitHub `first=100`); boards with >100 open blocked/open issues could miss dependants. Not addressed — tracker-wide limit.
- A dependency whose `view` fails keeps the dependant Blocked (fails closed) — deliberate, untested by spec.
- Markdown lint (`run-markdown-lint.sh`) reports ~1000 pre-existing MD013 (80-col) errors across skills; this branch's edits follow the files' existing long-line style. Not addressed — repo-wide lint config gap.
- Env: `pyright` and `ruff` are not on PATH, so `run-typecheck.sh` and `run-lint.sh` cannot spawn. Lint was run via `uvx ruff` on touched files (clean bar one UP017 style hint), and shellcheck on park-docs.sh is clean. Typecheck is IDE-only per CLAUDE.md.
- Process slip: ran `git stash` twice in the worktree during verification (once for a lint baseline, once by mistake); both were popped at once and nothing was lost. The first overlapped a background test run, which was then re-run (2085/2085).
- Evaluator PASS WITH WARNINGS (0 adversarial tests). Fixed: a dependency `view` failure now prints `unblock: skipped <ref> — could not view <dep>` instead of a silent `none`. Left: no-flock hosts land unlocked (warning only); a `git rev-parse` failure in check-checkpoints falls back to `.` and reports `missing: session log`, which fails safe.
