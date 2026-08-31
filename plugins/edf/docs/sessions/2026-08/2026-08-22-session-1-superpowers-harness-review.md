# Session log — superpowers harness review

## Approach rationale
- **Issue:** none — this session wasn't driven by a tracked GitHub issue. It started as a
  review request: read through `obra/superpowers` (skills, hooks, prompt templates, helper
  scripts, contributor docs) and compare against EDF's own 25 skills / 14 agents to find
  concrete improvements, not a survey. Produced six findings, ranked by impact; user picked
  #1 to implement first, then separately raised a model-pinning question that became a
  second, unrelated fix in the same session.
- **Approach chosen:** For #1 (diff packaging), matched superpowers' `review-package`
  script pattern to EDF's existing bin-script conventions (arg parsing style, error
  messages, `${CLAUDE_PLUGIN_ROOT}` resolution) rather than porting it verbatim — EDF's
  script needed PR-mode/local-mode branching and a `gh pr diff` fallback that superpowers'
  git-only version doesn't have. For the model-inherit change, read the Claude Code
  subagent docs directly (`code.claude.com/docs/en/sub-agents`) to confirm the resolution
  order before touching frontmatter, rather than assuming `inherit` behaves identically
  in-process and out-of-process.
- **LLD deviations:** none — no LLD covers this work (plugin-internal skill/agent/script
  authoring against `CLAUDE.md`'s own conventions, not an implementation against a
  design doc).
- **Pressure:** two independent light-to-standard changes (one new script + one skill
  edited across a handful of injection sites; eight frontmatter one-liners + one skill
  edit + one schema test). No sub-agent TDD flow applies to markdown skill/agent files or
  shell scripts of this shape — same reasoning as the prior non-issue session
  ([2026-08-20-session-1-framework-retro-fixes.md](2026-08-20-session-1-framework-retro-fixes.md)).

## Work completed

