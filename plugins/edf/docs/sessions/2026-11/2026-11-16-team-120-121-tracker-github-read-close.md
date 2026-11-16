# Team session — epic #114 (E3.1), resumed: #120, #121

## Issues shipped
| Issue | Story | PR | Branch | Merged |
|-------|-------|----|--------|--------|
| #120 | 1.3, 1.4 view/list/edit/comment | [#126](https://github.com/mironyx/engineering-delivery-framework/pull/126) | feat/github-read-edit | 2026-11-16 |
| #121 | 1.5, 2.1 AC4 close | [#127](https://github.com/mironyx/engineering-delivery-framework/pull/127) | feat/github-close | 2026-11-16 |

(#118, #119 shipped in an earlier lead session.) Epic #114 closed.

## Cross-cutting decisions
- Board fields (`projectItems`) are requested only by view/list and only with `project.env` (avoids `read:project` scope); LLD §1.3 corrected.
- `check-epic-checkbox.py` became a shim over the backend in #121; #120 deliberately copied its regex.

## Coordination events
- The lead session restarted mid-epic with no live teammate. #120's PR was already open, so the lead ran `edf:feature-end 120` itself from the orphaned worktree on the user's instruction.
- #121 (Wave 4) was spawned after #120 merged; teammate ran feature-core and feature-end on the user's quoted `/edf:feature-end 121`.
- `park-docs.sh` only handles `docs/` and `kb/`; this repo's docs are under `plugins/edf/docs`, so docs were stashed and landed by hand both times.
- `git pull --rebase` fails on the unrelated modified `monitoring/` files; `--autostash` was needed.

## What worked / what didn't
- Worked: sequential waves, human merge gate respected, teammate idle notices needed no intervention.
- Didn't: final-cost query reported $0.37 for #120 vs $6.05 in checkpoints (misleading label); no CI in the repo (only an external "Comprehension Check"); uv missing, so lint and diag did not run.

## Process notes for `edf:retro`
- Make `park-docs.sh` and the `docs/sessions` lookups honour `plugins/edf/docs` (or add a path variable) — repeated manual workaround.
- Investigate why `query-feature-cost.py --stage final` under-reports after a lead restart (session tagging with `--cont`).
- Install uv on this VM so run-tests/run-lint work.
- Epic exit criteria checkboxes were not ticked by any task; consider an explicit QA step.
