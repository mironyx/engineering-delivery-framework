# Session log — /architect epic #116 (V3 E3.3 Pipeline on the tracker script)

## Summary

Designed E3.3: one LLD (`lld-v3-e3-3-pipeline-call-sites.md`), a coverage manifest, and eight task issues (#143–#150) in three waves. The plan's rough shape (six tasks) grew to eight after two review rounds flagged task sizes. HLD Open Question 1 (epic progress shape) was closed by adding `child_statuses` to the `Issue` JSON — a revision of the contract E3.1/E3.2 shipped, owned by #144. No production code written.

## Shipped

| Commit | Scope |
|--------|-------|
| `dae6d9d` | LLD v0.1 and coverage manifest |
| `6e6738a` | Second-pass review warnings applied |
| (this PR) | Manifest issue backfill, this log |

## Board state

Epic #116 body rewritten with the Tasks checklist, dependency graph and waves. Created #143 identity resolver, #144 epic progress, #145 planning skills, #146 other skills, #147 agents/bin/starters, #148 cost labels, #149 implementation skills, #150 guard + shim removal. Waves: 1 = #143–#147, 2 = #148–#149, 3 = #150. Epic #115 (E3.2) is still open — its `SCRUM` smoke run is outstanding and gates closing #116.

## Cross-cutting decisions

- `child_statuses` (eighth `Issue` key) instead of per-child `view` calls: Jira +0 requests, GitHub +1 aliased GraphQL query. Revises Story 1.3 AC1 and HLD C3.6/Flow 5 (done in #144).
- PR cost labels move into `_tracker_github.set_pr_labels` rather than `gh pr edit` (reported `gh` failure, cli/cli#11983) — keeps the guard's `/issues` rule intact.
- GitHub PR `FEATURE_ID` now uses the same prefix derivation as `tag-session.py` (deliberate, tested change).

## What didn't go to plan

- I first recommended per-child `view` as "fine at epic sizes" without weighing efficiency; the user rejected it, and the HLD had already flagged the question. Redone as `child_statuses`.
- A Python rewrite of the LLD's Tasks section matched an early `### Tasks` mention and truncated Part B; caught by an anchor check and restored. Slicing on a heading string needs an anchored match.
- The six-task split was approved, then changed to eight after review; the user was told in the same turn.

## Process notes for `/retro`

- Heading-based text surgery on long docs is error-prone; prefer Edit with unique anchors or verify structure (`grep '^#'`) after every scripted rewrite.
- `lld-review` found real design flaws twice (GraphQL exit semantics, `gh pr edit` bug) — worth the second pass.
- Wave-1 PRs all bump `plugin.json`/`marketplace.json`; expect rebase conflicts on merge.
- `/architect` and the shared session-log guide say `docs/sessions/`, but this repo ignores root `docs/`; logs live under `plugins/edf/docs/sessions/`.

## Skill self-reflection

`/architect` Step 2 asks for confirmation before artefacts but gives no place to put an open design question (like the progress shape) *before* the split is approved. Suggestion: add an "open HLD questions" line to the Step 2 summary table so they are decided at the gate, not after.

## Next step

Human reviews and merges the docs PR, then `/feature-team epic 116` (Wave 1: #143–#147).
