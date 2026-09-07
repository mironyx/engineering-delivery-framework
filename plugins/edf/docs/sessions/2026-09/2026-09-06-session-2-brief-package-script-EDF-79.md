# Session log — [EDF-79]

## Approach rationale
- **Issue:** #79
- **Approach chosen:** Added `plugins/edf/bin/brief-package.sh`, modeled directly on
  `review-package.sh`'s "write once, pass a path" pattern. It resolves the issue's
  `## Design reference` link to an `LLD-...` anchor and extracts only that LLD section
  (heading-bounded, fenced-code-aware), resolves the matching `REQ-...` anchor via the
  coverage manifest (or directly from the issue body) and extracts only that requirements
  section, and pulls the issue's `## Acceptance criteria` section verbatim — all into one
  git-ignored `.edf/brief-<N>.md` file. Every extraction has a full-file fallback (never a
  silent omission) if an anchor can't be resolved, per the issue's explicit constraint that
  this is a token-efficiency change, not a scope reduction.
- **LLD deviations:** none — no LLD exists for this issue (pure tooling/process change).
- **Pressure:** heavy — `brief-package.sh` alone is ~230 lines of shell (excluding its
  header comment), which crosses the 150-line Heavy threshold on a single file. Still on
  the Standard/Heavy track (test-agent → implement, full diag, evaluator) per the table —
  Heavy doesn't change the track, just flags "consider splitting" (not warranted here: the
  script is one cohesive unit, splitting it would fragment one algorithm across files).

## Redesign — scoping was too aggressive (post-review, pre-merge)

After PR #87 passed review, the user pushed back on the extraction scope itself, not just
implementation bugs: extracting only `## Acceptance criteria` from the issue silently
dropped sibling sections (BDD specs, Files to create/modify, HLD reference — confirmed via
issue #50's real body) that `test-author`/`feature-evaluator` used to see in full. Worse,
a single-anchor LLD extract drops the paired Part A "design rationale" section every LLD
story has under this repo's ADR-0026 Part A/Part B convention (confirmed structurally
identical across all 3 real LLD files in this repo — `## N.M <title>` in Part A mirrors
`## N.M <title> — Implementation` in Part B) — the "why" (constraints, rejected
alternatives, open defects) without which the "how" alone can be misread. This is a
different failure class than the earlier fixes: the fallback safety net (never omit
silently) only fires when an anchor fails to resolve; it does nothing when resolution
*succeeds* but resolves to an incomplete subset — there is no "found but incomplete"
signal for an agent to notice.

**Redesign, applied to the same script:**
1. Issue: always include the full body verbatim — it's already small (50-150 lines), so
   heading-scoping it was optimizing a resource that was never the cost problem, and it's
   exactly what dropped BDD specs, etc. Removed the AC-only extraction path entirely (and
   its "acceptance-criteria" stdout status field, now meaningless).
2. LLD: resolve *every* `#LLD-...` anchor in the issue's Design reference section (not just
   the first — `head -1` dropped in favour of `mapfile` + a loop), and for each anchor pair
   its Part B section with the same-numbered Part A section (new `extract_part_a_region` +
   `extract_by_heading_number` helpers; task number parsed from Part B's own heading via a
   new `task_number_of` helper). Deliberately excludes the HLD and any ADRs the issue
   references — those are large, project-wide documents in their own right; pulling them in
   would reopen the exact re-reading cost #79 exists to close, and an LLD section is
   expected to already carry whatever HLD/ADR context a story needs.
3. Requirements: union REQ- anchors from direct issue-body mentions with the coverage-
   manifest lookup for *every* resolved LLD anchor (previously one lookup keyed on one
   anchor).
4. Kept from the prior round, unaffected: anchor-grep scoped to the Design reference
   section first (falls back to whole-body only if that section is missing);
   `extract_by_heading_text`'s `matched` flag + `END { exit 1 }` fix; full-file fallback on
   total resolution failure.

**Implementation bugs hit and fixed while rewriting, before any review:**
- `${#ARRAY[@]:-0}` is invalid bash (can't combine array-length with a `:-` default) —
  `set -u` made this fatal immediately. Fixed by always `declare -a ARRAY=()` up front
  instead of relying on `:-` fallbacks at every use site.
- The task-number-to-Part-A-section matcher originally built a dynamic awk regex with a
  shell-side `sed 's/\./\\./g'` escape for the literal dot in "2.3" — gawk's `-v`
  assignment strips backslash escapes it doesn't recognize as C-style sequences (with a
  warning), so the escape never survived into the regex and "2.3" would have also matched
  "2x3". Rewrote `extract_by_heading_number` as plain awk string comparison
  (`substr(rest,1,tlen)==tasknum` + a boundary check on the next char) — no dynamic regex,
  no escaping round-trip, and it's the more correct fix, not just a working one.
