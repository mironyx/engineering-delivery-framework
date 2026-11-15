# Session log — EDF-118

## Approach rationale
- **Issue:** #118
- **Approach chosen:** Follow the LLD §1.1 decomposition as written: `tracker.py` (hand-rolled create/status parsers, argparse for the rest), `_tracker_contract.py`, stub `_tracker_github.py`, with config resolved via `_edf_env.resolve` and the env root from `git rev-parse --git-common-dir` (as in `tag-session.py`).
- **LLD deviations:** none
- **Pressure:** heavy — ~220 src lines across 4 source files (tracker.py, _tracker_contract.py, _tracker_github.py stub, fixtures/fake_gh.py); 2 test files (test_tracker.py, conftest.py)

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-11-15T20:27:25Z | $0.00 | 0 in / 0 out | pressure: heavy — ~220 src lines, 4 src files |
| 4bF | 2026-11-15T20:33:44Z | $0.00 | 0 in / 0 out | test-author complete — 14 properties, 237 tests, all covered (CLI unknown-status deferred to #119) — brief: used as-is |
| 4dF | 2026-11-15T20:33:44Z | $0.00 | 0 in / 0 out | implementation complete |
| 5 | 2026-11-15T20:34:32Z | $0.00 | 0 in / 0 out | green on attempt 2 (I3 pycache test fix) — pytest direct, no uv; e2e skip; audit n/a |
| 6 | 2026-11-15T20:35:01Z | $0.00 | 0 in / 0 out | diag: exporter+CodeScene unavailable (worktree, no MCP); sonar skipped (no local analyze tool); justification ok; mock check clean |
| 6b | 2026-11-15T20:37:09Z | $0.00 | 0 in / 0 out | evaluator: PASS WITH WARNINGS — 3 adversarial tests; missing-git traceback fixed — brief: used as-is |

## Concerns & Deferred Items
- `append-checkpoint.py --issue` cannot find the log: it globs `<root>/docs/sessions`, but this repo keeps logs in `plugins/edf/docs/sessions`. Decided: pass `--session-log` explicitly.
- `starters/scripts/python/run-tests.sh` needs `uv`, which is not installed here, so it reports INCONCLUSIVE. The test-author sub-agent installed pip and pytest into `~/.local` (`--user --break-system-packages`), outside the project. Decided: run `python3 -m pytest` directly and flag the install to the lead/user; not reverted.
- The test-author's I3 grep test (`tests/test_tracker.py` TestJiraVarsReadOnlyByTracker) scanned `bin/__pycache__`. It failed on `tracker.cpython-*.pyc` after the I4 tests imported `tracker` in-process. Decided: exclude `__pycache__` from the scan; the assertion is unchanged. Feed back to test-author: grep invariants should scan source files only.
- Step 5 was run directly (`python3 -m pytest tests`: 746 passed, 18 skipped), not via `edf:test`, because every `starters/scripts/python/*` wrapper `exec`s `uv`, which is not installed. Python lint did not run (no `uv`/`ruff`). The markdown lint's MD013 failures are repo-wide (default config) and were not fixed.
- Evaluator silent risk: `tracker.py` `_git` raised `FileNotFoundError` (traceback, breaks I5) when `git` was not on PATH. Fixed: an `OSError` is treated as "outside a repo". Regression test `test_git_missing_from_path_falls_back_to_cwd_without_traceback`.
- Unknown status (AC5) is unit-tested via `normalise_status` only. The CLI path runs through the backend's `status()`, which is a stub until #119, so the end-to-end test belongs to #119.
