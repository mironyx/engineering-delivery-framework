# Session log — EDF-45

## Approach rationale

- **Issue:** #45
- **Approach chosen:** Consolidate the template's link rules into a single normative
  "Diagram navigability convention" block (path form, `design-root`, support matrix,
  `link`-directive convention, `#LLD-` anchor form, `classDiagram` display-label
  workaround), and have the per-diagram-type prose reference it rather than restate it.
  All 10 `edf://` sites migrate to document-relative example paths. ADR-0039 gains an
  append-only dated revision; Story 1.4 AC7 and the glossary entry are amended to the
  adopted form; the plan's "three parse-error cases" becomes two.
- **LLD deviations:** see PR body — glossary entry amended alongside AC7 (it carries the
  same superseded constraint), and the wireframe's example anchor id corrected to include
  the epic id.
- **Pressure:** Standard — Docs-layer change with 13 named BDD properties; rounded up from
  Light so the test-author and evaluator passes run against the stated properties.

## Cost checkpoints

| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-08-14T20:33:43Z | $0.00 | 0 in / 0 out | pressure: Standard — docs-layer, 13 BDD properties, rounded up from Light |
| 4bF | 2026-08-14T20:44:37Z | $0.00 | 0 in / 0 out | test-author complete — 14 properties, all covered; discrimination verified against HEAD (13/14 fail pre-implementation) |
| 4dF | 2026-08-14T20:44:38Z | $0.00 | 0 in / 0 out | implementation complete |
| 5 | 2026-08-14T20:44:38Z | $0.00 | 0 in / 0 out | green on attempt 1 — 348 tests, 1 pre-existing failure (test_cross_references edf:xxx placeholder) reproducing on main; run-tests.sh needs 'uv run --with pytest' as no pyproject.toml exists |
| 6 | 2026-08-14T20:45:13Z | $0.00 | 0 in / 0 out | diag pass — ruff check + format clean on the new test file; docs-only change otherwise. run-lint.sh could not spawn ruff (no project env), so ruff was run via uvx |
| 6b | 2026-08-14T20:47:40Z | $0.00 | 0 in / 0 out | evaluator: PASS — 11/11 ACs covered, 0 adversarial tests written, ADR Decision section verified unedited vs origin/main |
| 8 | 2026-08-14T20:48:52Z | $0.00 | 0 in / 0 out | [PR #57](https://github.com/mironyx/engineering-delivery-framework/pull/57) |
| 9 | 2026-08-14T20:57:53Z | $0.00 | 0 in / 0 out | review: 3 blockers + 3 warnings, all fixed — classDiagram click-ordering silent anchor loss (new ADR R4), direction-blind test assertions, stale HLD C2.1/C2.3; SKILL.md gap confirmed out of scope |
| 9 | 2026-08-14T21:00:31Z | $0.00 | 0 in / 0 out | re-verified: reordered classDiagram example renders 3 anchors (control: 0); ordering rule scoped to classDiagram+flowchart, stateDiagram-v2 order-insensitive |
| 10 | 2026-08-14T21:00:56Z | $0.00 | 0 in / 0 out | report done — review clean, no GitHub Actions CI configured in this repo; external Comprehension Check status not reported on the branch |

## Work completed

**PR:** [#57](https://github.com/mironyx/engineering-delivery-framework/pull/57) — open, awaiting
human review at the time of writing (see `## Next steps`).

- `plugins/edf/skills/lld/template.md` — all 10 `edf://` occurrences migrated to
  document-relative paths. The scattered per-diagram-type link prose was replaced by one
  normative "Diagram navigability convention" block: two link forms, path form, `design-root`,
  a five-row support matrix, the `link`-directive convention, the declaration-order rule, the
  `classDiagram` identifier constraint, and the `#LLD-` anchor form.
- `plugins/edf/docs/adr/0039-…md` — append-only `## Revision — 2026-08-14` with R1 (path form),
  R2 (`link` is not a parse error), R3 (rest of matrix confirmed), R4 (declaration order). The
  original Decision section is byte-identical to `origin/main`, verified by two agents.
- `plugins/edf/docs/requirements/v1-requirements.md` — Story 1.4 AC7 amended, plus the glossary
  entry carrying the same rule, a new `design-root` glossary entry, and AC1's example. v1.2 → v1.3.
- `plugins/edf/docs/design/v1/v1-design.md` — §C2.1 and §C2.3 amended. v1.1 → v1.2.
- `plugins/edf/docs/plans/2026-08-13-v1-implementation-plan.md` — "three parse-error cases" → two.
- `plugins/edf/docs/design/v1/vis-markdown-preview-navigation.html` + `-anchor.png` — example
  anchor id corrected to carry the epic id; anchor-state screenshot captured and embedded.
- Version `0.10.30` → `0.10.31` in `plugin.json` and `marketplace.json`, in sync.
- `tests/test_lld_template_link_forms.py` — 16 tests (14 BDD properties + Invariant 6 + two for
  the D5 ordering rule).

## Decisions made

- **The matrix is stated in both ADR-0039 and `template.md`.** Accepted duplication: the ADR is a
  decision record, the template is the authoring reference. The revision names `template.md` as
  operative to bound the drift.
- **`template.md` gives no relative link to ADR-0039**, only its title. The template is
  instantiated in projects that have no copy of the ADR, so a relative link would be dead in
  every one of them — the exact failure this epic removes.
- **The `classDiagram` `/`-identifier rule sits outside the support matrix.** It is an identifier
  constraint, not a `click`-support case; folding it in would make "exactly two parse-error rows"
  read as three.
- **The ADR header was touched** (`Accepted — revised …`) though the append-only constraint covers
  the Decision section's text, which is unchanged. A reader stopping at the header would otherwise
  take the superseded form as current.
- **Term `workspace-relative path` deliberately not renamed.** ~30 references across requirements,
  HLD and plan; the glossary entry now says "workspace" names the containment boundary, never the
  resolution base. A rename is a reasonable follow-up.
- **Scope was widened twice, both deliberately and both flagged for sign-off in the PR body:** the
  HLD (§C2.3 specified a check that would reject every valid link) and the wireframe (the
  screenshot deliverable is taken from it, so shipping it unchanged would have embedded a picture
  of the rule being broken).

## Review feedback addressed

Three agents ran: quality, design conformance, and an external-surface agent that re-measured
every Mermaid claim against `mermaid@11.12.2` in a throwaway jsdom harness. Six findings, all
fixed before hand-off.

1. **(blocker) `classDiagram` `click` before the `class` declarations yields zero anchors.** Both
   orderings parse, so a parse-only check cannot see it. The template's worked example — copied
   into every generated LLD — had them first; masked by the `edf://` hrefs the sanitiser was
   stripping anyway. Fixed, stated normatively, recorded as ADR-0039 **R4** and LLD **D5**, pinned
   by two tests. Re-measured after the fix: 3 anchors, control 0. Generalisation check narrowed the
   scope — holds for `flowchart` (2 vs 0), not for `stateDiagram-v2` (order-insensitive).
2. **(blocker) The test for the PR's central rule passed against a template stating the opposite.**
   Mutation-verified by the reviewer: `not permitted` contains `permitted`. Three assertions were
   direction-blind, one near-tautological. All now negation-guarded and section-scoped, and
   re-verified by mutation.
3. **(blocker) The HLD still mandated the superseded path form**, including a §C2.3 check that
   would have rejected every valid link. Fixed.
4. **(warn) Support-matrix tests scanned prose, not table rows**, contradicting their own
   docstring. Scoped to `|` lines.
5. **(warn) ADR R3 contradicted R2.** R3 now says the matrix stands unamended.
6. **(warn) `SKILL.md` still contains 5 `edf://` references.** Confirmed correctly out of scope —
   Epic E1.3 / Story 3.1, serialised apart because both chains bump `plugin.json`.

Every other Mermaid claim was empirically confirmed. One docs ambiguity settled: mermaid's "click
functionality is disabled at `securityLevel: strict`" refers to JS **callbacks**, not `href` links.

## LLD Sync report

```
## LLD Sync — Issue #45: v1-e1-1: ADR-0039 link forms and support matrix in LLD template

### Corrections (spec was wrong)
- Part B "The 10 `edf://` sites to migrate": prescribed `src/lib/example/service.ts` and
  `src/lib/…` as the replacement forms for lines 70 and 206-208 — repo-root paths, the exact
  form D1 (three sections above) measured as non-resolving. Built as `../../../src/lib/…`.
  The table contradicted its own document.
- D1 "Consequences outside this LLD": listed epics #28/#31 and the plan, but omitted
  `v1-design.md`, which carried the superseded path form in §C2.1 and — worse — specified the
  §C2.3 self-critique check as "no leading slash or `..` segment", which implemented as written
  would reject every valid link. Both amended by T1 (HLD 1.1 → 1.2).
- Part B "ADR-0039 revision": specified `## Revision — 2026-08-13`. Shipped as 2026-08-14, the
  day it was written and OQ1 was decided; the measurement date is stated inside the section.
- File-structure list: omitted `v1-design.md` and the wireframe HTML, both of which T1 had to
  edit. The requirements entry also understated scope (the glossary entry and AC1's example
  carried the same superseded rule as AC7).

### Additions (not in spec)
- **D5 — a `click` before its node declaration is silently dropped.** Found during T1 by
  rendering rather than parsing. classDiagram 3 anchors vs 0; flowchart 2 vs 0;
  stateDiagram-v2 order-insensitive. Both orderings parse in every case. Recorded as ADR-0039
  §Revision R4 and stated normatively in `template.md`.
- §B.1.3 harness gains `checkAnchorsRendered` — the original four checks were parse- or
  text-based and are all blind to D5. Parse success is not evidence of navigability.
- Invariant 20 (click ordering in template examples) and Invariant 21 (no document states the
  superseded path form as a live rule outside a dated history note).
- Wireframe `vis-markdown-preview-navigation.html`: example anchor id corrected from
  `LLD-delivery-service` to `LLD-v1-e1-delivery-service`. The screenshot deliverable is captured
  from this file, so shipping it unchanged would have embedded a picture of the anchor rule
  being broken.

### Omissions (in spec but not built)
- None. All 11 acceptance criteria were implemented.
- Out of scope by design and confirmed correct: `plugins/edf/skills/lld/SKILL.md` still contains
  5 `edf://` references — owned by Story 3.1 / Epic E1.3, serialised apart because both chains
  bump `plugin.json`.

### Confirmations (notable)
- D1, D2 and D3 were encoded in `template.md` exactly as specified; the two-parse-error count,
  the `link`-as-convention framing and the `erDiagram` no-op all survived independent
  re-measurement against `mermaid@11.12.2`.
- D3's matrix was re-verified a third time by the review's surface agent — including the claim
  that relative paths and `#fragment` hrefs survive the strict sanitiser while `edf://`,
  `vscode:`, `file:` and `javascript:` are stripped.
- The `classDiagram` display-label workaround parses with a body block attached, which is how
  the template's example uses it.

### LLD updated
File: plugins/edf/docs/design/v1/lld-v1-e1-1-template-vocabulary.md — Decisions (D5 added),
      §1.1 Invariants (20, 21), §B.1.1 (migration table, file structure, revision date),
      §B.1.3 (checkAnchorsRendered)
Version: 0.1 -> 0.2 (Status: Draft -> Revised)
Manifest: plugins/edf/docs/design/v1/coverage-v1-e1-1.yaml — both issue-45 entries
      Approved -> Revised, files populated
kb/: no changes — this repo has no kb/ directory (CLAUDE.md references one that does not exist)
```

## Cost retrospective

**Cost telemetry unavailable** — `query-feature-cost.py` reported "No session data found for
EDF-45" and every checkpoint row recorded `$0.00 / 0 tokens`, despite `tag-session.py` reporting
success and writing the prom file. Prometheus is not scraping this repo's textfile collector, so
the checkpoint table has no cost signal. **This is itself the top finding: the cost-tracking
mechanism silently produced zeros rather than failing loudly**, which is the same defect class
this epic exists to remove. Worth an issue.

Falling back to checkpoint elapsed times, which are real:

| Bucket | Elapsed | What happened |
|--------|---------|---------------|
| 3c → 5 | ~11 min | Design reading, test-author (background), implementation. Overlapped — the docs were written while test-author ran. |
| 5 → 8 | ~4 min | Diagnostics, evaluator (PASS, 0 adversarial tests), commit, PR. |
| 8 → 9 | ~12 min | **Review and review fixes — the largest bucket.** |

**Improvement actions:**

1. **Review was the most expensive phase and returned the highest value** — it found a real
   silent-failure bug that all prior gates missed. The evaluator passed 11/11 ACs and the full
   suite was green, yet the shipped example generated zero working links. *Action: for any change
   whose deliverable is a claim about external tool behaviour, budget for an agent that measures
   rather than reads. Parse/lint/test green is not evidence about the tool.*
2. **Test-author ran concurrently with implementation and finished after it**, so its tests saw the
   implemented file — which is how three direction-blind assertions survived. Discrimination had to
   be recovered afterwards by mutation. *Action: on Standard track, either block on test-author
   before writing the deliverable, or require a mutation check as part of its own report.*
3. **The LLD's own worked example contradicted its decision** (the 10-sites table prescribed
   repo-root paths three sections below D1 saying those fail). *Action: `/lld` self-critique should
   diff prescribed examples against the decisions in the same document.*
4. **Repo tooling is unusable**: `run-tests.sh`/`run-lint.sh` cannot spawn `pytest`/`ruff` (no
   `pyproject.toml`), and `update-coverage-manifest.py --verify-anchors` reports every anchor
   broken because it resolves `lld:` against `docs/design/` while this repo uses
   `plugins/edf/docs/design/`. Both reproduce on `origin/main`. *Action: file both.*

## Next steps

**This feature was NOT merged.** `edf:feature-end` was run through lld-sync, session log, manifest
and push, but stopped before the merge step. The PR contains two post-gate amendments to approved
documents — Story 1.4 AC7 (post-Gate-2) and the HLD §C2.1/§C2.3 (post-Gate-1) — that the PR body
explicitly flags as needing human sign-off, and no GitHub review has been submitted
(`reviewDecision` is empty). Merging on a relayed approval would have cancelled the sign-off this
PR was designed to obtain. Merge is a one-command follow-up once a human has reviewed.

Follow-up issues worth filing:

1. `plugins/edf/skills/lld/SKILL.md` still emits `edf://` — owned by Story 3.1 / Epic E1.3. Until
   it lands, the skill instructs the generator to emit a scheme `template.md` forbids.
2. Cost tracking silently records `$0.00` — Prometheus not scraping; the pipeline should fail
   loudly rather than write zeros.
3. `run-tests.sh` / `run-lint.sh` cannot spawn `pytest` / `ruff` — no `pyproject.toml` in the repo.
4. `update-coverage-manifest.py --verify-anchors` mis-resolves LLD paths for this repo's layout.
5. `tests/test_cross_references.py::test_feature_core_refers_real_agents` fails on `main` on the
   literal `edf:xxx` placeholder in the feature-core skill.
6. Consider renaming the term "workspace-relative path" to "document-relative path" across the
   requirements, HLD and plan (~30 references).

Next board item: **T2 (issue #46)** — diagram gates, palette and enforcement annotations. It shares
`template.md` with T1 and must obey D5's ordering rule when adding `click` directives to the state
and flowchart examples. It is blocked until #45 merges.
