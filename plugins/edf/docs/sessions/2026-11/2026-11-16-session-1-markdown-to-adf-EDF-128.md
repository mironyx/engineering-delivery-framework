# Session log — EDF-128

## Approach rationale
- **Issue:** #128
- **Approach chosen:** Hand-written line-based block parser plus a single-pass inline tokeniser with GFM flanking rules, in a pure stdlib `_adf.py`; keep the LLD shape.
- **LLD deviations:** none
- **Pressure:** heavy — ~250 src lines in 1 source file (1 test file); table decides, not file count.

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-11-16T20:21:08Z | $0.32 | 2,476 in / 1,679 out | pressure: heavy — ~250 src lines, 1 src file [models: claude-sonnet-5-5 $0.32, claude-haiku-5-5 $0.00] |
| 4bF | 2026-11-16T20:22:53Z | $0.63 | 3,642 in / 16,500 out | test-author complete — 19 BDD properties, all covered — brief: used as-is [models: claude-sonnet-5-5 $0.63, claude-haiku-5-5 $0.00] |
| 5 | 2026-11-16T20:26:23Z | $1.09 | 3,656 in / 41,058 out | green on attempt 1 (python -m pytest; uv missing; e2e skip; audit n/a) [models: claude-sonnet-5-5 $1.09, claude-haiku-5-5 $0.00] |
| 6 | 2026-11-16T20:26:27Z | $1.09 | 3,656 in / 41,058 out | diag unavailable (no exporter); justification ok [models: claude-sonnet-5-5 $1.09, claude-haiku-5-5 $0.00] |
| 6b | 2026-11-16T20:26:51Z | $1.30 | 3,667 in / 44,535 out | evaluator: PASS — brief: used as-is [models: claude-sonnet-5-5 $1.30, claude-haiku-5-5 $0.00] |
| 8 | 2026-11-16T20:27:13Z | $1.33 | 3,671 in / 45,294 out | [PR #137](https://github.com/mironyx/engineering-delivery-framework/pull/137) [models: claude-sonnet-5-5 $1.32, claude-haiku-5-5 $0.00] |
| 9 | 2026-11-16T20:30:00Z | $2.25 | 18,064 in / 71,309 out | review: 1 block + 1 warn fixed (warn on fallback, unsafe href); self-checked [models: claude-sonnet-5-5 $2.24, claude-haiku-5-5 $0.00] |
| 10 | 2026-11-16T20:30:05Z | $2.25 | 18,064 in / 71,309 out | report done; ci: none; PR marked ready [models: claude-sonnet-5-5 $2.24, claude-haiku-5-5 $0.00] |

## Concerns & Deferred Items
- LLD §External Surfaces ADF rows are pinned and verified 2026-11-16; Step 3a research sub-agent skipped, relied on the LLD table.
- Env: `uv` missing and no diagnostics-exporter/pyright/ruff here; verified with `python -m pytest` directly; `edf:diag` unavailable (no `.diagnostics/`).
- Evaluator silent risk: `_adf.py` `md_to_adf` catch-all `except Exception` falls back to literal paragraphs silently (intentional, A4); fallback path untested.
- Review fixes: catch-all fallback now `warnings.warn`s and is tested; `javascript:`/`data:`/`vbscript:` link hrefs stay literal text (_adf.py `_match_link`). Fix ~10 src lines — self-checked, skipped re-review.
- Deferred: only scripting schemes are blocked, not a full href allow-list (Jira sanitises on render).

## Work completed
- [PR #137](https://github.com/mironyx/engineering-delivery-framework/pull/137): `md_to_adf`, `ALLOWED_NODES`, `ALLOWED_MARKS` in `plugins/edf/bin/_adf.py` (pure stdlib).
- `tests/test_adf.py`: 145 tests (mapping, flanking, allow-lists, purity, 40 malformed inputs, fallback, unsafe links). Full suite 1136 passed.

## Decisions made
- Line-based block parser plus CommonMark delimiter-stack inline parser; LLD shape kept, no deviations.
- Review fixes beyond the LLD: fallback warns (`RuntimeWarning`); `javascript:`/`data:`/`vbscript:` links stay text. Both recorded in LLD §1.1.

## Review feedback addressed
- [silent-swallow] `_adf.py:57` — fixed in 955b92c (warns, tested).
- [anti-pattern] `_adf.py:370` unsafe link schemes — fixed in 955b92c (scripting schemes literal; full allow-list deferred).
- [unspecified-function] helpers lacking justification — not a defect (`check-justification.py` reports ok).

## LLD Sync report
## LLD Sync — Issue #128: Markdown to ADF conversion

### Corrections (spec was wrong)
- None. The public contract (`md_to_adf`, `ALLOWED_NODES`, `ALLOWED_MARKS`) matched the spec.

### Additions (not in spec)
- Block dispatch order and paragraph-interrupt rules, table width = widest row, empty list item/heading handling (§1.1 Implementation).
- Links with `javascript:`/`data:`/`vbscript:` targets stay literal text; a parser failure warns with `RuntimeWarning` and returns literal paragraphs (review findings).

### Omissions (in spec but not built)
- `adf_to_md` and round-trip tests: Task 2 (#129 scope), not this issue.

### Confirmations (notable)
- Emphasis follows GFM flanking; `snake_case_name`, `2 * 3 * 4`, `a_b *c* d_e` stay plain as specified.

### LLD updated
File: plugins/edf/docs/design/v3/lld-v3-e3-2-jira-backend.md §1.1 Implementation
Version: 0.1 → 0.2

## Cost retrospective
| Bucket | Cost |
|--------|------|
| 3c → 5 (test-author, implementation) | $0.77 |
| 5 → 8 (diag, evaluator, PR) | $0.24 |
| 8 → 9 (review + fixes) | $0.92 |
Final $2.52. Drivers: (1) review = 3 agents on a 460-line diff ≈ 40% of cost; (2) test-author wrote 139 tests in one pass, no fix cycles (green on attempt 1).

## Next steps
- Task 2 (ADF → Markdown and round-trip) is unblocked; Task 3 (`fake_jira`) can run in parallel.
- Process: `/docs/` is gitignored here and `park-docs.sh` only parks top-level `docs/`/`kb/`; this repo's tracked docs live under `plugins/edf/docs/`. Consider making feature-core and park-docs path-aware.
