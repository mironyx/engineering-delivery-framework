# Session log — framework retro fixes

## Approach rationale
- **Issue:** none — this PR wasn't driven by a tracked GitHub issue. It originated from a
  conversation: a Claude Code sub-agent model-resolution question led into an August
  process retrospective, then a read-only self-audit of the plugin's own skills/agents.
- **Approach chosen:** Rather than fix speculatively, pulled real `/feature-core` session
  logs from `feature-comprehension-score` (a project using this plugin) for August 2026 —
  47 sessions — and aggregated actual cost-checkpoint deltas and recurring "Cost drivers" /
  "Improvement actions" entries into a ranked issue list. Fixed the ones traceable to this
  repo (EDF plugin itself), left two out of scope (one already covered by a downstream
  project's own requirements proposal, one living in that project's own scripts).
  Separately ran three parallel read-only audit agents over the core implementation
  pipeline (`feature-core`/`feature`/`feature-team`/`feature-end`), the verification/review
  layer (`test`/`diag`/`pr-review` + their agents and wrapper scripts), and the
  test-authoring/QA layer (`test-author`/`feature-evaluator`/`qa` + its agents), which
  surfaced 14 further findings; fixed the 7 High and 7 Medium ones per user direction, left
  Low-severity findings as backlog.
- **LLD deviations:** none — no LLD covers this work (it's plugin-internal skill/agent
  authoring, not a designed feature).
- **Pressure:** heavy by line-count convention (touched 21 files across two commits beyond
  the initial tool-grant commit), but each change is a small, independent, well-scoped
  correction — not a single cohesive feature. No sub-agent TDD flow applies to markdown
  skill/agent instruction files or shell scripts of this shape.

## Work completed

PR [#69](https://github.com/mironyx/engineering-delivery-framework/pull/69), 4 commits:

1. **`hld-review`/`requirements-review` tool grants** — added `WebFetch`/`WebSearch` plus a
   matching "verify load-bearing external/regulatory claims" process step to both, mirroring
   `lld-review`'s existing pattern.
2. **Retro-driven fixes** (traced to real session-log evidence, not speculation):
   - `run-build.sh` (TS) now sources `.env.test.local` like `run-e2e.sh` already did.
   - `edf:test` now captures its own CWD and prefixes every resolved command with it —
     fixes worktree CWD drift in `/feature-team` that produced false-green verification.
   - `test-runner` reports the tail of failure output, not the head — fixes a confirmed
     false-pass where a chained `full`-mode typecheck failure was hidden behind an earlier
     passing stage's output.
   - `pr-review`'s 2-agent threshold now counts source-file diff lines only, excluding
     test files.
   - `feature-core` Step 4bF resolves `target_test_file` from convention instead of
     freehand construction.
3. **Same-branch correction:** the Step 4bF fix above initially cited the wrong kb file
   (`kb/conventions.md` instead of `kb/file-map.md` for `test-dir`) — caught by the
   self-audit below and fixed same-day.
4. **Self-audit fixes (7 High + 7 Medium of 14 found):** `feature-evaluator` CWD guard +
   scoped test run (was rerunning the full suite, violating `feature-core`'s own Rule 2);
   `lld_path`/`coverage_manifest` contract mismatches between `feature-core` and
   `feature-evaluator`; exit-code masking (`exit $(( ts_rc + py_rc ))`, mod-256 wraparound)
   across all seven `run-*.sh` dispatchers; an overly broad graceful-skip regex in
   `run-audit.sh` (TS) that could mask a real high/critical vulnerability finding; stale
   "first 10 lines" references left inconsistent after the tail-not-head fix; a missing
   fallback in `pr-review`'s test-file exclusion; an inaccurate summarizer claim in
   `test-runner.md`; no defense-in-depth path validation in `test-author`; `qa/SKILL.md`
   never executing the AC/Visual scenario categories it extracts; an advisory-only
   adversarial-test volume cap in `feature-evaluator`; and `feature-core`'s Critical Rules
   2/3/5 not documenting their own actual exceptions.

## Decisions made

- **Fix at the EDF-plugin level, not the downstream-project level, wherever the bug lives
  in a starter template or skill/agent file** — a project-local script fix doesn't help the
  next project that runs `/setup`. Applied the identical fix directly to
  `feature-comprehension-score`'s already-deployed `run-build.sh` as a one-off (uncommitted
  there — that repo's own commit/PR convention wasn't assumed).
- **Skip item #6 from the retro** (LLD Document Control merge conflicts in parallel
  `feature-end` runs) — user confirmed a `v2-requirements.md` proposal in the downstream
  project already covers it; duplicating the fix here would diverge from that plan.
