# Session log — EDF-129

## Approach rationale
- **Issue:** #129
- **Approach chosen:** Recursive renderer in `_adf.py` mirroring the parser: block renderers per node type, inline renderer applying marks in order link/strong/em/code, a single `_escape` for text; unknown nodes fall back to concatenated text.
- **LLD deviations:** none
- **Pressure:** standard — ~90 src lines in 1 source file (1 test file).

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-11-16T21:06:03Z | $0.31 | 2,628 in / 2,521 out | pressure: standard — ~90 src lines, 1 src file [models: claude-sonnet-5-5 $0.31, claude-haiku-5-5 $0.00] |
| 4bF | 2026-11-16T21:09:22Z | $0.78 | 8,200 in / 27,866 out | test-author complete — 14 BDD properties, all covered — brief: used as-is [models: claude-sonnet-5-5 $0.78, claude-haiku-5-5 $0.00] |
| 4dF | 2026-11-16T22:53:38Z | $1.68 | 8,234 in / 54,087 out | implementation complete [models: claude-sonnet-5-5 $1.68, claude-haiku-5-5 $0.00] |
| 5 | 2026-11-16T22:54:35Z | $1.70 | 8,236 in / 54,536 out | green on attempt 1 (python3 -m pytest; uv missing; e2e skip; audit n/a) [models: claude-sonnet-5-5 $1.70, claude-haiku-5-5 $0.00] |
| 6 | 2026-11-16T22:54:35Z | $1.70 | 8,236 in / 54,536 out | diag unavailable (no exporter/ruff); justification ok [models: claude-sonnet-5-5 $1.70, claude-haiku-5-5 $0.00] |
| 6b | 2026-11-16T22:55:59Z | $2.01 | 8,255 in / 60,016 out | evaluator: PASS WITH WARNINGS — brief: used as-is [models: claude-sonnet-5-5 $2.01, claude-haiku-5-5 $0.00] |
| 8 | 2026-11-16T22:56:28Z | $2.06 | 8,259 in / 61,231 out | [PR #139](https://github.com/mironyx/engineering-delivery-framework/pull/139) [models: claude-sonnet-5-5 $2.05, claude-haiku-5-5 $0.00] |
| 9 | 2026-11-16T23:00:48Z | $2.86 | 8,316 in / 75,212 out | review: 2 rounds, warns fixed, trailer 'block' dismissed [models: claude-sonnet-5-5 $2.86, claude-haiku-5-5 $0.00] |
| 10 | 2026-11-16T23:00:54Z | $2.89 | 8,318 in / 76,293 out | report done; ci: none; PR marked ready [models: claude-sonnet-5-5 $2.89, claude-haiku-5-5 $0.00] |

## Concerns & Deferred Items
- Env: `append-checkpoint.py` only globs root `docs/sessions`; worktree has a gitignored `docs/sessions` symlink to `plugins/edf/docs/sessions` so the tracked log is found.
- Test-author spec error: 3 HOSTILE strings with a raw `\n` in one text node (`x\n- y`, `x\n1. y`, `x\n# y`) asserted exact single-node round trip, which `md_to_adf` can never emit (A1 covers docs it produces). Moved to `NEWLINE_TEXT` / `TestNewlineInText` in `tests/test_adf.py` asserting lines kept (hardBreak), no structure gained; headings/cells flatten to a space.
- Nested sub-lists: one listItem holding two sibling sub-lists (from odd indentation) is rendered with earlier sub-lists deeper so they do not merge on re-parse (`_list_lines`).
- Evaluator: PASS WITH WARNINGS. Fixed non-numeric heading level and `None` block child (no raise). Deferred: `_text_of` ignores `attrs` text (emoji, media vanish — per LLD "text content"); non-paragraph children in a listItem are flattened to text.
- Env: `uv`/ruff/diagnostics unavailable; verified with `python3 -m pytest`.
- Review (PR #139): 226-line diff, 2 agents. Dismissed "Co-Authored-By trailer = block" (session attribution rule requires it). Fixed: None/non-dict children, null text, wrong-typed attrs/marks/cells never raise (`_kids`/`_attrs`/`_list_of`, plus warn-and-degrade-to-text backstop in `adf_to_md`); dead `_wrap(plain)` param removed. Fix re-review found 3 more gaps, fixed and tested; final round (~25 lines) self-checked, suite green.
- Deferred to lld-sync: LLD §1.1 names `_render_block/_render_inline` but impl uses `_block/_inline_node` + helpers (`_escape_line`, `_list_lines`, `_table_md`, …); update LLD decomposition.

## Work completed
- [PR #139](https://github.com/mironyx/engineering-delivery-framework/pull/139): `adf_to_md` in `plugins/edf/bin/_adf.py` (escaping, unknown-node-to-text, null handling, never raises).
- Round-trip (A1), fidelity (A6) and code-block (A5) tests in `tests/test_adf.py`.

## Decisions made
- Hostile strings with a raw `\n` in one text node moved to `TestNewlineInText` (see Concerns & Deferred Items).
- Sibling sub-lists in one item render at decreasing indents so they do not merge on re-parse.

## Review feedback addressed
- [correctness] `_adf.py` None/non-dict children, null text, wrong-typed attrs/marks/cells — fixed in 9322d0a (3 fix rounds on PR #139).
- [process] "Co-Authored-By trailer = block" — not a defect (session attribution rule requires it).

## LLD Sync report
## LLD Sync — Issue #129: ADF to Markdown conversion and round-trip tests

### Corrections (spec was wrong)
- §1.1 `adf_to_md` decomposition: spec named `_render_block/_render_inline` → built `_block`, `_inlines`/`_inline_node` plus helpers — naming only.

### Additions (not in spec)
- Never-raise hardening (`_kids`, `_attrs`, `_list_of`, `_level`, warn-and-degrade backstop) and sibling sub-list indent rule — see §1.1 pseudo-code.
- Raw `\n` inside one text node is outside A1 (`md_to_adf` cannot emit it); lines kept via hardBreak, flattened in headings/cells.

### Omissions (in spec but not built)
- None. Deferred: `_text_of` ignores `attrs` text (emoji, media); non-paragraph listItem children flatten to text.

### Confirmations (notable)
- Mapping, A1/A5/A6 invariants and unknown-node-to-text built as specified.

### LLD updated
File: plugins/edf/docs/design/v3/lld-v3-e3-2-jira-backend.md §1.1
Version: 0.3 → 0.4

## Cost retrospective
- PR-creation cost $2.06 (step 8); step 10 checkpoint $2.89, so ~$0.83 post-PR (review rework). `query-feature-cost.py --stage final` reported only $0.3583 (2 sessions) — undercounts; the prom file path it used is `feature-comprehension-score/monitoring/...`, not this repo. The `ai-cost-final` labels are therefore unreliable.
- 4bF→4dF ($0.78→$1.68, 54%): implementation of a ~90-line renderer; action: list odd-input shapes (None children, wrong-typed attrs) in the test-author brief to avoid later hardening rounds.
- 8→9 ($2.06→$2.86): two review rounds found never-raise gaps; same action.

## Next steps
- #132 Jira create is unblocked (#128, #131 merged); #133 needs #132.
- Fix `tag-session.py` prom path resolution so cost is aggregated for this repo.
- LLD-deferred: `_text_of` attrs text, listItem non-paragraph children.
