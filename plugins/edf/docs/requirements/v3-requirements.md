# EDF Jira Issue Tracker — V3 Requirements

## Document Control

| Field | Value |
|-------|-------|
| Version | 0.1 |
| Status | Draft — Structure |
| Author | LS / Claude |
| Created | 2026-11-14 |
| Last updated | 2026-11-14 |

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-11-14 | LS / Claude | Initial draft |

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
Its statuses are To Do, Design, In Progress, In Review and Done, with no Blocked status.

## Glossary

| Term | Definition |
|------|-----------|
| **Tracker** | Where work items live: GitHub Issues (default) or Jira. |
| **Tracker script** | The one EDF script that skills and agents use for every issue operation. |
| **Issue reference** | The tracker's own ID: `#123` for GitHub, `SCRUM-123` for Jira. |
| **Space** | A Jira project, identified by its key (e.g. `SCRUM`). |
| **Board status** | EDF's logical states: `todo`, `in progress`, `blocked`, `done`. |
| **ADF** | Atlassian Document Format, the JSON rich-text format that Jira Cloud requires for issue bodies and comments. |

## Design Principles / Constraints

1. **Simplest thing that works.** Support one Jira setup, the team-managed Cloud space shown by `SCRUM`, with fixed defaults. Add configuration only when a real project needs it.
2. **GitHub stays the default.** With `JIRA_HOST` unset, all output is unchanged and existing adopters need no migration.
3. **One switch, fail loudly.** Setting `JIRA_HOST` selects Jira. If a required companion variable is missing, the script stops with an error that names it. EDF never falls back to GitHub without saying so.
4. **One script for all issue operations.** Skills and agents call the tracker script and never call `gh issue`, `gh project` or the Jira API directly. `gh pr` and `gh run` are unaffected. The script extends the existing `gh-create-issue.sh` contract (`created:<ref>` / `exists:<ref>`).
5. **Credentials come from the environment only.** They are read from the OS environment first, then `.env`, using the existing `_edf_env.py` precedence. They are never written to committed files or logs.
6. **Skills keep using Markdown.** Skills write and read issue bodies as Markdown. The tracker script converts to and from ADF.

## Roles

| Role | Type | Description |
|------|------|-----------|
| **Project Maintainer** | Persistent | Configures EDF for a host project: picks the tracker and sets credentials and the space. |
| **Operator** | Persistent | Runs EDF skills (`/architect`, `/feature`, `/bug`, …). |
| **EDF skill / agent** | Contextual | Calls the tracker script automatically during a pipeline run. |

Jira permissions are those of the API token's user. EDF adds no permission layer of its own.

---

## Epic 1: Tracker Script [Priority: High]

