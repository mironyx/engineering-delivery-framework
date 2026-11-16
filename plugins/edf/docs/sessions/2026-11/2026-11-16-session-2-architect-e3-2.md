# Session 2026-11-16 #2 — /architect 115 (E3.2 Jira backend and Markdown↔ADF converter)

## Summary

Produced the E3.2 LLD (`lld-v3-e3-2-jira-backend.md`), its coverage manifest and seven task
issues (#128–#134) under epic #115. The user confirmed the overview first; the plan's five-task
sketch grew to seven after `edf:lld-review` flagged Tasks 1 and 2 as oversize (converter split
by direction, test fixture split from the client). The Jira API claims were verified against
Atlassian's official OpenAPI document, not recall: the search endpoint is `POST
/rest/api/3/search/jql` and `/search` is "Currently being removed".

## Shipped

| Commit | Scope |
|--------|-------|
| `82c4a49` | LLD draft + coverage manifest |
| `df7e6da` | Review fixes, seven-task split |
| manifest backfill | `issue:` numbers #131–#134 |
| (this PR) | Session log |

## Board state

- Epic #115 body rewritten: Tasks checklist, dependency graph, five waves.
- New `kind:task` issues in Todo: #128 Markdown→ADF, #129 ADF→Markdown, #130 `fake_jira`,
  #131 client + registration, #132 create, #133 view/list, #134 edit/comment/status/close.

## Cross-cutting decisions

- Task-list checkboxes become literal `[ ]` text: `taskList`/`taskItem` are not in Atlassian's
  documented ADF node index.
- Tests run against a local **HTTPS** fake with an `openssl`-generated certificate trusted via
  `SSL_CERT_FILE`, so the `https://` rule has no test-only seam.
- No redirect following and no retry, so credentials only reach the configured host once.
- `list --status` filters on the derived status that `view` prints; unmapped Jira statuses map by
  status category (a deliberate extension of the glossary's "other statuses are ignored").
- `--add-to-board`/`--board-status` are accepted and ignored on Jira.

## What didn't go to plan

- The Atlassian REST reference pages are JavaScript-rendered; the web-fetch agent got nothing.
  The published OpenAPI JSON was readable with `curl` and gave exact shapes and status codes.
- The first LLD draft had a markdown tokeniser with no flanking rule (`snake_case_name` would
  become emphasis) and a `list` filter that disagreed with the printed status; both caught by
  `edf:lld-review`, not the self-critique.
- E3.1's `test_token_never_printed` would have started calling `example.atlassian.net` once the
  Jira operations landed; review spotted it, the LLD did not.

## Process notes for /retro

- `gh-issue-manager` was not dispatched; the same `gh-create-issue.sh` was driven from a script
  that parsed the LLD's Tasks section directly, which avoided pasting seven bodies into a prompt.
  Worth making that the documented path.
- `park-docs.sh`-style tooling and `append-checkpoint.py` still assume `docs/`, not
  `plugins/edf/docs`.
- JQL text-search escaping and index lag remain unverified; the E3.2 exit criteria carry a real
  `SCRUM` smoke run for them (Task 7).

## Skill self-reflection

- Worked: reading the vendor's OpenAPI document turned most "recall-based" surfaces into verified
  ones, and the reviewer's Tier 2 pass found a real existing-test collision.
- Struggled: the External Surfaces `New to repo` column needed a grep per surface; no step says
  where to run it. Suggestion: have Step 2.5 list the exact greps for that column.

## Next step

Human reviews the docs PR; then `/feature-team epic 115` (waves 1: #128, #130).
