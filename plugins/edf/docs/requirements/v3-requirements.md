# EDF Jira Issue Tracker — V3 Requirements

## Document Control

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Status | Final |
| Author | LS / Claude |
| Created | 2026-11-14 |
| Last updated | 2026-11-14 |

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-11-14 | LS / Claude | Initial draft |
| 1.0 | 2026-11-14 | LS / Claude | Final |
| 0.4 | 2026-11-14 | LS / Claude | Back to REST API v3 with Markdown↔ADF conversion for a defined subset (DP7, Glossary), because FCS reads Jira bodies as ADF and v2 plain text would reach it as mangled wiki markup. The cost is a two-way converter in the script. Stories 2.3–2.5 merged into 2.3, a single routing story. |
| 0.3 | 2026-11-14 | LS / Claude | Jira backend uses REST API v2 with Markdown stored unchanged, instead of converting to ADF. This removes a two-way converter, and the accepted cost is that Markdown looks rough in Jira's UI (DP7). Story 2.1 no longer auto-closes epics, to match today's GitHub behaviour. Story 2.2 changed from branch names to `FEATURE_ID`, because branches don't carry the issue number. Gate 2 fixes: 1.1 429/5xx AC; 1.2 `--type epic` and open-issue definition; 1.5 reopen AC; 2.3/2.4 negative ACs; 3.1 `.gitignore`. |
| 0.2 | 2026-11-14 | LS / Claude | Gate 1 decisions: `JIRA_SPACE` var; Blocked status required; fixed status mapping, rank ordering and labels added as glossary and DP6; ACs written |

---

## Context / Background

EDF tracks work in GitHub Issues and a GitHub Projects board. Issue access is split between
two scripts (`bin/gh-create-issue.sh`, `bin/gh-project-status.sh`) and direct `gh issue` /
`gh project` calls in about 20 skill, agent and bin files. Teams that plan in Jira cannot
adopt EDF without keeping work items in two places.

V3 lets a host project send all issue tracking to Jira Cloud. Code, PRs and CI stay on
GitHub. Setting `JIRA_HOST` is the only switch. Without it, EDF behaves exactly as it does
today. The reference target is the `SCRUM` space on `mironyx.atlassian.net`. It is a
team-managed project with native Epics, where a Task points to its Epic through `parent`.
EDF requires the space's workflow to have To Do, In Progress, Blocked and Done. `SCRUM` also has Design and In Review, which EDF does not use; Blocked must be added to it.

## Glossary

| Term | Definition |
|------|-----------|
| **Tracker** | Where work items live: GitHub Issues (default) or Jira. |
| **Tracker script** | The one EDF script that skills and agents use for every issue operation. |
| **Issue reference** | The tracker's own ID: `#123` for GitHub, `SCRUM-123` for Jira. |
| **Space** | A Jira project, identified by its key (e.g. `SCRUM`). |
| **Board status** | EDF's logical states: `todo`, `in progress`, `blocked`, `done`. |
| **Status mapping** | Fixed: `todo`→To Do, `in progress`→In Progress, `blocked`→Blocked, `done`→Done. Other statuses are ignored. |
| **ADF** | Atlassian Document Format, the JSON rich-text format REST API v3 uses for bodies and comments. FCS reads Jira bodies as ADF. |
| **Supported Markdown** | Headings, paragraphs, bold, italic, inline code, links, bullet and numbered lists (nested), fenced code blocks, tables, task-list checkboxes. |
| **Open issue** | GitHub: state open. Jira: status category not Done. |

## Design Principles / Constraints

1. **Simplest thing that works.** Support one Jira setup, the team-managed Cloud space shown by `SCRUM`, with fixed defaults. Add configuration only when a real project needs it.
2. **GitHub stays the default.** With `JIRA_HOST` unset, all output is unchanged and existing adopters need no migration.
3. **One switch, fail loudly.** Setting `JIRA_HOST` selects Jira. If a required companion variable is missing, the script stops with an error that names it. EDF never falls back to GitHub without saying so.
4. **One script for all issue operations.** Skills and agents call the tracker script and never call `gh issue`, `gh project` or the Jira API directly. `gh pr` and `gh run` are unaffected. The script extends the existing `gh-create-issue.sh` contract (`created:<ref>` / `exists:<ref>`).
5. **Credentials come from the environment only.** They are read from the OS environment first, then `.env`, using the existing `_edf_env.py` precedence. They are never written to committed files or logs.
6. **Labels stay labels.** EDF labels (`kind:task`, `bug`, …) become Jira labels. Every issue is a Task except epics. The next item is the highest-ranked To Do issue.
7. **Skills read and write Markdown; Jira stores ADF.** The Jira backend uses REST API v3. The script converts Supported Markdown to ADF on write and back on read, so issues read properly in Jira's UI and in FCS. Constructs outside the supported set are kept as plain text, never dropped.

