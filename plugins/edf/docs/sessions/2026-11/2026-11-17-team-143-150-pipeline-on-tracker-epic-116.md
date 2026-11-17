# Team session — Epic #116 (E3.3 Pipeline on the tracker script), 2026-11-17

Lead view of `/feature-team epic 116`: 8 tasks, 3 waves, 8 teammates, all merged, epic closed.

## Issues shipped

| Issue | Story | PR | Branch | Merged (UTC) |
|---|---|---|---|---|
| #146 | Migrate remaining skills | #153 | feat/migrate-remaining-skills | 17:44 |
| #145 | Migrate planning skills + gh-issue-manager | #152 | feat/migrate-planning-skills | 17:45 |
| #144 | Epic progress: child statuses | #156 | feat/epic-progress-child-statuses | 17:46 |
| #143 | Feature identity resolver | #154 | feat/feature-identity-resolver | 17:46 |
| #147 | Migrate agents, bin, starters | #155 | feat/migrate-agents-bin-starters | 17:46 |
| #148 | Route cost labels | #158 | feat/route-cost-labels | 18:01 |
| #149 | Migrate feature skills | #157 | feat/migrate-feature-skills | 18:02 |
| #150 | Guard test, parity repoint, shim removal | #159 | feat/issue-access-guard | 18:11 |

Waves: W1 #143–#147 (parallel), W2 #148 #149 (after #143/#144), W3 #150 (guard last). Plugin version 0.10.82 → 0.10.87.

## Cross-cutting decisions

- Wave-2 teammates were briefed with Wave-1 lessons (session-log path, no `uv`, known failing test, version number).
- #150 deleted `gh-project-status.sh`, so the lead closed the epic via `tracker.py status/comment/close` instead of the skill's script call. The skill text for Step 7 still names the old script until `feature-team` is next touched (#149 migrated it; verify).
- #150 removed two live-`gh` dry-run tests (non-hermetic, covered by goldens).

## Coordination events

- All teammates in one message per wave; merges were sequential-by-command from the user, so version-bump conflicts (0.10.83/0.10.84/0.10.85 collisions) were resolved by each later teammate rebasing and re-bumping. Several PRs bumped to the same number; the merged history is not one-patch-per-change (0.10.84 appears in #144, #143, #147).
- Shutdown requests without a `request_id` could not complete the structured handshake; teammates acknowledged in plain text and the lead stopped them with `TaskStop`.
- #145 and #147 both edited the LLD header; #147 resolved the conflict keeping both Revised rows.
- CI never ran on any PR (no workflow runs / paths-ignore) — no merge was CI-gated.
- #143 and #147 skipped test-author/evaluator; `edf:test-author` was not a registered agent type in teammate sessions (general-purpose stand-in used).

## What worked / what didn't

- Worked: disjoint-file Wave 1 gave 5 PRs in ~15 min; teammates reported clearly and held for the merge gate.
- Didn't: `append-checkpoint.py` and `park-docs.sh` assume root `docs/` (gitignored here), so cost checkpoints were lost for #143 (3c–6b), #146 (3c, 9, 10) and partly #145/#147; teammates improvised (symlink, hand-parking). One stray log landed at root `docs/` (moved in #150). `#144`'s session log was copied to root `docs/` and never committed.
- Lint, typecheck and `edf:diag` were skipped on every PR (`uv`/ruff/pyright missing on this VM).

## Process notes for `edf:retro`

- Fix `append-checkpoint.py` / `park-docs.sh` to resolve `plugins/edf/docs/sessions/` (or make the path a kb/file-map concept).
- Follow-up task: switch `backlog` and `lld-sync` to `epic-progress.py` now #144 has landed.
- Shutdown protocol: lead's `shutdown_request` needs a `request_id`; otherwise use `TaskStop`.
- Version-bump collisions in parallel waves: consider assigning bump numbers at spawn or bumping once at epic end.
- Jira ACs (2.1 AC1–AC3, 2.2 AC1–AC5, 2.3 AC2–AC4/AC6) await #115 verification and the manual `/qa` run on `SCRUM` listed in the epic exit criteria — not done here.
- Missing-from-record: #144's final session log is not in git.
