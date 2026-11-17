# Session log — EDF-150

## Approach rationale
- **Issue:** #150
- **Approach chosen:** Guard test scans skills/agents/bin/starters with LLD patterns; parity tests drive `tracker.py` directly; shims and `check-epic-checkbox.py` deleted; shim variants of the golden matrix dropped.
- **LLD deviations:** none
- **Pressure:** standard — ~60 test lines new, 3 source files deleted, docs/version edits.

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-11-17T18:06:56Z | $0.63 | 2,872 in / 11,618 out | pressure: standard — test/doc-heavy, 3 deletions [models: claude-sonnet-5-5 $0.63, claude-haiku-5-5 $0.00] |
| 5 | 2026-11-17T18:06:56Z | $0.63 | 2,872 in / 11,618 out | green on attempt 1; audit n/a [models: claude-sonnet-5-5 $0.63, claude-haiku-5-5 $0.00] |

## Concerns & Deferred Items
- Live-gh `test_dry_run_output`/`test_dry_run_with_labels` removed from `test_shell_scripts.py` (not hermetic; dry-run covered by `create-dry-run*` goldens).
- CRLF config-loading test in `test_shell_scripts.py` replays a bash loop copy, not the script; left as-is (pre-existing).
