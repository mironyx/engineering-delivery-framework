# Session log — EDF-52

## Approach rationale

- **Issue:** #52
- **Approach chosen:** Rewrite the `Diagram generation rules` block of `SKILL.md` Step 2 as
  four numbered concerns (type selection, palette, link emission, annotation) plus a
  co-versioning rule, each concern carrying its worked example inline in the same block as
  the rule rather than in a separate examples section. Every value, gate and matrix row is
  referenced by template section name, never restated.
- **LLD deviations:** none to the rule content. One structural simplification — the LLD's
  Part B lists the rules and the worked examples as two separate structures ("Rules to
  state", "Worked examples — required shape"). Emitting them as two sections in `SKILL.md`
  would produce eight blocks and force a rule↔example cross-reference. Folding each example
  under its own rule gives four blocks, no cross-references, and less prompt text loaded on
  every `/lld` run — which is the constraint the LLD itself states. The acceptance criteria
  are unchanged: each of the four concerns still carries a worked example.
- **Pressure:** Standard — see below.

### Step 3b — LLD challenge

1. **Does the LLD reinvent something the repo already has?** No. `template.md` (epic #28)
   already holds the canonical palette table, the tie-break, the support matrix, the path
   form and the identifier constraint. The LLD's central instruction is to *reference* those
   rather than restate them, which is the opposite of reinvention. The test module reuses the
   established sibling pattern in `tests/test_lld_template_link_forms.py`.
2. **Is there a simpler way to get the same behaviour?** Yes, and it is counted: four blocks
   instead of eight, and zero rule↔example cross-references instead of four (see LLD
   deviations above).
3. **Would you build it this way if the LLD didn't exist?** Yes. Reference-not-restate is
   forced by Design Principle 6, and one worked example per rule is what makes a generation
   rule mechanical rather than remembered.

## Cost checkpoints

| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-08-16T10:00:40Z | $0.00 | 0 in / 0 out | pressure: Standard — docs-only rule rewrite (~100 lines prompt text) plus a new 12-property test module; rounded up from Light per the doubt rule |
| 4bF | 2026-08-16T10:07:08Z | $0.00 | 0 in / 0 out | test-author complete — 16 tests over 14 properties + D5/D6 + version parity, no spec gaps |
| 4dF | 2026-08-16T10:07:08Z | $0.00 | 0 in / 0 out | implementation complete — 16/16 green; examples verified against mermaid 11.12.2 via the #47 conformance harness |
| 5 | 2026-08-16T10:09:13Z | $0.00 | 0 in / 0 out | green on attempt 2 (16/16 target; 406/407 suite — 1 pre-existing unrelated failure on main: test_cross_references edf:xxx placeholder in feature-core). ruff clean. No .diagnostics input in worktree |
| 6b | 2026-08-16T10:10:59Z | $0.00 | 0 in / 0 out | evaluator: PASS — 15/15 ACs covered, 0 adversarial tests written, no gaps |
| 8 | 2026-08-16T10:12:07Z | $0.00 | 0 in / 0 out | [PR #66](https://github.com/mironyx/engineering-delivery-framework/pull/66) |
| 9 | 2026-08-16T10:19:47Z | $0.00 | 0 in / 0 out | review: 2 test blockers fixed (inverted NEGATION guard, non-local content-signal search), 2 tautological assertions tightened, no-emit reason and Step 2.5 contradiction marker added; mutation-tested |
| 10 | 2026-08-16T10:21:03Z | $0.00 | 0 in / 0 out | report done — PR #66 open for human review; only check is the human-gated Comprehension Check |

## Reviewer-facing concerns (carried from PR #66 body, recorded here per lead request)

Four items raised for human attention before merge, none blocking, none fixed as part of #52:

1. **Self-caught bug in the task's own test suite.** During review, an inverted assertion was
   found that checked for the *opposite* of D6 — it passed when `classDef` was (wrongly)
   treated as globally scoped across fenced blocks. The author had noticed the assertion read
   awkwardly while writing it and bent the prose to satisfy it rather than question it. Fixed,
   and all three test corrections from this review pass are now mutation-tested (removing the
   property they check genuinely fails the test).
2. **New measured finding, out of #52's scope, not fixed — only flagged.** `classDef` +
   `class X role` in a `classDiagram` renders with **zero styling applied**; the identical
   construct in a `flowchart` styles correctly. Measured via the #47 conformance harness, not
   assumed. Possible gap in `template.md`'s "every diagram carries its own `classDef`"
   guidance, which reads as type-independent but isn't. Candidate for a follow-up issue
   alongside #60–#62.
3. **Deliberate scope split, needs lead/human sign-off.** Step 2.5's self-critique checklist
   still asserts the old `edf://`/`..`-ban claims that Step 2 now contradicts, so `SKILL.md`
   briefly disagrees with itself. Rewriting Step 2.5 is task #53's job; a `TODO(#53)` marker
   was left in place rather than doing #53's work early. One `edf://` reference remains in
   `SKILL.md` (Step 2.5, line 283) for exactly this reason — not an oversight.
4. **Two pre-existing, unrelated issues observed, not introduced or fixed here:**
   `test_cross_references` fails on `main` too (an `edf:xxx` placeholder in feature-core's
   prose); and `run-tests.sh` cannot spawn `pytest` in this environment (`uv run --with pytest`
   works as a substitute).

## Work completed

Rewrote the "Diagram generation rules" block of `plugins/edf/skills/lld/SKILL.md` Step 2 so the
template's conventions are applied mechanically rather than remembered.

- **PR:** [#66](https://github.com/mironyx/engineering-delivery-framework/pull/66)
- **Key files:**
  - `plugins/edf/skills/lld/SKILL.md` — Step 2 rules (co-versioning rule, four concerns each
    with a worked example, retained decomposition rule, rewritten syntax rule); plus a
    `TODO(#53)` marker on the Step 2.5 navigability item.
  - `tests/test_lld_skill_step2_generation_rules.py` — new, 16 tests.
  - `plugins/edf/.claude-plugin/plugin.json` / `.claude-plugin/marketplace.json` — 0.10.34.
- **Tests added:** 16 (all passing). Full suite 406/407 — the single failure is pre-existing on
  `main` and unrelated.
- **All four Step 2 `edf://` references removed.** The fifth occurrence is inside Step 2.5 and
  belongs to task #53, exactly as the LLD specifies.
- **`flowchart.md` unchanged** — it models Step 2 only as file-per-epic/phase plus the
  FE-wireframe branch, and no step ordering or branching changed.

## Decisions made

1. **Each worked example folded under its own rule** rather than into a separate examples
   section (the LLD lists the two as separate structures). Four blocks instead of eight, no
   rule↔example cross-references, less prompt text on every `/lld` run — which is the
   constraint the LLD itself states. Acceptance criteria unchanged.
2. **Claims were measured, not assumed**, using the conformance harness from #47 (mermaid
   11.12.2). Three results changed what shipped:
   - A trailing `%%` comment on the same line as a declaration is a **parse error** — so the
     examples carry no inline comments.
   - The D4 semicolon-in-`Note` claim reproduced as a genuine parse error; the comma form
     parses.
   - In a `classDiagram`, `classDef` + `class X role` renders with **no styling**, while the
     same construct in a `flowchart` styles correctly. The palette example was therefore
     written as a text snippet rather than a diagram, so the skill does not teach a form that
     silently does nothing. Recorded in the LLD as an E1.1/template-level question.
3. **Type-selection signals reduced to short lookup labels.** The first draft copied the gate
   rows near-verbatim, which is the duplication the reference-not-restate constraint exists to
   prevent. Review caught it.
4. **Step 2.5 marked as superseded pending #53.** Step 2 now corrects three claims that item
   still makes, and both are loaded into the same prompt on every `/lld` run. A one-line
   `TODO(#53)` marker resolves the contradiction for the reader without doing #53's work.

## Review feedback addressed

Two blockers and five warnings from the two-agent review. Both blockers were in the **test
module**, not the prose.

| Finding | Resolution |
|---|---|
| **Block** — `NEGATION` guard applied inverted: the D6 assertion passed on "classDef is global" and failed on the correct "classDef is not global" | Fixed with a direct assertion; unused constant removed |
| **Block** — content-signal assertions had no locality, so "gate table" satisfied the `erDiagram` signal | Windowed to ±200 chars around each diagram-type mention; patterns tightened |
| Warn — `re.search(r"/", block)` tautological | Now requires the slash on the same line as the identifier rule |
| Warn — worked-example test would pass with one example beside four headings | Now asserts on the four labelled markers |
| Warn — type-selection signals near-verbatim copies of the gate rows | Reduced to short lookup labels |
| Warn — link-emission example omitted the no-emit *reason* | Reason added |
| Warn — Step 2.5 contradicts Step 2 in the same prompt file | `TODO(#53)` marker added |

All three test fixes were **mutation-tested**: removing the property from `SKILL.md` now fails
the corresponding test.

**Rejected:** the `Co-Authored-By` blocker. The last 20 commits on `main` carry 21 such
trailers and the harness mandates them — repo convention wins over the generic checklist item.

**Deferred, flagged to the human reviewer:** review also noted that Step 2 restates the support
matrix and path form in prose. That text is prescribed verbatim by the LLD's Part B "Rules to
state", and serves a different purpose from the template's table (what to emit vs. support and
failure mode). Changing it would contradict the approved LLD.

## LLD Sync report

```
## LLD Sync — Issue #52: v1-e1-3: Step 2 diagram generation rules with worked examples

### Corrections (spec was wrong)
- Palette rendering is type-dependent: E1.1's D6 guidance ("every diagram carries its own
  classDef") is uniform as advice but not in effect. Measured on mermaid 11.12.2, `classDef` +
  `class X role` inside a `classDiagram` applies no styling; the same construct in a
  `flowchart` styles correctly. → the palette worked example ships as a text snippet.
  Belongs to the template (E1.1); warrants its own issue.
- Invariant 2 is not satisfiable until T2 (#53) lands: its grep is whole-file with no Step 2.5
  carve-out, unlike Invariant 1 which Part B exempts explicitly. → tests bound assertions to
  the Step 2 block; Invariants 1 and 2 should carry matching carve-out wording when T2 closes.
- Part B "Rules to state" ("do not restate the gate conditions") conflicts with the acceptance
  criterion ("name each type's content signal"). → resolved with four short lookup labels plus
  an instruction to read the exact condition from the table.

### Additions (not in spec)
- D5 (emit `click` after the declaration it names) and D6 (`classDef` is fence-local) are in
  the shipped rules but absent from the LLD's four-rule block, which predates #45/#46's syncs.
- A `TODO(#53)` marker on the Step 2.5 navigability item, deferring to Step 2 where the two
  disagree — the PR introduces that contradiction even though the fix is T2's scope.
- `tests/test_lld_skill_step2_generation_rules.py` — 16 tests against the LLD's 12 BDD specs,
  plus D5, D6 and version parity.

### Omissions (in spec but not built)
- The `stateDiagram-v2` no-`_self` form is stated in the rule but not exemplified in a diagram
  — traded away for prompt economy. The LLD required "both forms, on a supporting type", which
  the `classDiagram` example satisfies.

### Confirmations (notable)
- All four Step 2 `edf://` sites migrated; the fifth correctly left to T2.
- The version bump was read from the file rather than hard-coded — and moved twice (0.10.32 →
  0.10.33, then rebased to 0.10.34), which is exactly the failure the LLD's warning predicted.

### LLD updated
File: plugins/edf/docs/design/v1/lld-v1-e1-3-skill-quality-gates.md §3.1 (Part A + Part B)
Version: 0.1 → 0.2
```

## Cost retrospective

**Cost telemetry was unavailable** — Prometheus returned $0.0000 / 0 tokens for every
checkpoint and for the final query, so the figures below are wall-clock from the checkpoint
timestamps, not spend. (Fixing the exporter is worth doing: this is the second signal that
cost data is not being recorded for teammate sessions.)

| Bucket | Wall clock | Share |
|---|---|---|
| 3c → 5 — design reading, test-author, implementation, verification | 8m33s | 42% |
| 5 → 8 — evaluator, diagnostics, commit/push/PR | 2m54s | 14% |
| 8 → 9 — review and review rework | 7m40s | 38% |
| 9 → 10 — reporting | 1m16s | 6% |

**Cost drivers and actions:**

1. **Post-PR rework was 38% of elapsed time, and both blockers were in the test module.** The
   tests were written against the spec before implementation (correct), but their assertions
   were never themselves checked. **Action: mutation-test new assertions at Step 4dF** — flip
   or delete the property and confirm the test fails. Doing that pre-PR would have caught both
   blockers and roughly halved the review bucket. This generalises to any docs/prose task where
   the "unit under test" is text, since text assertions are unusually easy to satisfy vacuously.
2. **An inverted assertion bent the implementation.** I reworded the prose awkwardly to satisfy
   a guard that was asserting the opposite of its docstring, instead of questioning the guard.
   **Action: when a test forces unnatural phrasing, suspect the test first.** The awkwardness
   was itself the signal, and I noticed it at the time without acting on it.
3. **Verification ran green on the first attempt** (3c→5 has no fix cycles). Reading the design
   and the sibling test modules before writing anything is what paid for that.

## Next steps

- **#53 (T2)** is the direct follow-up: Step 2.5 parse-then-navigability checks. It should
  remove the `TODO(#53)` marker, migrate the fifth `edf://`, and align Invariants 1 and 2's
  carve-out wording.
- **New issue worth filing:** the `classDiagram` palette finding — the template's "every
  diagram carries its own `classDef`" guidance applies no styling in `classDiagram` under the
  pinned Mermaid. Belongs with the #60–#62 conformance follow-ups.
- **New issue worth filing:** `test_cross_references::test_feature_core_refers_real_agents`
  fails on `main` (literal `edf:xxx` placeholder in feature-core's prose reads as an agent name).
- **Tooling:** `update-coverage-manifest.py --verify-anchors` reports "file not found" for every
  entry in this repo, including manifests untouched by this PR — it does not resolve this repo's
  nested `plugins/edf/docs/design/` layout. Anchors were verified manually.
- **Tooling:** `run-tests.sh` cannot spawn `pytest` here; `uv run --with pytest pytest` works.
