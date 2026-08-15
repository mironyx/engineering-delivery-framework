# Session log — EDF-46

## Approach rationale

- **Issue:** #46
- **Approach chosen:** Harden the four conditional diagram gates, the palette section and the
  enforcement annotations **in place** inside `plugins/edf/skills/lld/template.md`, rather than
  adding new sections. The template already carries a palette table, a "When required" /
  "When optional" pair per type, and a `Note`-annotated sequence example — this task replaces
  their vague wording with checkable content signals, adds the tie-break and adjacency rules,
  and applies palette classes plus `click` directives to the state-diagram and flowchart
  worked examples using #45's (frozen) link forms.

### Step 3b — LLD challenge (written)

1. **Does the LLD reinvent something the repo already has?** No. Grepped `template.md`: the
   palette table (four roles), the per-type "When required"/"When optional" headings and the
   `Note`-annotated sequence example all exist already. §B.1.2 hardens them; it does not
   introduce a parallel structure. Kept as specified.
2. **Is there a simpler way to get the same behaviour?** Partly. The LLD's "Gate conditions
   to state" table could have been emitted *in addition to* the four in-place prose gates,
   which would state every gate twice and create a second thing to keep in sync. Instead the
   table is emitted **once**, as the gate index in Behavioural Flows, and each type's prose
   gate is hardened to match it — one fewer duplicated statement, one fewer sync surface.
3. **Would you build it this way if the LLD didn't exist?** Yes, with one addition the LLD
   does not call for (see Design deviation D-A below): the template's existing palette prose
   instructed authors to *"define the `classDef` blocks inside the first diagram of each type
   that uses them, then reference by class name in subsequent diagrams"*. That is false —
   each fenced mermaid block is an independent render, so a `classDef` does not carry into a
   later diagram. Measured, not reasoned: see the render harness note below. Since this task
   owns the palette section and is applying palette classes to two further examples, the
   instruction had to be corrected or the two new examples would have been written against a
   rule that produces unstyled diagrams.

### Design deviations

- **D-A — palette carry-over instruction corrected.** The LLD does not mention it. The
  pre-existing "define once, reference in subsequent diagrams" instruction is wrong; every
  diagram using palette classes must carry its own `classDef` lines. Corrected in the palette
  section and honoured by every worked example.

### Verification approach

Per the epic's premise, **parse success is not evidence of correctness** (decisions D4 and
D5). Every mermaid block in `template.md` is checked with a throwaway `mermaid@11.12.2` +
`jsdom` harness that both `mermaid.parse`s the block and `mermaid.render`s it under
`securityLevel: 'strict'`, then counts the `<a href>` elements in the produced SVG and
asserts the count equals the number of `click` directives declared. The committed version of
this harness is T3's deliverable (issue #47) — this task uses a scratch copy so it is not
shipping T3's files early.

- **Pressure:** Standard — ~145 changed lines across 3 source files
  (`template.md`, `plugin.json`, `marketplace.json`); 1 test file.

## Cost checkpoints

| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-08-15T12:05:53Z | $0.00 | 0 in / 0 out | pressure: Standard — ~145 lines across 3 source files (template.md + 2 manifests), 1 test file |
| 4bF | 2026-08-15T12:13:35Z | $0.00 | 0 in / 0 out | test-author complete — 21 BDD properties, all covered, no blocking gaps |
| 4dF | 2026-08-15T12:17:19Z | $0.00 | 0 in / 0 out | implementation complete — 21/21 new tests pass; all 5 mermaid blocks render with anchors == clicks |
| 5 | 2026-08-15T12:19:14Z | $0.00 | 0 in / 0 out | green on attempt 1 — 357 passed; 1 pre-existing unrelated failure (test_cross_references edf:xxx placeholder, fails on main at 24f491b); ruff/pytest runners absent in sandbox, used venv pytest directly |
| 6 | 2026-08-15T12:19:20Z | $0.00 | 0 in / 0 out | diag pass — docs/JSON change only; no CodeScene/Sonar surface. py_compile + JSON parse clean; markdown-lint deltas are MD013/MD060 cosmetic on a file already at 182 errors, and markdownlint is not wired into CI (no .github/workflows) |
| 6b | 2026-08-15T12:26:17Z | $0.00 | 0 in / 0 out | evaluator: PASS WITH WARNINGS — all 11 ACs covered; 4 adversarial tests added (clause-scoping gap: original gate tests would pass with When required/When optional content swapped); no blockers |
| 8 | 2026-08-15T12:27:34Z | $0.00 | 0 in / 0 out | [PR #58](https://github.com/mironyx/engineering-delivery-framework/pull/58) |
| 9 | 2026-08-15T12:34:36Z | $0.00 | 0 in / 0 out | review clean — 0 blockers; 1 warn (D-B normative scope) resolved via LLD OQ3 in 12640ff; 1 dismissed false positive (Co-Authored-By, matches repo precedent); agent B re-verified all 10 mermaid claims by measurement |
| 10 | 2026-08-15T12:39:19Z | $0.00 | 0 in / 0 out | report done — PR #58 open, 0 blockers, 1 warn resolved; no CI checks reported (repo has no workflows); awaiting human review |

## Work completed

**PR:** [#58](https://github.com/mironyx/engineering-delivery-framework/pull/58) — 3 commits, squash-merged to `main`.

Implemented T2 of epic [#28](https://github.com/mironyx/engineering-delivery-framework/issues/28), the definition half of Stories 1.1–1.3.

| File | Change |
|---|---|
| `plugins/edf/skills/lld/template.md` | Gate index table + hardened per-type gates; canonical palette table with total tie-break; `text`-fenced `classDef` demo; palette classes + `click` on the state and flowchart examples; four enforcement `Note` types with format, adjacency and no-semicolon rules |
| `plugins/edf/docs/design/v1/lld-v1-e1-1-template-vocabulary.md` | D6 recorded; OQ3 raised and resolved; invariants 22–23; implementation notes; 0.2 → 0.3 |
| `plugins/edf/docs/design/v1/coverage-v1-e1-1.yaml` | Stories 1.1–1.3 → `Revised`, files populated |
| `plugins/edf/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | 0.10.31 → 0.10.32, in sync |
| `tests/test_lld_template_gates_palette_annotations.py` | 21 tests (test-author) |
| `tests/evaluation/test_gates_palette_annotations_eval.py` | 4 adversarial tests (evaluator) |

**Tests:** 25 added, suite 361 passing.

## Decisions made

- **Gates emitted once, not twice.** The LLD's gate table could have shipped alongside the
  existing per-type prose, stating every gate in two places. Shipped as a single index table
  with the per-type prose hardened to match — one fewer sync surface.
- **D-A / D6 — palette carry-over instruction was wrong.** The template told authors to define
  `classDef` once and reference it in later diagrams. Measurement: a `class X role` without a
  local `classDef` parses, renders, and emits no CSS rule — silently unstyled. Corrected, and
  recorded in the LLD as D6 beside D1–D5.
- **D-B / OQ3 — tie-break made total.** The approved rule ordered `{new, external}` above
  `{error, auth}` but never ordered `new` vs `external`, leaving "exactly one class" undecidable
  for the case that motivates it. Adopted `external` > `new` > `auth` > `error`. PR review
  correctly flagged that this was *new normative content* landed via a PR note; re-routed
  through the LLD's own open-question mechanism as OQ3 and signed off by the human on the PR.
- **Verified by rendering, not parsing.** Built a throwaway `mermaid@11.12.2` + `jsdom` harness
  that renders each block and asserts rendered `<a href>` count == declared `click` count.
  D3, D4 and D5 were each reproduced before being relied on, and D6 was found this way.

## Review feedback addressed

- **[warn] D-B normative scope** — resolved in `12640ff` by recording OQ3 in the LLD and
  correcting the PR body's understated framing. Signed off at review; no code change needed.
- **[block] `Co-Authored-By` trailer** — dismissed as a false positive from the review skill's
  generic checklist. `CLAUDE.md` is silent on it, 9 of the last 10 non-merge commits on `main`
  carry it, and the session's harness config mandates it.
- **Deferred, with follow-ups recommended:**
  - `tests/test_cross_references.py::test_feature_core_refers_real_agents` fails on `origin/main`
    too — `feature-core/SKILL.md` carries the prose placeholder `edf:xxx` and the test's regex
    cannot distinguish it from a real reference. Different skill, out of scope here.
  - `bin/update-coverage-manifest.py --verify-anchors` hardcodes `pathlib.Path("docs/design")`,
    but this repo's docs live under `plugins/edf/docs/design/`. Every anchor reports
    "file not found"; it exits 0 so nothing is gated. Anchors verified by hand instead.

## LLD Sync report

## LLD Sync — Issue #46: diagram type gates, palette application and enforcement annotations

### Corrections (spec was wrong)
- **Palette carry-over:** `template.md` (endorsed implicitly by §1.2 "Palette block placement")
  said `classDef` is defined in the first diagram of each type and referenced by class name in
  later diagrams → each fenced block renders independently, so nothing carries; every diagram
  repeats the `classDef` lines it uses. Measured, not reasoned. Recorded as **D6**.
- **Tie-break partiality:** §1.2 stated `new`/`external` outrank `error`/`auth` and stopped
  there → made total as `external` > `new` > `auth` > `error`, because the rule as written could
  not decide the case it exists for. Recorded as **OQ3**, resolved at PR review.

### Additions (not in spec)
- Invariant 22 (every example using a palette `class` declares the matching `classDef`) and
  Invariant 23 (the tie-break is total).
- Note for T3: the harness should assert emitted `classDef` CSS rules, by the same argument that
  added `checkAnchorsRendered` for D5 — parse checks cannot see D6 either.

### Omissions (in spec but not built)
- None. All 11 acceptance criteria shipped.

### Confirmations (notable)
- D4 (`;` in a `Note` is a parse error) and D5 (a `click` before its declaration renders zero
  anchors) were both independently re-measured during T2 and confirmed. Worth recording: this
  epic exists because such claims were previously asserted from recall.
- The `text`-fence requirement was confirmed empirically — a bare `classDef` block in a
  `mermaid` fence fails with "No diagram type detected".

### LLD updated
File: `plugins/edf/docs/design/v1/lld-v1-e1-1-template-vocabulary.md` §B.1.2
Version: 0.2 → 0.3

## Cost retrospective

**Cost telemetry unavailable** — Prometheus returned `$0.0000` / 0 tokens for every checkpoint
and for the final query, so no cost analysis is possible for this feature. The checkpoint
*timestamps* are intact, so the analysis below uses wall-clock as a proxy. Fixing the
Prometheus scrape is worth doing before the next epic, or these retrospectives stay blind.

| Bucket | Wall clock | Note |
|---|---|---|
| 3c → 4bF | 7m42s | test-author sub-agent |
| 4bF → 4dF | 3m44s | implementation |
| 4dF → 5 | 1m55s | full verification, **green on first attempt** |
| 6 → 6b | 6m57s | evaluator sub-agent |
| 6b → 8 | 1m17s | commit + PR |
| 8 → 9 | 7m02s | review — 3 agents in parallel, plus the OQ3 fix |

**Time to PR: 22 min.**

**Driver:** the three sub-agent spawns (test-author, evaluator, review) accounted for ~22 of
~28 minutes; actual implementation was under 4 minutes. That is the expected shape for a docs
task with a small edit surface and a large correctness surface.

**What paid for itself:** building the render harness *before* writing anything. It cost a few
minutes up front and caught D6 pre-implementation — had the two new worked examples been
written against the old carry-over instruction, they would have shipped silently unstyled and
the epic would have repeated the exact defect it exists to remove.

**Improvement actions:**
1. **Fix the Prometheus scrape** before the next feature — six checkpoint rows of `$0.00` make
   the cost-tracking machinery pure overhead.
2. **Zero fix cycles (green first attempt)** — the test-author's spec-only tests plus the
   pre-built harness meant implementation had an executable target. Keep this ordering.
3. **Scope gate tests to the clause, not the section.** The evaluator found the original gate
   tests would pass with the "When required" / "When optional" content swapped. Worth adding to
   the test-author's contract-properties checklist: when a spec defines a positive/negative
   pair, assert against each side, not the region containing both.

## Next steps

- **Blocked on this epic:** T3 (#47) — conformance fixture, harness and report. It should
  productionise the scratch harness used here and add a `classDef` CSS-rule assertion for D6.
- **E1.3** delivers the application half of Stories 1.1–1.3; manifest entries stay `Revised`
  until it merges.
- **Follow-up issues recommended:** the `edf:xxx` cross-reference test failure on `main`, and
  the `update-coverage-manifest.py --verify-anchors` hardcoded `docs/design` path.
