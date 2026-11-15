# Session log — EDF-119

## Approach rationale
- **Issue:** #119
- **Approach chosen:** Follow LLD §1.2 Part B: record goldens from the pre-port scripts first (`record_tracker_golden.py` extracts them from git at `0f8ad5f`), port create/status into `_tracker_github.py` (argv-only `_gh` with explicit stdin), board helpers in-process, bash scripts become shims. Alternatives rejected: keeping bash and wrapping it from Python (keeps two implementations), or argparse for create (breaks parity).
- **LLD deviations:** (1) two goldens carry `port_stdout/port_stderr` overrides because the bash scripts exit 1 silently under `set -euo pipefail` (URL without number; not on board) — the port prints the LLD's message; (2) `status` reads the GraphQL result itself (`_issue_query`) so gh's not-found stderr passes through; `_fetch_issue` wraps it for `create --parent`; (3) `create --parent` on a dedup hit also adds `## Parent epic` to the existing issue's body (AC says "new (or existing)"); (4) empty `--title ""`/`--body ""` now fail like bash (`-z` checks).
- **Pressure:** heavy — ~280 src lines across 4 source files (`_tracker_github.py`, two shims, `tracker.py` empty-value fix); test files: `test_tracker_github.py`, `test_tracker.py` (stub-observation updates), recorder + goldens.

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-11-15T21:16:21Z | $1.42 | 2,968 in / 18,198 out | pressure: heavy — ~280 src lines, 4 src files [models: claude-opus-5-5 $1.42, claude-haiku-5-5 $0.00] |
| 4bF | 2026-11-15T21:22:19Z | $3.38 | 14,355 in / 67,135 out | test-author complete — 19 properties, 130 tests, all covered; fake_gh gained argv_contains — brief: used as-is [models: claude-opus-5-5 $3.38, claude-haiku-5-5 $0.00] |
| 4dF | 2026-11-15T21:24:22Z | $3.82 | 14,371 in / 73,613 out | implementation complete — 130/130 new tests, test_tracker + test_shell_scripts green [models: claude-opus-5-5 $3.82, claude-haiku-5-5 $0.00] |
| 5 | 2026-11-15T21:25:48Z | $4.15 | 14,385 in / 76,830 out | green on attempt 1 — pytest direct (882 passed, 18 skipped), no uv; e2e skip (no e2e-dir); audit n/a (no dependency files) [models: claude-opus-5-5 $4.15, claude-haiku-5-5 $0.00] |
| 6 | 2026-11-15T21:25:48Z | $4.15 | 14,385 in / 76,830 out | diag: exporter missing (worktree), CodeScene MCP unavailable, sonar skipped (no local analyze tool); shellcheck clean on shims; justification ok (5 added); mock grep clean [models: claude-opus-5-5 $4.15, claude-haiku-5-5 $0.00] |
| 6b | 2026-11-15T21:28:06Z | $4.89 | 17,046 in / 84,403 out | evaluator: PASS WITH WARNINGS — 0 adversarial; 2 silent risks fixed (+7 tests) — brief: used as-is [models: claude-opus-5-5 $4.89, claude-haiku-5-5 $0.00] |
| 8 | 2026-11-15T21:29:16Z | $5.06 | 17,052 in / 86,337 out | [PR #125](https://github.com/mironyx/engineering-delivery-framework/pull/125) [models: claude-opus-5-5 $5.06, claude-haiku-5-5 $0.00] |
| 9 | 2026-11-15T21:35:57Z | $9.24 | 81,100 in / 136,843 out | review: r1 4 block (3 swallow: 2 fixed, 1 accepted for golden; trailer kept per lead) + 13 warn (2 fixed, 11 to lld-sync); r2 A clean, C 2 warn fixed [models: claude-opus-5-5 $9.21, claude-haiku-5-5 $0.03] |
| 10 | 2026-11-15T21:36:14Z | $9.40 | 81,104 in / 138,852 out | report done — ci: none (no workflows); PR marked ready; review clean after 2 rounds [models: claude-opus-5-5 $9.37, claude-haiku-5-5 $0.03] |

## Concerns & Deferred Items
- Golden recording found two dead error paths in the pre-port bash: `gh-create-issue.sh` URL-without-number and `gh-project-status.sh` not-on-board both exit 1 with no output (`set -e` + `pipefail` on the command substitution). Decided: the port prints the messages; goldens record both bash bytes and `port_*` expectations (`tests/fixtures/record_tracker_golden.py` INTENTIONAL_CHANGES). LLD Open question 4 to list them at lld-sync.
- `tests/test_tracker.py`: 6 #118 grammar tests used `Error: not implemented` as the "reached the backend" signal for create/status. Now that both are real, they observe the gh calls or the backend's config error instead; the grammar asserted is unchanged. Added `test_create_empty_value_counts_as_missing` (tracker.py accepted `--title ""`, bash rejected it).
- The test-author extended the shared `tests/fixtures/fake_gh.py` with an optional `argv_contains` rule key, so lookups for different issue numbers can be told apart. It is backward-compatible.
- Evaluator: PASS WITH WARNINGS, 0 adversarial tests. Two silent risks fixed: a malformed `gh api graphql` reply caused a traceback (`_issue_node` now raises `TrackerError`), and `issue: null` crashed `status` (it now reports not on the board). Tests: `TestMalformedGraphql`.
- Evaluator risk accepted (parity): a failed dedup search is swallowed and the create proceeds (`_find_existing`), as `gh-create-issue.sh` did with `2>/dev/null || true`.
- Evaluator risk accepted: `_link_parent` turns a malformed epic node (`KeyError`/`ValueError`) into the "failed to link" warning, and create still exits 0. The issue already exists at that point, so failing would make re-runs harder.
- diag: no `.diagnostics/` in the worktree, no CodeScene MCP, and no local SonarQube analysis tool (`analyze_file_list` not exposed), so all three were skipped. shellcheck is clean on both shims. Python lint (ruff) did not run (no `uv`).
- Review blocker not actioned: the `Co-Authored-By` trailer is banned by `pr-review` `prompts/agent-a.md:44`, but the session attribution settings require it and 22 of the last 30 `main` commits carry it. Kept; escalated to the lead ([PR comment](https://github.com/mironyx/engineering-delivery-framework/pull/125#issuecomment-6901711862)).
- Review fixes (commit 7880646): exact-title guard before `--parent` writes on a dedup hit (agents A and B); the parent lookup no longer requests `projectItems`, so it needs no `read:project` scope (agent B); `_link_parent`/`_board_add` errors now carry detail (agent C). `_add_new_issue_to_board` stays detail-free because of the golden (accepted, commented).
- Test data, not assertions: 3 test-author fixtures modelled a dedup hit with an existing issue titled "Some issue", which a search for TITLE cannot return. Set `title=TITLE`. The two link-warning assertions now include the reason suffix (contract change from review).
- Deferred to /lld-sync: 10 private helpers missing from LLD §1.2 Part B; `-f` vs `-F` for literal owner/name; Open question 4 to list the two silent-exit fixes.
- Fix: 46 source lines (> 20), so a second review round is required.
- Review round 2: agent A clean. Agent C found 2 warnings, both fixed: `_fetch_issue` defaults to board fields again (LLD §1.3/§1.4 `view`/`close` need `projectItems`), and only `create` passes `board=False`; the existing-issue write error now carries gh's stderr. Fix: ~15 source lines — self-checked, skipped re-review.
- Lead decision: keep the `Co-Authored-By` trailer for #119. The user decides repo-wide; if they say drop it, drop it at the feature-end squash-merge, with no commit rewrite.
- Minor, for /lld-sync: the `repo` parameter of `_fetch_issue` is used only by status (via `_issue_query`). `create` never passes it.

## Work completed
- [PR #125](https://github.com/mironyx/engineering-delivery-framework/pull/125), squash-merged.
- `plugins/edf/bin/_tracker_github.py`: create (dedup, dry-run, `--type epic`, `--parent` with epic checklist and `## Parent epic`, board add) and status (set and `--add-to-board`); argv-only `_gh` with explicit stdin.
- `gh-create-issue.sh` and `gh-project-status.sh` are now shims over `tracker.py`; the usage text stays in the shim for `$0` parity.
- Goldens: 27 scenarios recorded from the pre-port scripts (`tests/fixtures/record_tracker_golden.py`, `tests/fixtures/tracker_golden/`), replayed through both shims and `tracker.py`.
- Tests: `tests/test_tracker_github.py` (141, 51 of them golden runs); `test_tracker.py` +2 and 6 updated; full suite 892 passed, 18 skipped. `test_shell_scripts.py` unchanged (I7).

## Decisions made
- Kept the parity-bound board-add warning in `create` detail-free; it is the one swallow left on purpose (see Concerns).
- `--type` other than task|epic is rejected with `Error: unknown type '<t>'. Use: task | epic` (the LLD gave no wording).
- Moved the epic checklist placement into the pure function `_add_checklist_line`, so its rules (T-line replacement, then placeholder, then append) are testable without gh.

## Review feedback addressed
- [compliance] commit 660ae6c `Co-Authored-By` trailer: not a defect (lead decision; matches `main` history).
- [silent-swallow] `_tracker_github.py` `_board_add`: fixed in 7880646.
- [silent-swallow] `_tracker_github.py` `_link_parent`: fixed in 7880646.
- [silent-swallow] `_tracker_github.py` `_add_new_issue_to_board`: not a defect (golden pins stderr, I6; commented).
- [bug] dedup hit + `--parent` writes to a fuzzy match: fixed in 7880646 (exact-title guard).
- [anti-pattern] `projectItems` needs `read:project` on the parent lookup: fixed in 7880646, refined in fae4ef1.
- [unspecified-function] ×10, [deviation-form] `-f`/`-F`: fixed by lld-sync (LLD v0.3).
- r2 [deviation-form] `_fetch_issue` lost board fields by default: fixed in fae4ef1. r2 [silent-swallow] task write stderr: fixed in fae4ef1.
- Comments: [round 1](https://github.com/mironyx/engineering-delivery-framework/pull/125#issuecomment-6901711862), [round 2](https://github.com/mironyx/engineering-delivery-framework/pull/125#issuecomment-6901739805).

## LLD Sync report

## LLD Sync — Issue #119: GitHub backend create and status, byte-identical, with shims

### Corrections (spec was wrong)
- Open question 4: the spec expected today's not-on-board and URL-without-number errors, but bash exits silently there (`set -e` + `pipefail`). Listed as intentional changes; the goldens carry `port_*` overrides.
- `_fetch_issue`: the spec always ran `ISSUE_QUERY`, which needs `read:project` even for the parent lookup. It now takes `board=False` for create and keeps board fields as the default for §1.3/§1.4.
- Literal owner/name are passed with `-f`, not `-F`, because placeholders only need `-F` and `-F` would type a numeric owner.
- `_link_child` on a dedup hit: the spec linked whatever `in:title` matched. It now requires an exact title match (`_ensure_parent_section`).

### Additions (not in spec)
- Helpers: `_issue_query`, `_issue_node`, `_read_project_env`, `_add_checklist_line`, `_ensure_parent_section`, `_link_parent`, `_find_existing`, `_print_dry_run`, `_add_new_issue_to_board`, `_passthrough`, `_BASE_FIELDS`/`_PLAIN_ISSUE_QUERY`.
- Error detail: link warnings carry the reason; a malformed `item-add` or GraphQL reply raises an `Error:` instead of a traceback; `issue: null` on status means not on the board.
- Golden format: `tracker_argv`, `{script}`/`{cwd}` tokens, a `--rev` recorder; `fake_gh` rules gain `argv_contains`.
- `--type` validation; empty `--title`/`--body` counted as missing.

### Omissions (in spec but not built)
- None.

### Confirmations (notable)
- Hand-rolled create/status parsing kept byte parity for all 27 goldens without argparse.
- The usage text in the shims (for `$0`) and `remove` printing usage, as designed.

### LLD updated
File: plugins/edf/docs/design/v3/lld-v3-e3-1-tracker-script.md §1.2 Part B, Open question 4
Version: 0.2 → 0.3
Coverage manifest: `coverage-v3-e3-1.yaml` REQ-tracker-script-create-issue and REQ-tracker-script-change-status → `files:` filled, `status: Revised`.

## Cost retrospective

| Bucket | Cost | Share |
|--------|------|-------|
| Session start → 3c (setup, LLD read, golden recording) | $1.42 | 14% |
| 3c → 5 (test-author, implementation, test fixes) | $2.73 | 27% |
| 5 → 8 (diag, evaluator, fixes, PR) | $0.91 | 9% |
| 8 → 9 (3 + 2 review agents, 2 fix rounds) | $4.18 | 41% |
| 9 → final (report, feature-end, lld-sync) | $0.93 | 9% |
| **Total** | **$10.17** (PR creation $5.06; post-PR delta $5.11) | |

- **Review was the biggest driver (41%).** Five agent spawns each re-read the ~1,800-line diff (mostly golden JSON). Next time, pass the review agents a numstat-based exclusion for `tests/fixtures/tracker_golden/`, or run Agent B only when the LLD marks a surface Unverified.
- **Review found what the evaluator missed:** the fuzzy dedup write and the `read:project` scope. Add "a new write on a fuzzy-match path" and "token scope of new queries" to the test-author/evaluator property checklist.
- **Golden-first paid off:** recording before porting surfaced two dead error paths early, and the implementation went green on attempt 1.

## Next steps
- #120 — GitHub view/list/edit/comment. Reuse `_fetch_issue` (board fields default), `_board_item`, `_write_body`.
- #121 — GitHub close, absorbing `check-epic-checkbox.py`.
- E3.3 — migrate call sites and drop the T-line substitution from `gh-issue-manager` (Open question 3).
- Infra: `run-tests.sh`/`run-lint.sh` need `uv`; Python lint has not run for E3.1 so far.
