---
name: feature
description: Autonomously implement the next feature from the project board. Picks the top Todo item, creates a branch, implements with TDD, runs diagnostics, commits, creates a PR, runs edf:pr-review and fixes any findings, then reports. Only pauses for real blockers.
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

- If `$ARGUMENTS` starts with `epic <N>`: read epic issue #N with `gh issue view <N>`. Parse the task checklist from the body. Pick the first unchecked task issue number. If all tasks are checked or no tasks exist, stop: "Epic #N has no remaining tasks."
- If `$ARGUMENTS` contains an issue number (not prefixed with `epic`): use that issue directly.
- If no arguments: run `gh issue list --label kind:task --state open --limit 1` and use the first result.

**Guard:** Check whether the selected issue has the `epic` label (`gh issue view <number> --json labels`). If it does, stop: "Issue #N is an epic. Use `/feature epic <N>` to pick a task within it, or `/feature <task-number>` for a specific task."

**Validate the issue has enough context:**

1. Read the issue body: `gh issue view <number>`.
2. Check for:
   - Design doc or LLD section reference
   - BDD test specs or acceptance criteria
   - If missing, stop and report: "Issue #N lacks [missing item]. Cannot proceed autonomously."

Once the issue number is known, tag the session so it is identifiable in the IDE and in Grafana:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/tag-session.py <issue-number>
```

### Step 2: Create feature branch

1. Derive a short slug from the issue title (e.g., issue #123 "Add scoring engine" → `scoring-engine`).
2. Fetch latest main and create the branch:
   ```bash
   git fetch origin main
   git checkout -b feat/<slug> origin/main
   ```
3. Move the issue to In Progress: `bash ${CLAUDE_PLUGIN_ROOT}/bin/gh-project-status.sh <number> "in progress"`.

### Step 3: Invoke feature-core

With the branch checked out and the board item In Progress, hand off to the core implementation cycle:

```
edf:feature-core <issue-number>
```

This covers: read design → TDD → full verification → diagnostics → commit → PR + CI probe → review → report.

## Blocker policy

**Pause and report** if:

- Issue not found on the board or has no kind:task label
- Issue lacks a design reference or acceptance criteria (caught in Step 1 validation)

For all other blockers (test failures, type errors, design mismatches, missing dependencies), see the blocker policy in `edf:feature-core`.
