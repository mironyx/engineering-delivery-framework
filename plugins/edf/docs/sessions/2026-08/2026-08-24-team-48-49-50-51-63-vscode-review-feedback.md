# Team Session — V1 E1.2 VSCode Extension: Review Feedback (epic #30)

Lead's orchestration log for the full `/feature-team epic 30` run. Per-issue logs carry the
implementation detail; this captures the lead view that spans all five tasks.

## Issues shipped

| Issue | Story | PR | Branch | Merged |
|-------|-------|-----|--------|--------|
| #48 | 2.1 scaffold + test harness | #68 | feat/insert-review-command (scaffold) | 2026-08-22 |
| #49 | 2.2 heading extraction + insertion modules | #72 | feat/insert-review-command | 2026-08-22 |
| #50 | 2.3 insert review comment command + target resolution | #73 | feat/insert-review-command | 2026-08-23 |
| #51 | 2.4 vsix packaging + recorded security review | #74 | feat/vsix-packaging | 2026-08-24 |
| #63 | 2.5 diagram click-through overlay | #75 | feat/diagram-click-through | 2026-08-24 |

## Cross-cutting decisions

- **Target resolution simplified three times under maintainer direction (0.6 → 0.7 → 0.8).** The
  first implemented shape was a recency-stack walk with a single-visible-editor fallback (0.6).
  The maintainer rejected the fallback chain outright: "no name - stop, there is a name - find in
  MRU. if unique - good. if not unique - ask to close the wrong one... if we cannot do this we
  should stop and again not guess." That became the 0.7 title-anchored never-guess algorithm, and
  the 0.8 delta closed two edge cases the maintainer named: seed the MRU stack from
  `visibleTextEditors` at activation (the tracker otherwise starts empty on the first command after
  a lazy activation), and reword the zero-match message to tell the user to open the original
  markdown file (the reachable cases are the source editor being closed with/without a restart,
  not just eviction from the bounded stack).
- **Necessity gate added to the design pipeline.** The redesign churn was the direct result of
  under-specification: fallback branches accreted during design with no reachable triggering
  scenario. The maintainer asked "can we improve our skills to choose more simple solutions" —
  answered by adding a necessity gate to the `lld` skill's self-critique, the `lld-review` agent,
  and a new "fallback accretion" anti-pattern (plugin 0.10.45). Every `alt`/`else`/fallback branch
  must now name a concrete input state; branches that cannot are cut, not kept "for safety".
- **Extension ships as a committed `.vsix`.** The maintainer wants to install the extension from
  the repo without a marketplace. The built artifact is committed and pushed
  (`extensions/edf-review/edf-review-0.2.1.vsix` after the overlay merged; `0.2.0` was the
  pre-overlay build), plus `extensions/edf-review/build-vsix.sh` for reproducible rebuilds. Model:
  plugin install carries the `.vsix`; installing into VS Code stays a separate, manual, opt-in step.

## Coordination events

- **Human review gate held throughout.** Every PR was surfaced for review and the lead only
  forwarded `edf:feature-end` after a verbatim user trigger. #50 received two `/edf:feature-end`
  invocations — the second was blocked (already forwarded, teammate mid-run) to avoid a duplicate
  merge attempt.
- **teammate-50 died mid-feature-end** (API error 402 Insufficient Balance) while running the final
  cost query. Resumed via agentId; the cost labels had already been applied so the idempotency
  check skipped the repeat query. No work lost.
- **teammate-63 repeatedly ended its turn while a background test suite ran** (twice, before its
  PR opened). Resumed with an explicit directive to run tests synchronously and stay in the loop
  until the PR was open; PR #75 landed after the second resume.
- **Model drift mid-epic.** The session ran Sonnet 5 through Waves 1–4, then the maintainer
  switched to Haiku 4.5 before Wave 5 spawned. Teammates inherit the lead's model (`model: inherit`),
  so teammate-63 implemented the overlay on Haiku — plausibly contributing to its turn-ending
  behaviour. Flagged to the maintainer; they kept the Haiku teammate and it delivered.
- **No GitHub Actions CI in this repo.** The sole check on every PR is the external "Comprehension
  Check" app (app.mironyx.dev), pending human input. All verification was local
  (@vscode/test-electron host, tsc strict, vsce package, install parity).
- **`gh-project-status.sh` CRLF bug.** Both #51 and #63 hit a pre-existing CRLF config-parsing bug
  (`.github/project.env` line endings) and worked around it (`gh project item-edit` / `sed`
  CR-strip). The script itself was fixed earlier (commit `44f9181`, plugin 0.10.44) but the env-file
  parsing still bites on Windows.

## What worked / what didn't

- **Worked:** the maintainer-driven simplification loop. The 0.6 fallback chain (tracker walk +
  visible-editor fallback) was exactly the fallback-accretion the necessity gate now catches; the
  final algorithm is ~5 lines of decision logic with a bounded stack, and every stop branch names
  its reachable cause. The seeded tracker + open-original-file message closed the two real
  first-use/closed-source cases with no guessing.
- **Worked:** commit the `.vsix` to the repo. The maintainer can `git pull` and install directly;
  the build script makes the artifact reproducible rather than a one-off.
- **Didn't:** teammate-63's Haiku turn-ending. Two lead resumes were needed just to get a PR open.
  Cost of running the final, most fiddly task (webview DOM + containment validation) on the
  cheapest model.
- **Didn't:** cost tracking. Every checkpoint is $0.0000 — Prometheus is unreachable from this
  repo, so the "cost" labels are placeholders. The real effort driver was the 3x target-resolution
  redesign, not tokens.

## Process notes for `edf:retro`

- Fallback accretion is now a first-class anti-pattern with a necessity gate at design time — the
  #50 churn should not recur. Validate at LLD self-critique, not review.
- Wave 5 ran on Haiku by accident of the lead's `/model` switch; feature-team's `model: inherit`
  is correct but the lead should confirm the session model before spawning a design-heavy wave.
- A teammate that repeatedly ends turns mid-background-test should be resumed with a "run
  synchronously and stay in the loop" directive rather than re-spawned (context is worth keeping).
- The `.vsix`-in-repo shipping model should be documented in the extension README (`build-vsix.sh`,
  install command, bump-version-before-rebuild note).