- The heading-level calc for the new matcher had to line up with the other 3 extractor
  functions' `RLENGTH-1` convention (single `[ \t]` in the match, not `[ \t]+`) — using `+`
  would have overcounted the level on a heading with extra whitespace and corrupted the
  section-boundary check.

**Testing:** manually verified the boundary fix against issue #50's real LLD
(`grep -n "## LLD context|### LLD-|#### Part A|#### Part B|## 2.4 Packaging"`) before
touching the test suite — confirmed Part A stops exactly before Part B's own heading (no
bleed into the next task's Part A). Rewrote `TestBriefPackage`: updated the two existing
anchor-resolution tests for the new stdout/body shape, dropped the now-meaningless
AC-fallback test (there's nothing to fall back from — the body is always in full), added
tests for full-body inclusion with no AC heading (issue #1) and LLD-fallback-to-full-file
when no anchor is referenced at all (issue #1 again, real fixture, no synthesis needed).
Hit a Windows-specific mojibake issue while editing: unicode em-dash/section-sign (`—`,
`§`) characters typed into new test-assertion strings came out as `<REPLACEMENT CHAR>`
bytes in the file — did not chase the root cause (likely an encoding mismatch somewhere in
the edit path on this Windows box), just rewrote those specific assertions to avoid
non-ASCII literals (`"Part A" in body and "2.3" in body` instead of a single unicode
string) — more robust anyway, since it no longer depends on exact heading punctuation.
Spawned `edf:feature-evaluator` against the redesign specifically (not `gh issue view 79`,
since this isn't a separate issue — six explicit acceptance criteria for the redesign
itself, described in the agent prompt). Verdict: PASS WITH WARNINGS. It correctly
identified that no real closed issue/LLD in this repo exercises the two new code paths
(multi-anchor Design reference, task-number boundary collision) and wrote two adversarial
tests: one with a synthetic decoy LLD file (real stable anchor from issue #50, fabricated
sibling sections "2.30" and "12.3" to prove the boundary check rejects both), and one with
a `gh` shim on `$PATH` that returns a synthetic multi-anchor issue body while the LLD file
and coverage manifest underneath stay entirely real (`_LLD_FIXTURE`/`_REQ_FIXTURE`) — both
passed. It also flagged a silent-failure asymmetry: the manifest req/lld lookup dropped an
anchor with no warning if a manifest entry ever had its `req:`/`lld:` fields in the
unexpected order (works today because every manifest in this repo has them in the expected
order), unlike every other resolution-failure path in the script, which does warn — fixed
by adding the missing `echo ... >&2` for symmetry. 459 passed, 18 pre-existing skips after
all fixes.

## Follow-up — measuring whether brief_path actually saves tokens

User raised a real risk the redesign didn't address: `test-author`/`feature-evaluator`'s
"fall back to full docs if the brief looks thin" escape hatch means a bad brief costs
*more* than no brief at all (brief read + full-doc read, strictly worse than the
pre-#79 baseline of one full-doc read) — and nothing recorded whether this ever happens.
Considered putting the signal in the session log alone; rejected as the primary mechanism
since nothing aggregates session logs automatically across cycles (though `/retro` does
mine them, so it's not a bad *secondary* location). Instead: added a `Brief usage` field
to `test-author`'s Output report and `feature-evaluator`'s 15-line return contract (`used
as-is | fell back (<reason>) | none provided`), and updated `feature-core` Step 4bF/6b to
(a) fold that fact into the existing cost-checkpoint note — which already captures
cumulative cost/tokens from Prometheus at that exact step, so a fallback's cost impact is
directly attributable — and (b) append it to the session log's Concerns & Deferred Items
section immediately on a fallback, matching how every other deviation in this pipeline
gets surfaced. This reuses existing infrastructure (checkpoints, session log) rather than
inventing a new metrics path, and a future `/retro` or dedicated audit script can
`grep -rh "fell back" docs/sessions/**/*.md` across many cycles to see how often the
mechanism actually degrades. Doc-only change (agent `.md` files + `feature-core/SKILL.md`)
— no code, so the existing 460-test suite is unaffected and stayed green.

## Process deviation (recorded, not hidden)
Implemented `brief-package.sh` and hand-validated it against real anchors in this repo's
own dogfooded LLD/requirements docs (issue #50's `LLD-v1-e1-2-command-wiring` /
`REQ-vscode-extension-review-feedback-...` pair) *before* writing the pytest test file —
the reverse of the prescribed test-author-first flow. Rationale: there is no separate
product spec/LLD to write tests against here (the issue body *is* the full spec — a
mechanical extraction algorithm), and manual validation against real anchors caught the
"requirements coverage-manifest req: line precedes lld: line" ordering bug and a duplicate
heading cosmetic issue immediately, which a test-first pass without ground-truth fixtures
would likely have missed too. Tests were then written to match `review-package.sh`'s
existing `tests/test_shell_scripts.py` suite conventions before proceeding to full
verification.

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|

## Concerns & Deferred Items

- `pr-review/prompts/agent-c.md` (design-conformance, "Agent C" — issue #79 called it
  "Agent A") already extracts only the referenced doc *section* per design-reference
  comment, not the full LLD file — so AC item 4 ("update pr-review Step 9's
  design-conformance path... if it independently re-reads the full LLD") required no
  change. Verified by reading `agent-c.md` Step 2 before concluding this.
- **Pre-existing environment gap, out of scope:** this repo has no root `pyproject.toml`,
  so the starters' `run-tests.sh p` / `run-typecheck.sh p` / `run-lint.sh p` wrappers (which
  `exec uv run ...`) fail with "Failed to spawn" here — unrelated to this change. Verified
  no regressions by running `python -m pytest tests/ -q` directly (454 passed, 18
  pre-existing skips) and `bash -n` on the new script. `shellcheck`/`ruff` are also not
  installed locally, so lint could not be run at all for this change; the script was
  written to match `review-package.sh`'s existing style (`set -euo pipefail`, quoted
  variables) as the closest available substitute for automated lint.
- **`edf:diag` gate could not run in this environment:** diagnostics-exporter has no
  active VS Code editor session attached (opening the files produced no export after two
  waits), the CodeScene MCP server is not configured/connected in this session, and
  SonarQube MCP reports `CONNECTION_CLOSED`. All three are environment/tooling
  availability issues, not something introduced by this change. Substituted manual review
  of `brief-package.sh` against `review-package.sh`'s style and structure, plus the
  hand-validated extraction tests above.
- **Evaluator findings (PASS WITH WARNINGS), both addressed:** (1) missing self-ignore
  test for the default `.edf/.gitignore` write path — evaluator added
  `test_default_output_path_is_self_ignoring` (now 8 tests, all passing). (2) two silent
  degradation paths in `brief-package.sh`: a failed `gh issue view --json body` call
  silently produced an empty body instead of failing loudly (fixed — now matches the
  title-fetch's hard-fail pattern); a missing `--requirements` file was silently skipped
  in the fallback loop while `REQ_STATUS` still reported the originally-requested count
  (fixed — status now reports the actually-included count, and a warning is printed to
  stderr for each skipped path). Full suite re-run clean after both fixes: 455 passed, 18
  pre-existing skips.
- **`edf:pr-review` findings on PR #87 (2 warn + 1 block), all fixed:** (1) [warn/bug]
  `brief-package.sh`'s LLD anchor grep scanned the whole issue body instead of just the
  "## Design reference" link its own header comment claimed — fixed to scope to that
  section first, falling back to whole-body search only if the section isn't found. (2)
  [warn/justification] the brief-build step ran unconditionally in Step 3's shared
  preamble, so Light-track issues paid for a `gh` call and file write that Step 4L never
  consumes — moved into Step 4bF (Full track only), and `flowchart.md` updated to match.
  (3) [block/silent-swallow] the brief-script-failure fallback in Step 3 didn't say to log
  the failure anywhere — Step 4bF's version now instructs appending it to the session
  log's Concerns section immediately. Full suite re-run clean after all three fixes: 455
  passed, 18 pre-existing skips.
- **Second re-review pass found a real bug in the fix itself:** `extract_by_heading_text`'s
  awk never exited non-zero on a no-match (only a missing file did), so the caller's
  fallback-to-full-body path for "no Acceptance Criteria heading found" was dead code — an
  issue without that heading would silently get an empty "resolved" section instead of the
  documented fallback. Fixed with a `matched` flag + `END { if (!matched) exit 1 }`.
  Added regression test `test_ac_extraction_falls_back_when_no_heading_found` (using issue
  #1, which has no AC heading) — this is exactly the kind of gap a hand-crafted fixture
  wouldn't have caught since I only ever tested against issues that DO have the heading.
  Also fixed two stale "from Step 3" cross-references in `feature-core/SKILL.md` left over
  from the earlier fix that moved the brief-build step into Step 4bF. A final targeted
  re-review pass reported no further findings. 456 passed, 18 pre-existing skips.
| 3c | 2026-09-06T15:19:18Z | unavailable | unavailable | pressure: heavy - brief-package.sh ~230 lines single file, no split warranted |
| 5 | 2026-09-06T15:30:21Z | unavailable | unavailable | green — 454 passed (pytest direct; run-tests.sh wrapper blocked by pre-existing missing pyproject.toml) |
| 6 | 2026-09-06T15:32:09Z | unavailable | unavailable | diag tooling unavailable in this environment (no editor, no CodeScene MCP, SonarQube down) - manual review substituted |
| 6b | 2026-09-06T15:41:29Z | unavailable | unavailable | evaluator: PASS WITH WARNINGS - 1 coverage gap + 2 silent-failure risks, both fixed |
| 8 | 2026-09-06T15:43:40Z | unavailable | unavailable | [PR #87](https://github.com/mironyx/engineering-delivery-framework/pull/87) |
| 9 | 2026-09-06T16:08:40Z | unavailable | unavailable | review clean after 2 rounds - 5 findings fixed total, final re-check clean |
| 10 | 2026-09-06T16:09:14Z | unavailable | unavailable | report done - no CI configured in this repo, tests verified locally |
| 9b | 2026-09-06T18:07:59Z | unavailable | unavailable | redesign review: 2 rounds, 2 real bugs fixed (anchor-less design-ref widening, unescaped manifest regex), final check clean |
| 9c | 2026-09-06T18:32:17Z | unavailable | unavailable | brief-usage tracking added and reviewed - 1 casing fix, clean after |

## Work completed

PR: [#87](https://github.com/mironyx/engineering-delivery-framework/pull/87) — closes #79.

- `plugins/edf/bin/brief-package.sh` (new, ~427 lines) — packages a per-issue brief (full
  issue body + paired LLD Part A/Part B sections for every referenced anchor + matching
  requirements sections, via ADR-0026 stable IDs and the coverage manifest) into a
  git-ignored file, modeled on `review-package.sh`'s "write once, pass a path" pattern.
- `plugins/edf/skills/feature-core/SKILL.md` — Step 4bF builds the brief once (Full track
  only) and threads `brief_path` into `edf:test-author` and `edf:feature-evaluator`; both
  agents' checkpoint-note instructions now surface a `brief_path` fallback if one occurs.
- `plugins/edf/agents/test-author.md`, `plugins/edf/agents/feature-evaluator.md` — accept
  `brief_path`, prefer it over `requirements_paths`/`lld_path` when sufficient, fall back
  otherwise; both now report a `Brief usage` field (`used as-is | fell back (<reason>) |
  none provided`) so fallback frequency is observable across cycles.
- `plugins/edf/skills/feature-core/flowchart.md` — brief-build node moved into the Full
  track subgraph to match where it actually runs.
- `tests/test_shell_scripts.py` — 13 tests in `TestBriefPackage`, covering anchor
  resolution, Part A/Part B pairing and boundary-exactness, multi-anchor union, every
  fallback path, and the self-ignoring output directory.
- Plugin versions: `0.10.59` → `0.10.61` (three bumps across the review/redesign cycle).

## Decisions made

- **Scope widened mid-review** (see `## Redesign` above): the first shipped version
  extracted only the issue's AC section and a single LLD Part B section. User feedback
  (not a pr-review finding — a direct design-risk question) identified this as unsafe:
  the fallback-to-full-content safety net only covers "anchor not found," not "resolved
  but incomplete," and there is no signal for the latter. Widened to full issue body +
  every referenced LLD anchor's Part A/Part B pair + the requirements union. HLD/ADRs
  stayed deliberately out of scope — pulling those in would reopen the re-reading cost
  this issue exists to close.
- **No LLD deviation** — this issue has no design doc; `brief-package.sh`'s own algorithm
  (anchor-based section extraction, Part A/B pairing by task number, fallback-never-omits)
  is exactly as specified across the issue body and the follow-on user conversation, not a
  deviation from a pre-existing spec.
- **`pr-review`'s design-conformance agent (`agent-c.md`) needed no change** — it already
  scoped LLD reads to the referenced section per-file design-reference comments, which was
  issue #79's conditional AC item 4. Verified by reading the agent prompt before concluding.

## Review feedback addressed

Three separate review rounds on this PR, all findings fixed (see `## Concerns & Deferred
Items` above for full detail per round):
1. **`edf:feature-evaluator` (first pass):** 1 coverage gap (missing self-ignore test) + 2
   silent-degradation paths (`gh` body-fetch failure, missing `--requirements` file) — all
   fixed.
2. **`edf:pr-review` (first pass, 2 rounds):** anchor-grep scoping, brief-build step placed
   in the wrong pipeline stage, missing failure-log instruction, and (on re-review) a real
   bug where `extract_by_heading_text` never signaled "not found" — all fixed, plus 2 stale
   cross-references.
3. **`edf:feature-evaluator` + `edf:pr-review` (redesign pass, 2 rounds):** 2 coverage gaps
   in the widened-scope tests (multi-anchor, task-number boundary) + 2 real bugs
   (anchor-less Design reference section incorrectly widening the search, an unescaped
   dynamic-regex bug in the coverage-manifest lookup) — all fixed, plus 1 casing
   inconsistency in the `brief_path`-fallback tracking follow-up.

No CI is configured in this repo (confirmed via `gh pr checks` and a background
`edf:ci-probe` run) — nothing to reconcile there.

## LLD Sync report

Skipped — no LLD covers this issue (confirmed in the PR body's Design reference field:
"none — internal plugin tooling issue, no LLD").

## Cost retrospective

**No numeric data available.** Prometheus was unreachable throughout this feature (every
cost-checkpoint row above reads "unavailable"; the Step 2.5 final-cost query also returned
"Prometheus unreachable" — posted to the PR as-is). This retrospective is therefore
structural (round counts, rework shape), not token/dollar-denominated.

**Cost driver: 3 separate review rounds, not 1.** A typical Full-track feature clears
`edf:pr-review` once. This one needed three: an initial implementation pass, a scope
redesign the user requested mid-review (after the first review had already passed clean —
not itself a review finding), and a follow-up feature (fallback-rate tracking) the user
asked for afterward. Each redesign/addition round re-triggered its own evaluator +
pr-review cycle. The redesign round alone found 2 real implementation bugs on top of the
2 coverage gaps its own evaluator pass caught — meaning the *first* implementation of the
widened scope wasn't clean either; it needed the same fix-evaluate-review loop as the
original.

**Improvement for next time:** two of the three rounds trace to the same root cause — the
original scope (single-heading, single-anchor extraction) was implemented and shipped
before its design was stress-tested against a "what could this miss" question. That
question surfaced real, structural gaps (dropped BDD specs, dropped Part A rationale) that
no amount of unit testing of the *implemented* algorithm would have caught, because the
tests were written against the same (too-narrow) understanding of what the brief needed to
contain. For a **new extraction/summarization algorithm** specifically (as opposed to a
bug fix or a well-specified feature), doing one explicit "what could a reader of this
output be missing?" pass against a real example *before* writing tests — not just before
shipping — would likely have caught the Part A/BDD-specs gap in the first round instead of
the second.

**What went right, worth repeating:** hand-validating the extraction script against real,
already-merged issues/LLDs in this repo (issue #50, issue #1) before writing the pytest
suite caught two real bugs (a manifest field-ordering assumption, a duplicate-heading
cosmetic issue) that a synthetic-fixture-first approach likely would have missed, since the
synthetic fixtures would have encoded the same assumptions as the implementation. The
evaluator's own synthetic-fixture tests (a `gh` shim for multi-anchor issues, a decoy LLD
file for task-number boundaries) were the right call *in addition to* the real-fixture
tests, for the code paths no real issue in this repo happens to exercise yet — real
fixtures first, synthetic fixtures to fill the gaps real ones can't reach.

## Next steps

- Issue #83 ("trim feature-evaluator's duplicate implementation read and adopt
  brief_path") explicitly depends on this landing — its Step 6-fold part is independent
  and could ship regardless, but its `brief_path` adoption part now has a real mechanism
  to adopt.
- The `Brief usage` fallback-rate tracking added in this PR has no data yet — it only
  starts producing signal once Full-track features that pass `brief_path` actually run.
  Revisit after a handful of cycles (via `grep -rh "fell back" docs/sessions/**/*.md`) to
  see whether the mechanism holds up in practice or needs another round of scope
  adjustment.
- This repo's own local dev environment gaps (no `pyproject.toml` for `uv run pytest`,
  `shellcheck`/`ruff` not installed, no CodeScene MCP configured, SonarQube connection
  down) blocked `edf:diag` and the standard `run-tests.sh`/`run-lint.sh` wrappers for the
  entire feature — every verification ran via direct `pytest`/`bash -n` substitutes
  instead. Worth a dedicated setup pass if `edf:diag` is expected to gate future work on
  this repo's own plugin code, not just downstream projects that adopt EDF.