PR [#70](https://github.com/mironyx/engineering-delivery-framework/pull/70) — **hand
`pr-review` agents a diff file instead of pasting the diff**:
- New `plugins/edf/bin/review-package.sh` (`--pr <n>` / `--local`): writes diffstat + full
  diff at `-U10` to a git-ignored `.edf/review/` file, prints only the path plus a numstat
  table. PR mode prefers local git (`merge-base..head`, never `HEAD~1`) with a `gh pr diff`
  fallback when the PR's refs aren't fetched locally.
- `pr-review/SKILL.md` Step 1 now builds the package instead of running `gh pr diff` into
  the calling session; Step 2 classifies from the numstat table; all four agent prompts
  take `{{DIFF_FILE}}` instead of `{{DIFF}}`.
- 7 new tests in `tests/test_shell_scripts.py::TestReviewPackage`. Measured on real PR #69:
  a 57,685-byte diff replaced by one path line + 23 numstat rows.
- Version 0.10.41 → 0.10.42.

PR [#71](https://github.com/mironyx/engineering-delivery-framework/pull/71) — **agents that
exercise judgement inherit the session model**:
- Eight agents (`feature-evaluator`, `hld-review`, `lld-review`, `qa-executor`,
  `qa-explorer`, `requirements-design-drift`, `requirements-review`, `test-author`) flipped
  from `model: sonnet` to `model: inherit`. The six mechanical agents keep `model: haiku`.
- `feature-team`'s teammate spawn no longer tells the lead to check `/model` and
  hand-substitute the alias — an omitted `model` param already defaults to `inherit`.
- Added `test_judgement_agents_inherit_the_session_model` to `tests/test_agent_schema.py`,
  enforcing the mechanical/judgement split. Red-green verified: re-pinning `lld-review` to
  `sonnet` fails the test; restoring `inherit` passes.
- Documented the resolution order (`CLAUDE_CODE_SUBAGENT_MODEL` env var → per-invocation
  `model` param → frontmatter → main conversation) in `CLAUDE.md`, and confirmed EDF has no
  genuine out-of-process agent spawns — `feature-team` teammates use the same `Agent` tool
  with worktree isolation, not a separate `claude` CLI process — so `inherit` resolves
  identically for both.
- Version bumped independently to 0.10.43 (collision — see Decisions made).

Both merged to `main` (squash), in the order requested: #70 then #71. Local and remote
feature branches deleted after merge.

## Decisions made

- **Version-bump collision, self-inflicted.** Both PRs were branched from `main` and each
  bumped the same `version` field in `plugin.json`/`marketplace.json` independently
  (0.10.42 and 0.10.43) without checking whether the other was still open. #71's PR body
  even noted the coming collision ("whichever merges second will conflict... trivial to
  resolve, but it will not auto-merge") — documenting a foreseeable problem instead of
  avoiding it. User called this out directly as frustrating. Fixed by rebasing #71's
  branch onto post-#70 `main` and resolving both version lines to `0.10.43`; cost was one
  rebase and a few minutes, but it was avoidable by sequencing the branches (or checking
  `gh pr list --state open` before opening the second PR touching a shared field).
  **Improvement action:** when opening a second PR in the same session that touches a
  version/manifest field also touched by an open PR, either branch the second PR from the
  first's branch, or check the first PR's merge state before bumping the shared field.
- **`/feature-end` not invoked literally.** It's built around `/feature-core`'s
  issue-driven pipeline (mandatory session log tied to a `FEATURE_ID`, LLD sync, board/
  issue closing). Neither PR had a linked issue, so ran the wrap-up mechanics that apply —
  verify tests, squash-merge in requested order, switch to main, delete branches — rather
  than fabricate an issue number or `FEATURE_ID` to force the literal skill to run
  end-to-end. Same call the prior non-issue session made.
- **Left the seven `**Model:** pass model: "opus"` skill-level overrides alone**
  (`architect`, `kickoff`, `requirements`, `discovery`, `bug`, `refactor-architect`,
  `frontend-architect`). They sit above frontmatter in the resolution order and still force
  Opus for design work even after this change — flagged as a deliberate-looking choice in
  #71's PR body rather than unilaterally removed, since it wasn't asked for.

## Review feedback addressed

No `edf:pr-review` pass was run against either PR — direct conversational authoring, not
`/feature-core`. Neither PR's GitHub reviews contained comments; the only checks were the
repo's non-blocking "Comprehension Check" (still pending at merge time on both, and `main`
has no branch protection requiring it — confirmed via `gh api .../branches/main/protection`
returning 404).

## LLD Sync report

Skipped — no LLD covers this work.

## Cost retrospective

No Prometheus cost-checkpoint data — this repo has no `EDF_FEATURE_PROM_DIR` configured
and the work wasn't run through `edf:feature-core`'s checkpoint mechanism. Qualitative:

- **Cost driver:** cloning and reading all 14 superpowers skills, its hooks, and prompt
  templates in full before writing the comparison — a broad one-time read, not something
  that recurs once the findings are on record.
- **Rework:** the version-bump collision above was the one real rework cost this session;
  everything else (script + skill edits, frontmatter flips, tests) landed clean on first
  pass, verified by full-suite runs before each commit.
- **Verification discipline:** both changes were red-green tested before commit — the
  `review-package.sh` empty-diff/self-ignoring-dir/stdout-never-carries-the-diff behaviors
  each had a dedicated test, and the model-inherit schema test was confirmed to actually
  fail on a reverted pin before being trusted.

## Next steps

- Four more findings from the superpowers review are still open, in priority order:
  scoped re-reviews in the fix loops (biggest remaining context/cost saving after #70), a
  shared `verification-before-completion`-style skill plus a "don't trust the report"
  block in reviewer agent prompts, rationalization tables on `feature-core` Step 3c / 5 / 9,
  and a ledger-based compaction-resume protocol plus a SessionStart skill router.
- Process gap surfaced this session: no standing check for "does another open PR touch the
  same shared field" before bumping a version. Worth a line in `CLAUDE.md`'s version-bump
  convention section if this repeats.
- Suggested next board item: none — this repo has no open-issue board item tied to either
  PR to suggest a follow-on from.
