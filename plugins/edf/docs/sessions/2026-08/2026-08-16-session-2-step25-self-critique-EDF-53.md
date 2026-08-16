# Session: Step 2.5 parse-then-navigability self-critique checks (EDF-53)

**Date:** 2026-08-16
**Issue:** [#53](https://github.com/mironyx/engineering-delivery-framework/issues/53) — v1-e1-3: Step 2.5 parse-then-navigability self-critique checks
**PR:** [#67](https://github.com/mironyx/engineering-delivery-framework/pull/67)
**Epic:** [#31](https://github.com/mironyx/engineering-delivery-framework/issues/31) — V1 E1.3 Skill Instructions & Quality Gates
**Track:** implemented directly in a teammate worktree (no `feature-core` cost checkpoints — see Cost retrospective)

## Approach rationale

The issue framed placement as load-bearing rather than cosmetic, so the work split into three
independent risks, each addressed before writing prose:

1. **Correctness of the parse claims.** The epic's standing rule — verify by measurement — exists
   because D5, D6 and #52's classDiagram finding all contradicted what the docs implied. The four
   parse cases were therefore re-measured against pinned mermaid 11.12.2 through the #47
   conformance harness before a single check was written, together with control cases designed to
   fail if the harness were not discriminating.
2. **Placement.** Inserting after *Attack surface / STRIDE-lite* and deleting the old trailing item
   are one change, not two. Leaving both would mean authors follow whichever they reach first.
3. **Not over-claiming.** #52 handed over a measured finding that `classDef` does nothing in a
   `classDiagram`. Any palette check that implied otherwise would emit a finding the author cannot
   act on — the same failure mode the D2 `link` constraint rules out.

Tests were written after the prose (unavoidable for a docs change), so they were mutation-checked
against the pre-change file to prove they can fail.

## Work completed

Rewrote `/lld` Step 2.5's diagram checks and repositioned them.

- **`plugins/edf/skills/lld/SKILL.md`** — replaced the single trailing "Diagram navigability" item
  with seven checks: parse · navigability · link path form · link target exists · link fragments
  resolve · palette applied · trust-boundary annotations. They now sit immediately after *Attack
  surface / STRIDE-lite* and before *Error paths*, with five items following them. Parse checks run
  first and gate the rest; on failure the gate names the offending block by diagram type and line
  and stops assessing that diagram. A report-format note requires every finding to name its
  offender and explicitly rejects "diagram could be improved".
- **`plugins/edf/skills/lld/flowchart.md`** — added the parse-gate branch (`All diagrams parse?` →
  report-and-skip, or the full check sequence), both paths rejoining the existing "Issues found?"
  node. New nodes assigned their palette classes.
- **`tests/test_lld_skill_step25_self_critique.py`** — 28 tests, covering all 13 BDD specs plus
  Invariants 7–14.
- **`plugins/edf/docs/design/v1/lld-v1-e1-3-skill-quality-gates.md`** — lld-sync updates (below).
- **`tests/test_lld_skill_step2_generation_rules.py`** — docstring only; #52's scoping note claimed
  Step 2.5 "still contains an `edf://` reference and `link` prose", which this change made false.
- **Versions** — `0.10.34` → `0.10.35`, read from `plugin.json` rather than assumed, with
  `marketplace.json` set to match.

### Measurements

All against pinned mermaid 11.12.2 via the #47 harness:

| Construct | Result | In the gate? |
|---|---|---|
| `click` in a `sequenceDiagram` | parse error | yes |
| `_self` on a `stateDiagram-v2` `click` | parse error | yes |
| `/` in a `classDiagram` identifier | parse error | yes |
| `;` in `Note` text | parse error | yes |
| sequence `link` directive | **parses** | **no — D2** |

Controls (all parse, confirming the harness discriminates rather than rejecting everything):
`stateDiagram-v2` click without `_self`, the `classDiagram` display-label workaround, `flowchart`
`click … _self`.

Palette styling, re-measured independently of #52:

```
flowchart        roles=[external] styledRoles=[external] ok=true
classDiagram     roles=[external] styledRoles=[]         ok=false
stateDiagram-v2  roles=[external] styledRoles=[external] ok=true
```

### Verification

- 28 new tests pass; full suite **434 passed**.
- **Mutation check:** against the pre-change `SKILL.md`, 23 of 28 fail.
- Edited `flowchart.md` run through the conformance harness — parses, all five palette roles styled.
- `ruff` clean on both touched test files.

## Decisions made

- **Seven flat checklist items, not the spec's three nested ones.** A markdown sub-bullet inherits
  its parent's verdict, which would have collapsed "path form" and "file existence" back into one
  check — the exact constraint the section exists to enforce. Recorded as a Correction.
- **No parse check for the sequence `link` directive**, per D2 and confirmed by measurement. It
  parses; checking it would report a non-error and teach authors to distrust the parse section.
- **The palette check asserts only on source-level consistency.** Given the measured classDiagram
  gap, asserting on rendered styling would produce an unfixable finding. The check states the gap
  so the gate does not chase it.
- **Fixing `template.md`'s classDiagram guidance was left out of scope**, per the handoff. It needs
  its own issue.
- **Invariants 1 and 2 need no carve-out.** #52 expected them to end up sharing carve-out wording.
  Deleting the old item removed both the fifth `edf://` and the `link <actor>` prose, so both greps
  are now satisfiable whole-file. The aligned wording is the *absence* of a carve-out.

## Review feedback addressed

None yet — PR #67 was opened for human review and had received no review comments at wrap-up time.
The merge was deliberately left to the lead session rather than performed here.

## LLD Sync report

```
## LLD Sync — Issue #53: Step 2.5 parse-then-navigability self-critique checks

### Corrections (spec was wrong)
- Checklist shape: §B.3.2 "Checks to state" nests path form, file existence and the #LLD-
  fragment check as sub-bullets under "Diagram navigability" → shipped as seven top-level
  items — a sub-bullet inherits its parent's single verdict, defeating the "two separate
  checks" constraint and Invariant 11's "two distinct bullets present".
- Palette check: spec says "every participant matching a defined role carries its class" and
  is silent on rendering → shipped with an explicit measured carve-out, because on the pinned
  mermaid a classDef applies NO styling in a classDiagram (works in flowchart and
  stateDiagram-v2). Applied verbatim the spec would emit a finding the author cannot fix.
- Invariant 1/2 alignment: #52's note predicted both would end up carrying the same carve-out
  wording → neither needs one. Deleting the old Step 2.5 item removed the fifth edf:// and the
  `link <actor>` prose, so both greps are satisfiable whole-file.

### Additions (not in spec)
- tests/test_lld_skill_step25_self_critique.py — 28 tests; the spec's file list named no test
  file. Mutation-checked against the pre-change SKILL.md (23/28 fail there), since a docs
  assertion suite never seen to fail is indistinguishable from one asserting nothing.
- flowchart.md parse-gate branch — the spec said "update if the branching changed"; it did.
  Verified through the #47 harness.

### Omissions (in spec but not built)
- None.

### Confirmations (notable)
- Parse-before-navigability ordering, the four measured parse cases, and the deliberate absence
  of a `link` parse check (D2) all shipped exactly as specified — and all four parse claims plus
  the `link` non-claim were independently re-measured rather than taken on trust.
- Path form uses design-root containment with `..` permitted; no `..` ban crept in.
- Placement immediately after "Attack surface / STRIDE-lite", with five items following.

### LLD updated
File: plugins/edf/docs/design/v1/lld-v1-e1-3-skill-quality-gates.md §B.3.2
Version: 0.2 → 0.3 (Status: Revised → Revised v2)
kb/: no changes — docs-only, no reusable helper touched.
Coverage manifest: coverage-v1-e1-3.yaml Story 3.2 entry → status Revised, files populated.
```

## Cost retrospective

**No usable cost data for this feature.** `query-feature-cost.py --stage final` returned
`$0.0000 / 0 tokens`, and the `ai-cost-final:0.0000` label reflects an empty scrape rather than a
real measurement. Root cause: `tag-session.py` wrote the prom file to
`/home/lgsok/projects/feature-comprehension-score/monitoring/textfile_collector/session_feature.prom`
— another project's collector — so nothing was scraped for this repo. The same will silently
affect every teammate session run from a worktree of this repo until the collector path is
resolved per-repo.

Qualitative observations, since the numbers are unavailable:

- **Measuring first was cheap and prevented rework.** Standing up the harness cost one `npm ci`
  plus two short scripts, and it settled five claims (four parse cases and the `link` non-claim)
  plus reproduced the classDiagram gap. Writing the checks first and validating later would have
  risked shipping a check for `link`, which the issue explicitly warns trains authors to distrust
  the section.
- **The mutation check earned its keep.** All 28 tests passed on first run, which is exactly the
  signal a docs test suite gives when it asserts nothing. Running them against the pre-change file
  (23/28 failing) was the only evidence they had teeth.
- **No fix cycles.** Full suite green on the first complete run; the sole failure was pre-existing
  on `origin/main`.

**Improvement actions:**

1. Fix `tag-session.py`'s collector-path resolution so cost data is captured per-repo — otherwise
   every parallel teammate session in this repo produces a misleading `ai-cost-final:0.0000`.
2. Adopt the mutation check as standard for docs-only test suites in this epic: run new assertions
   against the pre-change file and record the failure count in the PR.
3. `update-coverage-manifest.py --verify-anchors` reports "file not found" for every entry in this
   repo (both #52's and #53's) because it resolves LLD paths from repo root as `docs/design/…`,
   while this repo nests them under `plugins/edf/docs/design/…`. The anchors themselves are
   present and correct. Worth its own issue.

## Next steps

- **Merge PR #67** — deliberately left to the lead session for human review.
- **File: `template.md` classDiagram palette guidance.** The measured gap means the template
  currently instructs authors to apply a palette that a `classDiagram` will not render. Out of
  scope for #53; needs its own issue.
- **File: `feature-core` `edf:xxx` false positive.** `tests/test_cross_references.py::
  test_feature_core_refers_real_agents` fails on a clean `origin/main` checkout (verified at
  `e7b53d3`) — `feature-core/SKILL.md` uses `edf:xxx` as a prose placeholder and the test's regex
  reads it as a real agent reference.
- **File: cost-collector path** and **manifest anchor-verifier path** issues, per the cost
  retrospective.
- Epic #31 Story 3.2 closes with this PR; both epic tasks (T1 #52, T2 #53) are then complete.
