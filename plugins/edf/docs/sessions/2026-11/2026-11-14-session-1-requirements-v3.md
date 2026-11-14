# Session log — requirements v3 (Jira issue tracker)

## Summary

Produced `plugins/edf/docs/requirements/v3-requirements.md`. With `JIRA_HOST` set, EDF routes all issue tracking to Jira Cloud. Code and PRs stay on GitHub. The document has 3 epics, 9 stories and 58 ACs, and is Final. Two things pivoted during the session:

- **Body format.** The design moved from ADF to plain Markdown over REST API v2, then back to ADF. It returned to ADF because FCS reads Jira bodies as ADF.
- **Migration stories.** The skill migration was split into three stories for review, then merged back into one.

## Shipped

| Commit | Scope |
|---|---|
| 8755a73 | Structure: epics, stories, roles |
| 375d723 | Structure review fixes |
| 681da4c | Acceptance criteria and Gate 1 decisions |
| 76ac91c | Testability and review fixes |
| ef2baee | ADF conversion; migration stories merged |
| d20855f | Finalised |

## Board state

No issues created. `/kickoff` creates the epics.

## Cross-cutting decisions

- One tracker script is the only path to issues. Skills never call `gh issue` / `gh project`, and a guard test enforces this.
- Configuration is `JIRA_HOST`, `JIRA_EMAIL`, `JIRA_API_TOKEN` and `JIRA_SPACE`, kept distinct from the FCS `JIRA_TEST_*` variables.
- Only team-managed Cloud spaces are supported, with native Epics through `parent`.
- Status mapping is fixed: To Do, In Progress, Blocked, Done. The space must have a Blocked status.
- REST API v3, with Markdown converted to and from ADF for a defined subset.

## What didn't go to plan

- **The first draft wrote into a gitignored `docs/` path.** EDF's own docs live under `plugins/edf/docs/`, where v1 and v2 already exist. The worktree and branch were renamed to v3.
- **No git identity was configured in the environment.** Commits used the repo's historical author identity through `-c`.
- **The ADF/v2 flip.** The automated review correctly said v2 accepts plain strings, but that missed a consumer of the Jira data: FCS.

## Process notes for /retro

- `/requirements` defaults to `docs/requirements/`. It should resolve the requirements directory through `kb/file-map.md`, since this repo uses `plugins/edf/docs/requirements/`.
- In the brief, the user assumed that changing the issue script would be enough. In fact about 40 direct `gh` calls bypass it. A `/backlog` check for direct-call counts would catch this earlier.

## Skill self-reflection

- **Went well.** Probing the live Jira space (issue types, statuses) answered several open questions with facts rather than guesses.
- **Struggled.** The format decision ignored consumers of the data outside EDF.
- **Suggestion.** Add a Step 1 prompt to SKILL.md: "List other systems that read or write the data this feature touches."

## Next step

1. Add a Blocked status to `SCRUM`.
2. Run `/kickoff plugins/edf/docs/requirements/v3-requirements.md`.
