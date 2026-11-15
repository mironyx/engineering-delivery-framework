# 0041. Tracker Abstraction — One Script, Swappable Backends

**Date:** 2026-11-15
**Status:** Proposed
**Deciders:** LS / Claude

## Context

V3 adds Jira Cloud as an alternative issue tracker
([v3 requirements](../requirements/v3-requirements.md), [v3 HLD](../design/v3/v3-design.md)).
Today issue access is spread across two bash scripts (`gh-create-issue.sh`,
`gh-project-status.sh`), `check-epic-checkbox.py`, and inline `gh issue` / `gh project` calls
in 28 skill, agent, bin and starter files. Every one of them assumes GitHub.

Forces:

- **GitHub output must not change** for existing adopters (DP2, Story 1.1 AC1).
- **Skills are prompts.** Branching logic in a skill is followed probabilistically; branching
  logic in a script is tested. Twenty-eight prompt-level `if Jira … else …` branches would
  drift.
- **Jira needs real logic:** escaped JQL dedup, workflow transitions, parent validation,
  Markdown↔ADF conversion and credential redaction. None of that belongs in a prompt.
- **The plugin has no install step.** Scripts run on whatever Python `hooks/run-python.sh`
  finds; every existing `bin/*.py` is standard-library only (`urllib.request` for HTTP).

## Options Considered

### Option 1: One tracker script with swappable backends

A single entry point exposes `create`, `view`, `list`, `edit`, `comment`, `status`, `close`
and `tracker`. It resolves configuration and dispatches to a GitHub or Jira backend. Callers
see one contract regardless of tracker.

- **Pros:** callers never branch; Jira logic is unit-testable; GitHub parity is checked by
  the existing script tests; a third tracker is a new backend, not a skill sweep.
- **Cons:** one more indirection on every issue call; the GitHub logic now in bash and
  inline skill commands has to move behind the contract.

### Option 2: Per-tracker scripts, skills branch on `JIRA_HOST`

Keep the GitHub scripts; add `jira-*.py` scripts; each call site chooses.

- **Pros:** no change to the GitHub path.
- **Cons:** 28 files gain tracker branches; nothing stops a new skill from calling `gh issue`
  directly; output shapes diverge per call site.

### Option 3: Atlassian MCP server called from skills

Skills call Jira through an Atlassian MCP connector instead of a script.

- **Pros:** no HTTP or ADF code in EDF.
- **Cons:** not reachable from `bin/` scripts or every subagent; dedup, transition paths and
  epic linking would live in prompts; no deterministic test; adds a connector every adopter
  must configure.

## Decision

**Option 1.** EDF gets a single tracker script, and it is the only route to issue data.

- **Entry point and contract.** One Python script under `bin/`, run through
  `run-python.sh`. The operations, argument grammar, result lines (`created:` / `exists:` /
  `updated:` / `commented:` / `closed:` / `<ref> → <status>`), `view`/`list` JSON shape and
  `Error: …` forms are those in [HLD C3.1](../design/v3/v3-design.md#c31-tracker-script); the
  LLD pins them exactly. References are opaque strings (`#123`, `SCRUM-123`).
- **Selection.** `JIRA_HOST` unset → GitHub backend; set → Jira backend, after validating all
  four Jira variables and the `https://` scheme. No silent fallback in either direction
  (DP3). `tracker` reports the choice locally so other components never read `JIRA_HOST`.
- **Backends.** GitHub reproduces today's scripts byte for byte and is the only code allowed
  to call `gh issue`, `gh project` or `gh api …/issues`. Jira talks to REST API v3 with basic
  auth and is the only code that sends credentials. Markdown↔ADF conversion is a separate
  pure module the Jira backend calls.
- **`status` versus `close`.** `status` moves board state only (parity with
  `gh-project-status.sh`). `close` is the merge-time closure `/feature-end` calls: on GitHub
  it runs today's board → epic tick → `gh issue close` sequence, idempotently; on Jira it is
  the transition to Done.
- **Standard library only.** HTTP uses `urllib.request`, matching `query-feature-cost.py` and
  `append-checkpoint.py`, because the plugin cannot install packages into adopters'
  environments.
- **Enforcement.** A test under `tests/` fails, naming file and line, when any file in
  `skills/`, `agents/`, `bin/` or `starters/` outside the GitHub backend calls issue APIs
  ([HLD C3.8](../design/v3/v3-design.md#c38-issue-access-guard)).
- **Migration.** `gh-create-issue.sh` and `gh-project-status.sh` remain as thin shims that
  delegate to the tracker script, so call sites can migrate across several PRs. They are
  deleted once the guard test passes with no exclusions for them.

## Consequences

- Skills, agents and bin scripts depend on the tracker script's contract. Changing an output
  line or JSON field is now a breaking change for every caller and needs a version bump.
- **Testing the Jira backend conflicts with the project rule "respx for HTTP mocking".**
  respx mocks `httpx`, which the standard-library constraint rules out. Jira backend tests
  will instead run against a local fake HTTP server (a pytest fixture on `http.server`). This
  exercises the real request path without monkey-patching, but it is a stated exception to
  `CLAUDE.md` § Coding Principles and must be recorded there when the first Jira test lands.
- Adding a tracker (GitLab, Linear) means one backend module plus selection logic; no skill
  changes.
- The epic model changes on Jira (native Epics, `parent`, progress from child statuses);
  that is a revision to [ADR-0018](0018-epic-task-organisation.md), not part of this
  decision.
- Not chosen: retries and back-off, configurable status or issue-type mapping, a standalone
  connection check, and syncing between trackers. These are v3 non-goals.
