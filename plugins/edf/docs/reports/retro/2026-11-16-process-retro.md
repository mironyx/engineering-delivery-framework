# Process Retrospective

**Date:** 2026-11-16
**Period:** project start (no previous retro) to today — focus on v3 E3.1 (#114), 2026-11-14 to 2026-11-16
**Sessions reviewed:** requirements-v3, kickoff-v3, architect-e3-1, EDF-118, EDF-119, EDF-120, EDF-121, team-120-121 (2026-11-14 to 2026-11-16)

## What went well

- **Pipeline ran end to end with the human gate intact.** Requirements → kickoff → architect → four tasks, each a PR reviewed and merged only on a typed `/feature-end` (#124, #125, #126, #127).
- **Cost fell as the LLD matured.** Final cost per task: #118 $6.98, #119 $10.17, #120 about $6.05 (checkpoint table), #121 $1.98. #121 went green first attempt with no fix cycles.
- **Golden-first on #119** surfaced two dead error paths before porting and the implementation went green on attempt 1 (session log EDF-119).
- **Review and evaluator caught real defects** the author missed: the `read:project` token-scope problem (#119, #120) and the fuzzy-dedup write (#119).
- **Session logs complete** for every task, each with LLD sync report and cost retrospective; LLD advanced 0.2 → 0.5 and the coverage manifest stayed in step.

## What needs improving

- **Docs path assumption breaks the wrap-up tooling.** This repo's docs live in `plugins/edf/docs`, but `park-docs.sh` (park/land), `append-checkpoint.py --issue` and the feature-end idempotency greps assume `docs/`. Workaround by hand in #119–#121 (session logs EDF-118, EDF-120; team log).
- **Cost data unreliable.** #118 had no cost data ("Prometheus returned 0"); #120's final label is `ai-cost-final:0.3689` against $6.05 in checkpoints; #121 PR-creation $1.08 but 8→9 review $0.30. Labels can mislead the retro and Grafana.
- **Review is the dominant cost driver.** #119: 41% of $10.17 in 8→9, five agent spawns re-reading a ~1,800-line diff mostly golden JSON. #120: 52% of cost after PR creation.
- **No automated verification gate.** `uv` is missing so `run-tests.sh` and `run-lint.sh` fail; Python lint, diagnostics, CodeScene and SonarQube have not run for any E3.1 task. The repo has no CI workflows (only an external "Comprehension Check" that stayed IN_PROGRESS through two merges).
- **Epic exit criteria are not owned by any task.** #114's three exit-criteria boxes are unticked after all tasks merged.
- **Open process bugs unrelated to E3.1 remain** (#95 teammates skip lld-sync Step 1.5, #97 checkpoint conditional on "no blockers", #112, #103), and are not yet scheduled.
- **Lead pulls fail on a dirty main** (`monitoring/textfile_collector/*` tracked files modified by the metrics hook) — needs `--autostash` every time.
- **Lead restart orphaned the teammate flow.** The lead session restarted mid-epic with no live teammate for #120; feature-end ran from the lead against the orphaned worktree (worked, but off the documented path).

## Actions from previous retro

| Action | Status | Notes |
|--------|--------|-------|
| — | n/a | First retro; no previous report exists |

## New actions

| # | Action | Addresses |
|---|--------|-----------|
| 1 | Make `park-docs.sh`, `append-checkpoint.py` and feature-end greps resolve the docs root from `kb/file-map.md` (or search `plugins/edf/docs`) | Docs path assumption |
| 2 | Install `uv` on the VM (and add a CI workflow running `run-tests.sh` + `run-lint.sh`) | No verification gate |
| 3 | Fix `query-feature-cost.py --stage final` for `--cont` sessions and the 0-scrape on #118; stop labelling when the value is below the PR-stage cost | Unreliable cost data |
| 4 | Pass review agents a diff excluding fixture/golden paths; spawn Agent B only when the LLD marks a surface Unverified | Review cost |
| 5 | Add a task or checklist item that ticks epic exit criteria (or have the final feature-end report them) | Exit criteria unowned |
| 6 | Schedule #95 and #97 before the next multi-task epic (E3.2, #115) | Open process bugs |
| 7 | Add `monitoring/textfile_collector/*` to `.gitignore` or have the hook write outside the tree | Dirty main on pull |

## Process health scorecard

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Backlog hygiene | Green | Tasks labelled, dependency graph and waves explicit; stale process bugs #95/#97/#103/#112 unscheduled |
| Definition of done | Amber | Tests, review and LLD sync done; lint, diagnostics and exit criteria not |
| Commit discipline | Green | Conventional commits with issue refs, one squash per task |
| Session continuity | Green | Logs and team log written; tooling path workaround needed |
| Drift management | Amber | No drift report existed before this retro; scan run below |
| kb/ coverage | Green | `kb/architecture.md` has the tracker access entry; no new shared helpers uncatalogued by E3.1 |
| Multi-agent readiness | Amber | Waves honoured, human gate works; orphan-worktree recovery and docs-path assumptions manual |
