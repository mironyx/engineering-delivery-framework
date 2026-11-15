# 0018. Epic/Task Work Organisation

**Date:** 2026-04-02
**Status:** Accepted — revised 2026-11-15 for Jira-tracked projects (see
[Revision](#revision--2026-11-15))
**Deciders:** LS / Claude

## Context

The project started with long monolithic plan documents and phase-based LLD files
(`lld-phase-2-web-auth-db.md`). As the project grew, this proved inefficient:

- Plan documents covered too much scope, making it hard to track what was done vs pending.
- Phase-based LLD grouping mixed unrelated concerns (auth + DB + frontend in one file).
- No formal grouping between related implementation issues.

A cleaner model was needed: a lightweight container that groups related tasks into a
deliverable unit, with per-task design documents.

## Options Considered

### Option 1: Continue with phase-based organisation

Keep `lld-phase-<N>-<name>.md` naming. Group work by implementation phase.

- **Pros:** Already in use; no migration.
- **Cons:** Phases mix unrelated concerns. Hard to answer "what tasks remain for feature X?"
  No explicit parent-child relationship between issues.

### Option 2: Full agile epic management

Epics with burndown tracking, epic-level ADR indexes, epic summaries, dedicated epic
documents separate from issues.

- **Pros:** Rich traceability.
- **Cons:** Heavy ceremony for a small team. Maintenance overhead that would rarely be
  consulted. Most of the value comes from the grouping, not the reporting.

### Option 3: Lightweight epic/task model (chosen)

An **epic** is a GitHub issue with an `epic` label. Its body contains scope, success
criteria, and a task checklist linking child issues. A **task** is a standard GitHub issue
(typically `L5-implementation`) that references its parent epic. Each task gets its own
LLD file named `lld-<epic-slug>-<task-slug>.md`.

- **Pros:** Minimal ceremony. Reuses existing GitHub issues. Provides clear grouping.
  LLD naming makes epic membership obvious. L1-L5 labels remain orthogonal.
- **Cons:** No automated rollup (epic progress requires reading the checklist). Acceptable
  for team size.

## Decision

**Option 3 — lightweight epic/task model.**

- **Epic** = GitHub issue with `epic` label. Container only. Body lists scope, success
  criteria, and child task issues as a checklist.
- **Task** = GitHub issue (any L-level label). References parent epic. One LLD per task.
- **LLD naming:** `docs/design/lld-<epic-slug>-<task-slug>.md`.
- **L1-L5 labels** remain orthogonal — they describe design level, not hierarchy.
- **HLD** (`docs/design/v1-design.md`) stays as the top-level design document. Epics
  reference sections of it.
- Existing phase-based LLDs are not retroactively renamed. New work uses the epic-based
  naming convention.

## Consequences

- New `epic` label on GitHub.
- CLAUDE.md updated with epic/task organisation section.
- `/architect` skill updated to accept epic issues and produce per-task LLDs.
- `/feature` skill updated to pick tasks within an epic context.
- `/feature-team` skill updated to validate epic membership when picking tasks.
- `/lld` skill updated to use `lld-<epic-slug>-<task-slug>.md` naming.
- Existing `lld-phase-*` files remain — no retroactive rename.

## Revision — 2026-11-15

**Status of this section:** amends the Decision above for projects whose tracker is Jira
([ADR-0041](0041-tracker-abstraction.md), [v3 HLD](../design/v3/v3-design.md)). On GitHub
the original Decision stands unchanged. Where the two conflict on a Jira project, this section
governs.

The epic/task model, the one-LLD-per-task rule and the LLD naming are unchanged. What differs
is how the tracker represents the hierarchy:

| | GitHub (unchanged) | Jira |
|---|---|---|
| Epic | Issue with `epic` label | Native Epic issue type |
| Task → epic link | Epic body checklist; task body references the epic | Task's `parent` field |
| Epic progress | Read from checklist ticks | Rolled up from child task statuses (`done of total`) |
| Task completion | `/feature-end` ticks the epic checkbox | `/feature-end` moves the task to Done; epic body untouched |
| Epic closure | Manual | Manual |

- **"No automated rollup" no longer holds on Jira.** Progress is computed from child statuses
  (Story 2.1), because Jira holds the hierarchy natively and a body checklist would duplicate
  it and drift.
- **The epic body stays a container description on Jira.** It keeps scope, success criteria
  and REQ- anchors (ADR-0026); `/architect` does not write a task checklist into it.
- **Skills never branch on this.** Both representations sit behind the tracker script
  (ADR-0041): `create --type epic`, `create --parent`, `view` (`parent`, `children`) and
  `close` behave the same way from the caller's side.

