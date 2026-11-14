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

<a id="REQ-tracker-script-select-tracker"></a>

### Story 1.1: Select the tracker from the environment

**As a** Project Maintainer,
**I want to** switch EDF to Jira by setting `JIRA_HOST`, `JIRA_EMAIL`, `JIRA_API_TOKEN` and `JIRA_PROJECT`,
**so that** changing tracker needs no edits to code or skills.

*(Acceptance criteria in next pass)*

---

<a id="REQ-tracker-script-create-issue"></a>

### Story 1.2: Create an issue

**As an** EDF skill,
**I want to** create an issue from a title, Markdown body, labels and an optional parent epic, skipping it if an open issue with the same title already exists,
**so that** `/kickoff`, `/architect` and `/bug` file work into the active tracker.

*(Acceptance criteria in next pass)*

---

<a id="REQ-tracker-script-read-issues"></a>

### Story 1.3: View and list issues

**As an** EDF skill,
**I want to** fetch an issue (title, Markdown body, labels, status, parent, children) and list issues by status or label,
**so that** `/feature` can pick the next item and agents can read the brief.

*(Acceptance criteria in next pass)*

---

<a id="REQ-tracker-script-update-issue"></a>

### Story 1.4: Edit, comment on and change the status of an issue

**As an** EDF skill,
**I want to** replace an issue's body, add labels, add a comment, and move it between `todo`, `in progress`, `blocked` and `done`,
**so that** the tracker reflects pipeline progress.

*(Acceptance criteria in next pass)*

---

## Epic 2: Pipeline on Jira [Priority: High]

Moves the skills onto the tracker script and handles the places that assume GitHub. When this
epic is done, `/architect` → `/feature` → `/feature-end` runs end to end on a Jira-tracked
project.

<a id="REQ-pipeline-on-jira-epics"></a>

### Story 2.1: Native Jira epics

**As an** EDF skill,
**I want to** create epics as Jira Epics, give tasks the epic as `parent`, and read epic progress from child statuses instead of body checkboxes,
**so that** the epic model in ADR-0018 works in Jira.

*(Acceptance criteria in next pass)*

---

<a id="REQ-pipeline-on-jira-issue-references"></a>

### Story 2.2: Jira issue references in branches and PRs

**As an** Operator,
**I want to** use `SCRUM-123` in branch names, PR bodies and session logs, and have `/feature-end` move the issue to Done on merge,
**so that** the issue still gets closed without GitHub's `Closes #N`.

*(Acceptance criteria in next pass)*

---

<a id="REQ-pipeline-on-jira-migrate-skills"></a>

### Story 2.3: Migrate skills and agents to the tracker script

**As an** Operator,
**I want to** have every skill, agent and bin script that calls `gh issue` / `gh project` use the tracker script instead,
**so that** no part of the pipeline bypasses Jira.

*(Acceptance criteria in next pass)*

**Notes:** This is likely 2–3 PRs grouped by pipeline area (design, implementation, reporting). `/kickoff` or `/architect` will do the split.

---

<a id="REQ-pipeline-on-jira-guard-direct-calls"></a>

### Story 2.4: Guard against direct tracker calls

**As a** maintainer of EDF,
**I want to** a test that fails when any file other than the GitHub backend calls `gh issue` / `gh project`,
**so that** later changes cannot quietly bypass Jira routing.

*(Acceptance criteria in next pass)*

---

## Epic 3: Onboarding [Priority: Medium]

<a id="REQ-onboarding-setup-tracker"></a>

### Story 3.1: `/setup` configures the tracker

**As a** Project Maintainer,
**I want to** have `/setup` ask which tracker to use, write `.env` placeholders for the Jira variables, and run a connection check,
**so that** new adopters get Jira working without reading script sources.

*(Acceptance criteria in next pass)*

---

## Cross-Cutting Concerns

### Security

- **Secrets:** `JIRA_API_TOKEN` never appears in stdout, stderr, session logs, issue bodies or Prometheus files. Errors name the variable, not its value.
- **AuthN:** Use basic auth (email and API token) over HTTPS only, and reject a `JIRA_HOST` that is not `https://`. Report Jira's 401 and 403 as named errors without retrying.
- **Injection:** Pass titles, bodies and search terms as JSON or escaped JQL. Never build them into shell or JQL strings by concatenation.

### Performance

- The volume is small: tens of issues per `/architect` run. List operations are capped at 100 items, the same as today's `gh issue list --limit 100`.
- On a Jira 429, retry up to 3 times, honouring `Retry-After`.

### Observability

- Each operation prints one machine-parseable result line (`created:<ref>`, `exists:<ref>`, `updated:<ref>`).

## What We Are NOT Building

- **Jira Server / Data Center, or OAuth.** V3 supports Cloud with an API token only.
- **Company-managed Jira projects.** They link epics differently and use custom workflows.
- **Configurable status or issue-type mapping.** V3 uses fixed defaults (see Open Questions); mapping can be added when a second project needs it.
- **Moving code hosting off GitHub.** PRs, CI and reviews stay on GitHub.
- **Migrating or syncing existing GitHub issues.** Only one tracker is active per project.
- **Sprint management.**

## Open Questions

The proposed default for each question is option (a), the simplest choice.

| # | Question | Context | Options | Impact |
|---|----------|---------|---------|--------|
| 1 | What are the env var names? | The machine already has the FCS test credentials `JIRA_TEST_SITE_URL`, `JIRA_TEST_EMAIL`, `JIRA_TEST_API_TOKEN` and `JIRA_TEST_SPACE_KEY`. | (a) `JIRA_HOST`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT`; (b) the FCS names without `_TEST` | Story 1.1 |
| 2 | How is `blocked` represented? | SCRUM has no Blocked status. | (a) a `blocked` label, status unchanged; (b) the Jira flag | Story 1.4 |
| 3 | How do statuses map? | Jira statuses are To Do, Design, In Progress, In Review and Done. | (a) fixed mapping: `todo`→To Do, `in progress`→In Progress, `done`→Done, with Design and In Review unused | Story 1.4 |
| 4 | How does `/feature` pick the "top Todo" item? | Jira orders issues by rank. | (a) JQL `status = "To Do" ORDER BY rank`; (b) active sprint first | Story 1.3 |
| 5 | Are EDF labels kept as labels or mapped to issue types? | EDF uses `kind:task`, `bug`, `enhancement`. | (a) keep them as Jira labels, with all issues of type Task except epics | Story 1.2 |
