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
