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
