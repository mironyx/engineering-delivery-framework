# Session log — EDF-143

## Approach rationale
- **Issue:** #143
- **Approach chosen:** New `_feature_id.py` owns prefix derivation, Jira-key/GitHub-number resolution and PR issue lines; `tracker.active_backend` validates config locally; tag-session, append-checkpoint, query-feature-cost and create-feature-pr.sh delegate to it.
- **LLD deviations:** Jira key shape is checked generically (`KEY-n`, upper-cased), not against `JIRA_SPACE`, because the resolver must not read Jira settings (invariant I5). Skill prose (feature-core, feature-end) now calls `feature-id.py`.
- **Pressure:** standard — ~110 src lines across 6 files.

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 8 | 2026-11-17T17:34:53Z | $0.85 | 2,473 in / 18,374 out | [PR](https://github.com/mironyx/engineering-delivery-framework/pull/154) [models: claude-sonnet-5-5 $0.85, claude-haiku-5-5 $0.00] |
| 9 | 2026-11-17T17:36:45Z | $1.38 | 2,509 in / 26,985 out | review: 2 agents, justification/reuse fixes applied [models: claude-sonnet-5-5 $1.38, claude-haiku-5-5 $0.00] |
| 10 | 2026-11-17T17:37:17Z | $1.41 | 2,513 in / 27,340 out | report done; CI none (no workflows) [models: claude-sonnet-5-5 $1.41, claude-haiku-5-5 $0.00] |

## Concerns & Deferred Items
- Test-author/evaluator sub-agents were not spawned; tests written inline in `tests/test_feature_id.py`. Reviewer should weigh coverage accordingly.
- `query-feature-cost.py --issue` is still `int` and applies labels via `gh`; Jira refs there are Task 6 (LLD §Cost labels), only its prefix derivation moved here.
- `tests/test_shell_scripts.py::TestGhCreateIssue` fails locally (hits live GitHub, `exists:150`) — unrelated to this change.
- PR review: added `Justification:` comments, `main_checkout_root` now raises TrackerError outside git and replaces the `git_root()` copies in tag-session/append-checkpoint. `query-feature-cost.py` keeps its `FEAT` fallback and int `--issue` (Task 6 owns it). Co-Authored-By trailer kept per session attribution instruction.
- Checkpoints 3c–6b were never recorded (steps run without `append-checkpoint.py`); that cost data cannot be backfilled.

## Work completed
- [PR #154](https://github.com/mironyx/engineering-delivery-framework/pull/154): `_feature_id.py`, `feature-id.py`, `tracker.active_backend`.
- Consumers moved: `tag-session`, `append-checkpoint`, `query-feature-cost` (prefix only), `create-feature-pr.sh`; feature-core/feature-end prose call `feature-id.py`.
- `tests/test_feature_id.py` (new); `TestDeriveFeaturePrefix` moved from `test_utils.py`; 1950 tests pass.
- Version 0.10.83 (plugin.json, marketplace.json).

## Decisions made
- Jira key shape checked generically, not against `JIRA_SPACE` (resolver never reads Jira settings, I5).
- `main_checkout_root` shared by resolver CLI, tag-session and append-checkpoint.

## Review feedback addressed
- [unspecified-function] `_feature_id.py` helpers — fixed in a6392a1 (`Justification:` comments).
- [kernel-reuse] duplicate `git_root()` — fixed in a6392a1 (tag-session, append-checkpoint); query-feature-cost left for Task 6.
- [diagnostic] `main_checkout_root` outside git — fixed in a6392a1 (raises TrackerError).
- [deviation-form] `query-feature-cost.py` int `--issue` / `FEAT` fallback — deferred to LLD Task 6.
- [compliance] `Co-Authored-By` trailer — not a defect (required by session attribution instruction).

## LLD Sync report
## LLD Sync — Issue #143: Feature identity resolver and consumers

### Corrections (spec was wrong)
- Jira ref check: spec said "exactly what `_parse_ref` accepts" (space-aware) → generic `KEY-n` shape, because the resolver must not read Jira settings. §1.1.

### Additions (not in spec)
- `main_checkout_root()` in `_feature_id.py`, shared by the CLI, tag-session and append-checkpoint (replaces their `git_root()` copies).
- `find_session_jsonl(claude_dir, feature_id, issue_number)` signature.

### Omissions (in spec but not built)
- `query-feature-cost.py` `--issue` as a ref string: deferred to Task 6.

### Confirmations (notable)
- PR body lines, invalid-config exit 1 with one `Error:` line, and `create-feature-pr.sh` aborting before `gh pr create` built as specified.

### LLD updated
File: plugins/edf/docs/design/v3/lld-v3-e3-3-pipeline-call-sites.md §1.1
Version: 0.2 → 0.3

## Cost retrospective
| Bucket | Cost |
|--------|------|
| Start → PR (step 8) | $0.85 |
| PR → review done (step 9) | +$0.53 |
| Final total | $1.66 |
- Drivers: two review agents plus rework of helper duplication ($0.53); steps 3c–6b untracked.
- Action: record `append-checkpoint.py` rows at every step; add justification comments and reuse the shared root helper before review.

## Next steps
- Task 6: `query-feature-cost.py` ref-string `--issue` and tracker-routed labels.
- Rebase expected against #147 (`tests/test_shell_scripts.py`).
