---
name: feature
description: Autonomously implement the next feature from the project board. Picks the top Todo item, creates a branch, implements with TDD, runs diagnostics, commits, creates a PR, runs edf:pr-review and fixes any findings, then reports. Only pauses for real blockers. Never merges — ends at the report; the human reviews the PR and runs /feature-end.
allowed-tools: Read, Write, Edit, MultiEdit, Bash, Glob, Grep, Agent, Skill, TodoWrite
---

# Feature — Autonomous Implementation Cycle

Implements a single feature end-to-end without user intervention unless blocked.

**Usage:**

- `/feature` — picks the top Todo task from the project board
- `/feature 123` — works on task issue #123 specifically
- `/feature epic 45` — picks the next unchecked task from epic #45

**Pre-requisite:** The issue's design document (LLD, design doc section, or ADR) must be complete. If not, stop and tell the user. Epic issues (label `epic`) cannot be implemented directly — pick a task within the epic instead.

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing the pre-flight sequence, issue selection logic, or handoff to feature-core.

## Process

Execute these steps sequentially. Do not skip steps. Do not ask for confirmation between steps — only pause if a step fails after remediation attempts.

### Step 0: Pre-flight — ensure clean, up-to-date main

```bash
git checkout main && git pull origin main
```

Then verify the working tree is clean. `git checkout main` is a no-op success when
already on main with uncommitted changes, so the dirty state would otherwise be
inherited by the feature branch:

```bash
if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree has uncommitted changes on main. Stash or commit before /feature."
  git status --short
  exit 1
fi
```

If checkout fails due to uncommitted changes, or the porcelain check reports any
files, stop and tell the user.

### Step 1: Pick the work item and tag the session

**Determine the target issue:**

- If `$ARGUMENTS` starts with `epic <ref>`: run `bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/epic-progress.py <ref> --remaining` and pick the first ref printed. If it prints nothing, stop: "Epic <ref> has no remaining tasks."
- If `$ARGUMENTS` contains an issue ref (not prefixed with `epic`): use that ref directly. Refs are opaque (`#123`, `123`, `SCRUM-123`) — never build one by concatenation.
- If no arguments: run `bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/tracker.py list --status todo --label kind:task` and use the first ref in the result. If the list is empty, stop with `No Todo items` — before creating a branch.

**Guard:** Check whether the selected issue has the `epic` label (`bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/tracker.py view <ref>` → `labels`). If it does, stop: "Issue <ref> is an epic. Use `/feature epic <ref>` to pick a task within it, or `/feature <task-ref>` for a specific task."

**Validate the issue has enough context:**

1. Read the issue: `bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/tracker.py view <ref>` (JSON with `title`, `body`, `labels`, …).
2. Check for:
   - Design doc or LLD section reference
   - BDD test specs or acceptance criteria
   - If missing, stop and report: "Issue <ref> lacks [missing item]. Cannot proceed autonomously."

Once the issue number is known, tag the session so it is identifiable in the IDE and in Grafana:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/tag-session.py <ref>
```

### Step 2: Create feature branch

1. Derive a short slug from the issue title (e.g., "Add scoring engine" → `scoring-engine`).
2. Fetch latest main and create the branch:
   ```bash
   git fetch origin main
   git checkout -b feat/<slug> origin/main
   ```
3. Move the issue to In Progress: `bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/tracker.py status <ref> "in progress" --add-to-board`.

### Step 3: Invoke feature-core

With the branch checked out and the board item In Progress, hand off to the core implementation cycle:

```
edf:feature-core <ref>
```

This covers: read design → TDD → full verification → diagnostics → commit → PR + CI probe → review → report.

### Step 4: Stop — the PR awaits human review

`/feature` ends when feature-core's Step 10 report is delivered. **Do not invoke
`/feature-end`, merge the PR, close the issue, or pick up the next board item** — not even
when the review is clean and CI is green. The human reviews the PR and types `/feature-end`
themselves; that command is their merge approval (see `/feature-end` Step 0).

## Blocker policy

**Pause and report** if:

- Issue not found on the board or has no kind:task label
- Issue lacks a design reference or acceptance criteria (caught in Step 1 validation)

For all other blockers (test failures, type errors, design mismatches, missing dependencies), see the blocker policy in `edf:feature-core`.
