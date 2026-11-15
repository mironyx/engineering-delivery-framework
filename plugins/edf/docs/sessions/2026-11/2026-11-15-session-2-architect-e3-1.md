# Session 2026-11-15 #2 — /architect 114 (E3.1 tracker script + GitHub backend)

## Summary

Produced the E3.1 LLD (`lld-v3-e3-1-tracker-script.md`), its coverage manifest and four
sequential task issues (#118–#121) under epic #114. The kickoff artefacts (HLD v3, ADR-0041,
plan) were still only on the unmerged `docs/v3-kickoff` branch, so the docs branch is stacked on
it rather than on `main`. `edf:lld-review` raised five blockers in round one (worktree `.env`
root, dry-run writing on a dedup hit, mis-marked External Surfaces, argparse vs bash parity,
status echo) and one in round two (status on an unknown issue); all were fixed before the
issues were created.

## Shipped

| Commit | Scope |
|--------|-------|
| `7655e42` | LLD + coverage manifest for #114 |
| `c2c6bff` | Coverage manifest backfill (#118–#121) |

## Board state

- Epic #114 body rewritten: Tasks checklist, dependency graph, waves (#118 → #119 → #120 → #121).
- New `kind:task` issues on the board in Todo: #118 entry point, #119 GitHub create/status +
  shims, #120 view/list/edit/comment, #121 close.

## Cross-cutting decisions

- Module split: `tracker.py` (entry), `_tracker_contract.py` (shared types), `_tracker_github.py`
  (backend); E3.2 adds `_tracker_jira.py` to `_BACKENDS`.
- GitHub parity is proven with golden files recorded from the pre-port bash scripts under a
  fake `gh` on `PATH`, not by mocking `subprocess`.
- GitHub `status` in `view`/`list`: closed → `done`, open → board column, else `todo`.
- `create --parent` owns the epic checklist and replaces matching `T<k> — <title>` lines; E3.3
  must drop the T-line substitution from `gh-issue-manager`.
- `.env` is resolved from the main checkout (`--git-common-dir`), `project.env` from the
  worktree.
- Intentional GitHub output changes are listed in the LLD's Open question 4.

## What didn't go to plan

- The plan file was on an unmerged branch; worktree from `main` would have lacked every input.
- The first draft took `.env` from `--show-toplevel`, which silently selects GitHub in a linked
  worktree (DP3 violation). Caught by `edf:lld-review`, not self-critique.
- The redundant-fetch fix introduced a new unspecified path (status on an unknown issue) —
  fixing a review warning created a review blocker.
- `gh-issue-manager` first rewrote mermaid node ids along with labels and had to re-edit #114.
- No `git` identity in the shell; commits used the repo-history identity via `-c`.

## Process notes for /retro

- `/architect` Step 1a assumes the plan is on `main`; kickoff leaves it on a branch with no PR.
  Either kickoff should open its PR or `/architect` should detect and offer stacking.
- `run-markdown-lint.sh` runs with default rules and fails on every existing doc, so it cannot
  gate docs PRs.
- `kb/architecture.md` is still the empty template; `edf:lld` asks for a reused-helpers table
  from it.

## Skill self-reflection

- Worked: running the GraphQL query against the live repo turned "recall-based" surfaces into
  measured ones (labels filter is ANY-match; not-found exit code).
- Struggled: parity-bound ports. Self-critique has no item for "byte-identical port: pin parser
  behaviour, message streams, check ordering". Suggestion: add a *Parity port* checklist item to
  `edf:lld` Step 2.5 covering argument-parser differences, stdout-vs-stderr, and error ordering.
- `gh-issue-manager`'s mermaid substitution rule is easy to misapply; a worked before/after
  example in the agent file would prevent the double edit.

## Next step

Review the docs PR (stacked on `docs/v3-kickoff`), merge kickoff first, then `/feature 118`.