## Roles

| Role | Type | Description |
|------|------|-----------|
| **Project Maintainer** | Persistent | Configures EDF for a host project: picks the tracker and sets credentials and the space. |
| **Operator** | Persistent | Runs EDF skills (`/architect`, `/feature`, `/bug`, …). |
| **EDF skill** | Contextual | Calls the tracker script automatically during a pipeline run. |

Jira permissions are those of the API token's user. EDF adds no permission layer of its own.

---

## Epic 1: Tracker Script [Priority: High]

Every other epic depends on this one. It builds the single entry point, with a GitHub backend
(today's behaviour, moved behind the script) and a new Jira backend.

<a id="REQ-tracker-script-select-tracker-from-environment"></a>

### Story 1.1: Select tracker from environment

**As a** Project Maintainer,
**I want to** switch EDF to Jira by setting `JIRA_HOST`, `JIRA_EMAIL`, `JIRA_API_TOKEN` and `JIRA_SPACE`,
**so that** changing tracker needs no edits to code or skills.

**Acceptance Criteria:**

- Given `JIRA_HOST` is unset, when any tracker operation runs, then it uses the GitHub backend and its output is byte-identical to today's `gh-create-issue.sh` / `gh-project-status.sh` output.
- Given `JIRA_HOST`, `JIRA_EMAIL`, `JIRA_API_TOKEN` and `JIRA_SPACE` are set in the OS environment, when an operation runs, then it uses the Jira backend against that host and space.
- Given the variables are set only in the repo's `.env`, when an operation runs, then the Jira backend is used; given a variable is set in both, then the OS value wins.
- Given `JIRA_HOST` is set and any of `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_SPACE` is missing, when an operation runs, then it exits non-zero with `Error: JIRA_HOST is set but <VAR> is missing` and makes no GitHub or Jira call.
- Given `JIRA_HOST` does not start with `https://`, when an operation runs, then it exits non-zero with `Error: JIRA_HOST must use https://`.
- Given Jira returns 401 or 403, when an operation runs, then it exits non-zero with `Error: Jira authentication failed (<status>)` and the token value appears in no output.
- Given Jira returns 429 or a 5xx, when an operation runs, then it exits non-zero with `Error: Jira request failed (<status>)` and does not retry.

---

<a id="REQ-tracker-script-create-issue"></a>

### Story 1.2: Create issue

**As an** EDF skill,
**I want to** create an issue from a title, Markdown body, labels and an optional parent epic, skipping it if an open issue with the same title already exists,
**so that** `/kickoff`, `/architect` and `/bug` file work into the active tracker.

**Acceptance Criteria:**

- Given no open issue has the exact title, when create runs with title, Markdown body and labels, then the issue is created as type Task with the body converted to ADF and the labels applied, and the script prints `created:SCRUM-<n>`.
- Given an open issue with the exact same title exists, when create runs, then no issue is created and the script prints `exists:SCRUM-<n>`.
- Given only a closed issue has that title, when create runs, then a new issue is created.
- Given `--type epic`, when create runs, then the issue is created as type Epic (GitHub: an issue with the `epic` label, as today).
- Given `--parent SCRUM-<e>` names an Epic, when create runs, then the new Task's `parent` is that epic.
- Given `--parent` names an issue that does not exist, when create runs, then it exits non-zero with `Error: parent SCRUM-<e> not found` and creates nothing.
- Given `--dry-run`, when create runs, then it prints the planned title, labels and parent and makes no write call.
- Given the title contains quotes, `"`, `\` or JQL keywords, when the duplicate check runs, then it matches only the exact title and raises no error.
- Given the GitHub backend, when create runs with the same arguments, then behaviour matches today's `gh-create-issue.sh`, and `--parent` adds the task to the epic body's checklist.

---

<a id="REQ-tracker-script-view-and-list-issues"></a>

### Story 1.3: View and list issues

**As an** EDF skill,
**I want to** fetch an issue (title, Markdown body, labels, status, parent, children) and list issues by status or label,
**so that** `/feature` can pick the next item and agents can read the brief.

**Acceptance Criteria:**

- Given an issue exists, when view runs with its reference, then it prints JSON with `ref`, `title`, `body` (Markdown), `labels`, `status` (EDF board status), `parent` and `children` (refs).
- Given a body using every Supported Markdown construct, when it is created and then viewed, then the returned Markdown has the same headings, list structure, code block content and language, link text and targets, and table cells.
- Given a body created in Jira's own UI, when it is viewed, then `body` is Markdown, and any ADF node outside the supported set is rendered as its text content.
- Given a body containing an unsupported Markdown construct (e.g. raw HTML), when it is created, then the text survives as a plain paragraph and the create succeeds.
- Given a reference that does not exist, when view runs, then it exits non-zero with `Error: SCRUM-<n> not found`.
- Given issues in several statuses, when list runs with `--status todo`, then it returns only issues in To Do, ordered by Jira rank.
- Given list runs with `--label kind:task`, then it returns only issues with that label.
- Given more than 100 matching issues, when list runs, then it returns at most 100.
- Given the GitHub backend, when view or list runs, then it returns the same JSON shape for GitHub issues.

---

<a id="REQ-tracker-script-edit-and-comment"></a>

### Story 1.4: Edit and comment

**As an** EDF skill,
**I want to** replace an issue's body, add or remove labels, and add a Markdown comment,
**so that** `/architect` and `/lld-sync` can enrich issues and record progress.

**Acceptance Criteria:**

- Given an issue, when edit runs with `--body <markdown>`, then the issue body is replaced (converted to ADF) and the script prints `updated:<ref>`.
- Given an issue, when edit runs with `--add-label a --remove-label b`, then `a` is present, `b` is absent, and other labels are unchanged.
- Given `--remove-label` names a label the issue does not have, when edit runs, then it succeeds with no change.
- Given an issue, when comment runs with Markdown text, then a comment with that content appears on the issue and the script prints `commented:<ref>`.
- Given a reference that does not exist, when edit or comment runs, then it exits non-zero with `Error: <ref> not found`.

---

<a id="REQ-tracker-script-change-status"></a>

### Story 1.5: Change status

**As an** EDF skill,
**I want to** move an issue to `todo`, `in progress`, `blocked` or `done`,
**so that** the tracker reflects pipeline progress.

**Acceptance Criteria:**

- Given an issue in To Do, when status runs with `in progress`, `blocked` or `done`, then the issue moves via a Jira transition to In Progress, Blocked or Done respectively, and the script prints `<ref> → <status>`.
- Given an issue in In Progress or Blocked, when status runs with `todo`, then it moves to To Do.
- Given an issue already in the target status, when status runs, then it succeeds with no change.
- Given the space has no status named `Blocked`, when status runs with `blocked`, then it exits non-zero with `Error: space SCRUM has no "Blocked" status — add it to the workflow`.
- Given no transition leads from the current status to the target, when status runs, then it exits non-zero, naming the current and target statuses.
- Given an unknown status value, when status runs, then it exits non-zero, listing `todo | in progress | blocked | done`.
- Given the GitHub backend, when status runs, then behaviour matches today's `gh-project-status.sh`.

---

## Epic 2: Pipeline on Jira [Priority: High]

Moves the skills onto the tracker script and handles the places that assume GitHub. When this
epic is done, `/architect` → `/feature` → `/feature-end` runs end to end on a Jira-tracked
project.

<a id="REQ-pipeline-on-jira-native-epics"></a>

### Story 2.1: Native epics

**As an** EDF skill,
**I want to** create epics as Jira Epics and read epic progress from the statuses of its child tasks, instead of from checkboxes in the body,
**so that** the epic model in ADR-0018 works in Jira.

**Acceptance Criteria:**

- Given the Jira backend, when `/kickoff` or `/architect` creates an epic, then it calls create with `--type epic` and the epic is a Jira Epic.
- Given an epic with three child tasks, one in Done, when epic progress is read, then it reports 1 of 3 done and lists each child with its status.
- Given the Jira backend, when `/feature-end` completes a child task, then the epic's status is unchanged. Closing an epic stays manual, as it is today.
- Given the GitHub backend, when the same steps run, then the epic body checkbox behaviour (`check-epic-checkbox.py`) is unchanged.

---

<a id="REQ-pipeline-on-jira-jira-references-in-prs-and-logs"></a>

### Story 2.2: Jira references in PRs and logs

**As an** Operator,
**I want to** have the Jira key (`SCRUM-42`) used as the feature ID in PR bodies, session logs and cost tags, and have `/feature-end` move the issue to Done on merge,
**so that** Jira-tracked work flows through the same artefacts and still gets closed without GitHub's `Closes #N`.

**Acceptance Criteria:**

- Given the Jira backend and issue `SCRUM-42`, when `/feature-core` sets `FEATURE_ID`, then `FEATURE_ID=SCRUM-42` and `EDF_FEATURE_PREFIX` is not used.
- Given `FEATURE_ID=SCRUM-42`, when the session log is created, then its file name ends `-SCRUM-42.md`.
- Given a Jira-tracked feature, when the PR is created, then the body contains `Jira: SCRUM-42` and does not contain `Closes #`.
- Given a Jira-tracked feature, when `/feature-end` merges the PR, then `SCRUM-42` is moved to Done.
- Given the merge fails, when `/feature-end` stops, then `SCRUM-42` is not moved to Done.
- Given the GitHub backend, when the same flow runs, then `FEATURE_ID` (`<prefix>-<n>`), the PR body (`Closes #N`) and logs are unchanged. Branch names (`feat/<slug>`) are unchanged in both backends.

---

<a id="REQ-pipeline-on-jira-route-all-issue-calls-through-tracker-script"></a>

### Story 2.3: Route all issue calls through tracker script

**As an** Operator,
**I want to** have every skill, agent and bin script use the tracker script instead of `gh issue` / `gh project`,
**so that** the whole pipeline works on Jira, and changing tracker later needs no skill edits.

**Acceptance Criteria:**

- Given any file under `plugins/edf/skills`, `plugins/edf/agents` or `plugins/edf/bin` other than the GitHub backend calls `gh issue` or `gh project`, when the test suite runs, then a test fails, naming the file and line.
- Given a Jira-configured project, when `/architect` creates an epic and tasks, then they appear in the Jira space with the tasks parented to the epic, and no GitHub issue is created.
- Given a Jira-configured project with a To Do task, when `/feature` runs, then it picks the top-ranked To Do task, moves it to In Progress and reads its body through the tracker script.
- Given a Jira-configured project with no To Do task, when `/feature` runs, then it reports `No Todo items` and stops without creating a branch.
- Given the tracker script exits non-zero partway through a skill, when the failure occurs, then the skill stops and reports the error and any references already created.
- Given a Jira-configured project, when `/backlog` runs, then its report lists issues by `SCRUM-<n>` reference.
- Given a GitHub-configured project, when `/architect`, `/feature` and `/backlog` run, then they behave as they do today.

**Notes:** This is a mechanical substitution across about 20 files. It can ship as several PRs grouped by pipeline area. The guard-test AC is satisfied only by the last one. The end-to-end ACs are checked with a manual `/qa` run against `SCRUM`.

---

## Epic 3: Onboarding [Priority: Medium]

<a id="REQ-onboarding-setup-configures-tracker"></a>

### Story 3.1: Setup configures tracker

**As a** Project Maintainer,
**I want to** have `/setup` ask which tracker to use and write `.env` placeholders for the Jira variables,
**so that** new adopters know exactly what to set.

**Acceptance Criteria:**

- Given `/setup` runs and the Maintainer picks Jira, when it finishes, then `.env` contains `JIRA_HOST=`, `JIRA_EMAIL=`, `JIRA_API_TOKEN=` and `JIRA_SPACE=` placeholders, and `/setup` adds `.env` to `.gitignore` if it is not already there.
- Given `.env` already defines any of these, when `/setup` runs, then existing values are kept.
- Given the Maintainer picks GitHub, when `/setup` finishes, then no Jira placeholders are written.
- Given Jira is picked, when `/setup` finishes, then it reports that the space needs To Do, In Progress, Blocked and Done statuses.

---

## Cross-Cutting Concerns

### Security

- **Secrets:** `JIRA_API_TOKEN` never appears in stdout, stderr, session logs, issue bodies or Prometheus files. Errors name the variable, not its value.
- **AuthN:** Use basic auth (email and API token) over HTTPS only, and reject a `JIRA_HOST` that is not `https://`. Report Jira's 401 and 403 as named errors without retrying.
- **Injection:** Pass titles, bodies and search terms as JSON or escaped JQL. Never build them into shell or JQL strings by concatenation.

### Performance

- The volume is small: tens of issues per `/architect` run. List operations are capped at 100 items, the same as today's `gh issue list --limit 100`.
- No retries: a Jira 429 or 5xx fails the operation with a named error (Principle 3).

### Observability

- Each operation prints one machine-parseable result line (`created:<ref>`, `exists:<ref>`, `updated:<ref>`).

## What We Are NOT Building

- **Jira Server / Data Center, or OAuth.** V3 supports Cloud with an API token only.
- **Company-managed Jira projects.** They link epics differently and use custom workflows.
- **Configurable status or issue-type mapping.** V3 uses the fixed mapping in the Glossary; mapping can be added when a second project needs it.
- **Moving code hosting off GitHub.** PRs, CI and reviews stay on GitHub.
- **Migrating or syncing existing GitHub issues.** Only one tracker is active per project.
- **Sprint management.**
- **Retry/back-off and a standalone connection-check command.** At this volume, failing loudly is enough.

## Open Questions

None.

## Next steps

1. Add a Blocked status to the `SCRUM` workflow.
2. Run `edf:kickoff plugins/edf/docs/requirements/v3-requirements.md` to produce HLD, ADRs, and implementation plan.