- **Fix High + Medium self-audit findings now, leave Low as backlog** — per explicit user
  direction, not a unilateral severity cutoff.
- **feature-evaluator's Step 5 scoped to `test_files` instead of the full suite** — the
  simplest fix that satisfies both the CWD-guard need and Critical Rule 2 ("full suite
  runs once, nowhere else") simultaneously, rather than two separate patches.
- **Standardized the missing-LLD sentinel on `"none"`** (matching `test-author`'s existing
  convention) rather than inventing a third value, and updated `feature-evaluator` to
  handle it explicitly instead of leaving it undocumented.

## Review feedback addressed

No `edf:pr-review` pass was run against this PR — the work was done directly in
conversation rather than through `/feature-core`, so the standard Step 9 review-agent loop
doesn't apply here. The GitHub PR has no review comments (`reviews: []`, `reviewDecision`
empty). The only "review" this branch received was the self-audit described above, which
found and fixed its own regression (the `kb/conventions.md` → `kb/file-map.md` citation
error) before merge.

## LLD Sync report

Skipped — no LLD covers this issue. This is direct skill/agent/script authoring against
the plugin's own conventions (`CLAUDE.md`), not an implementation against a design doc.

## Cost retrospective

No Prometheus cost-checkpoint data exists for this session — it wasn't run through
`edf:feature-core`'s checkpoint mechanism (no `.env` / `EDF_FEATURE_PROM_DIR` configured in
this repo, and the work was conversational rather than pipeline-driven). Qualitative
retrospective instead:

- **Cost driver:** the three parallel audit agents (core pipeline, verification/review,
  test-authoring/QA) were the single largest spend in this session — each read 5-8 files in
  full plus cross-referenced actual repo state via Glob/Grep before reporting. Justified:
  the two agents that touched overlapping ground (core-pipeline and QA-layer) independently
  converged on the same `coverage_manifest` bug, which is exactly the kind of
  cross-validation that justifies the parallel-agent cost over a single sweep.
- **Rework:** one real rework cycle — the Step 4bF fix's wrong kb-file citation was caught
  by the *next* audit round rather than before the first push. **Improvement action:**
  when a fix references a specific convention file by name (e.g. "read kb/X for Y"),
  verify the claim against the actual starter template content before committing, not
  just before merging — a one-line `grep` would have caught this immediately instead of
  costing a second audit pass to surface it.
- **Scope discipline:** kept the PR to fixes traceable to concrete evidence (real session
  logs, or a verified cross-reference mismatch) rather than speculative "this looks
  slightly off" changes — avoided low-confidence churn in a plugin's core pipeline files.

## Next steps

- User flagged a broader idea — all skills should record problems they encounter into
  session logs as a standing behavior, not just via one-off audits like this one —
  explicitly deferred, not scheduled.
- Low-severity findings from the self-audit, left as backlog: Critical Rule 5 mislabels
  `edf:pr-review` as an agent type in one remaining place (functionally harmless since
  Step 9 already correctly invokes it as a Skill); `qa-explorer`/`qa-contracts` can
  duplicate findings on the same error/auth paths (cost/dedup issue, not correctness).
- The `run-typecheck`/`run-lint`/`run-build`/`run-e2e` wrapper scripts still don't
  summarize output the way `run-tests.sh` does (test-runner.md's claim about this was
  corrected to be accurate rather than the gap being closed) — extending the summarizer
  pattern to those four scripts is a real follow-up, not done here as it's a larger lift
  than a doc correction.
- Suggested next board item: none — this repo has no open-issue board item tied to this
  PR to suggest a follow-on from.