Every other epic depends on this one. It builds the single entry point, with a GitHub backend
(today's behaviour, moved behind the script) and a new Jira backend.

<a id="REQ-tracker-script-select-tracker-from-environment"></a>

### Story 1.1: Select tracker from environment

**As a** Project Maintainer,
**I want to** switch EDF to Jira by setting the Jira env vars (host, email, API token, space key; names per Open Question 1),
**so that** changing tracker needs no edits to code or skills.

*(Acceptance criteria in next pass)*

---

<a id="REQ-tracker-script-create-issue"></a>

### Story 1.2: Create issue

**As an** EDF skill,
**I want to** create an issue from a title, Markdown body, labels and an optional parent epic, skipping it if an open issue with the same title already exists,
**so that** `/kickoff`, `/architect` and `/bug` file work into the active tracker.

*(Acceptance criteria in next pass)*

---

<a id="REQ-tracker-script-view-and-list-issues"></a>

### Story 1.3: View and list issues

**As an** EDF skill,
**I want to** fetch an issue (title, Markdown body, labels, status, parent, children) and list issues by status or label,
**so that** `/feature` can pick the next item and agents can read the brief.

*(Acceptance criteria in next pass)*

---

<a id="REQ-tracker-script-edit-and-comment"></a>

### Story 1.4: Edit and comment

**As an** EDF skill,
**I want to** replace an issue's body, add or remove labels, and add a Markdown comment,
**so that** `/architect` and `/lld-sync` can enrich issues and record progress.

*(Acceptance criteria in next pass)*

---

<a id="REQ-tracker-script-change-status"></a>

### Story 1.5: Change status

**As an** EDF skill,
**I want to** move an issue to `todo`, `in progress`, `blocked` or `done`,
**so that** the tracker reflects pipeline progress.

*(Acceptance criteria in next pass)*

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

*(Acceptance criteria in next pass)*

---

<a id="REQ-pipeline-on-jira-jira-references-in-branches-and-prs"></a>

### Story 2.2: Jira references in branches and PRs

**As an** Operator,
**I want to** use `SCRUM-123` in branch names, PR bodies and session logs, and have `/feature-end` move the issue to Done on merge,
**so that** the issue still gets closed without GitHub's `Closes #N`.

*(Acceptance criteria in next pass)*

---

<a id="REQ-pipeline-on-jira-migrate-design-skills"></a>

### Story 2.3: Migrate design skills

**As an** Operator,
**I want to** have `/kickoff`, `/architect`, `/refactor-architect`, `/bug`, `/create-plan`, `/lld` and `gh-issue-manager` use the tracker script,
**so that** design work files issues into Jira.

*(Acceptance criteria in next pass)*

---

<a id="REQ-pipeline-on-jira-migrate-implementation-skills"></a>

### Story 2.4: Migrate implementation skills

**As an** Operator,
**I want to** have `/feature`, `/feature-core`, `/feature-team`, `/feature-end`, `/lld-sync`, `/pr-review` and their agents use the tracker script,
**so that** `/feature` runs on a Jira-tracked project.

*(Acceptance criteria in next pass)*

---

<a id="REQ-pipeline-on-jira-migrate-reporting-skills"></a>

### Story 2.5: Migrate reporting skills

**As an** Operator,
**I want to** have `/backlog`, `/retro`, `/baseline` and `update-coverage-manifest.py` read through the tracker script,
**so that** reports reflect Jira work items and no `gh issue` / `gh project` call is left outside the GitHub backend.

*(Acceptance criteria in next pass)*

**Notes:** This is the last migration story, so its ACs include a test that fails on any direct `gh issue` / `gh project` call outside the GitHub backend.

---

## Epic 3: Onboarding [Priority: Medium]

<a id="REQ-onboarding-setup-configures-tracker"></a>

### Story 3.1: Setup configures tracker

**As a** Project Maintainer,
**I want to** have `/setup` ask which tracker to use and write `.env` placeholders for the Jira variables,
**so that** new adopters know exactly what to set.

*(Acceptance criteria in next pass)*

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
- **Configurable status or issue-type mapping.** V3 uses fixed defaults (see Open Questions); mapping can be added when a second project needs it.
- **Moving code hosting off GitHub.** PRs, CI and reviews stay on GitHub.
- **Migrating or syncing existing GitHub issues.** Only one tracker is active per project.
- **Sprint management.**
- **Retry/back-off and a standalone connection-check command.** At this volume, failing loudly is enough.

## Open Questions

The proposed default for each question is option (a), the simplest choice.

| # | Question | Context | Options | Impact |
|---|----------|---------|---------|--------|
| 1 | What are the env var names? | The machine already has the FCS test credentials `JIRA_TEST_SITE_URL`, `JIRA_TEST_EMAIL`, `JIRA_TEST_API_TOKEN` and `JIRA_TEST_SPACE_KEY`. | (a) `JIRA_HOST`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT`; (b) the FCS names without `_TEST` | Story 1.1 |
| 2 | How is `blocked` represented? | SCRUM has no Blocked status. | (a) a `blocked` label, status unchanged; (b) the Jira flag | Story 1.4 |
| 3 | How do statuses map? | Jira statuses are To Do, Design, In Progress, In Review and Done. | (a) fixed mapping: `todo`→To Do, `in progress`→In Progress, `done`→Done, with Design and In Review unused | Story 1.4 |
| 4 | How does `/feature` pick the "top Todo" item? | Jira orders issues by rank. | (a) JQL `status = "To Do" ORDER BY rank`; (b) active sprint first | Story 1.3 |
| 5 | Are EDF labels kept as labels or mapped to issue types? | EDF uses `kind:task`, `bug`, `enhancement`. | (a) keep them as Jira labels, with all issues of type Task except epics | Story 1.2 |
