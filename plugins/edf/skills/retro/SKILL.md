---
name: retro
description: Run a process retrospective. Reviews recent sessions, git history, issue board state, and drift reports to identify what's working, what isn't, and what to change. Use at the end of a project phase, after 3-5 sessions of active work, or before starting multi-agent parallel work. Produces a report in docs/reports/.
allowed-tools: Read, Write, Bash, Glob, Grep
---

# Process Retrospective

Analyses the development process since the last retro (or project start) and produces a process improvement report.

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing data sources, health dimensions, or the report structure.

## Instructions

### 1. Gather data

- **Session logs** — Read all files in `docs/sessions/` since the last retro (search recursively — sessions are organised in `YYYY-MM/` monthly folders per ADR-0036). These capture completed work, decisions, and conversation summaries.
- **Git history** — Run `git log --oneline` to see commit frequency, message quality, and whether atomic commits per task are happening.
- **GitHub Issues** — Run `gh issue list --state all --json number,title,state,labels` to assess backlog health.
- **Project board** — Run `PROJECT_NUMBER=$(grep '^PROJECT_NUMBER=' .github/project.env | cut -d= -f2) && OWNER=$(grep '^REPO=' .github/project.env | cut -d= -f2 | cut -d/ -f1) && gh project item-list $PROJECT_NUMBER --owner $OWNER` to check priority ordering and status accuracy.
- **Drift reports** — Read any drift reports in `docs/reports/drift/` generated since the last retro. Note whether any design↔code drift findings (Critical/Warning) were raised and whether they were resolved within the same or next session.
- **kb/ coverage** — Compare new source files added since the last retro (`git log --oneline --since="<last retro date>" -- 'src/'`) against kb/architecture.md sections. Are there shared artifacts (helpers, components, tokens) added without kb/ entries? List them.
- **Previous retro** — Read the most recent `docs/reports/retro/YYYY-MM-DD-process-retro.md` if one exists, to check whether previous actions were implemented.

### 2. Assess process health

Evaluate against these dimensions:

| Dimension | What to look for |
|-----------|-----------------|
| **Backlog hygiene** | Issues labelled? Priority ordered? Dependencies explicit? |
| **Definition of done** | All DoD items ticked? Cross-references and drift checks happening? |
| **Commit discipline** | One commit per task? Conventional messages with issue refs? Untracked files? |
| **Session continuity** | Session logs written? All sections present? Next session orient quickly? |
| **Drift management** | Drift scan run at session end? Critical items resolved within one session? |
| **kb/ coverage** | New shared artifacts (helpers, components, tokens) registered in kb/architecture.md? Catalogue truthful? |
| **Multi-agent readiness** | Tasks scoped to single files? Cross-ref updates deferred? Second agent pick up `ready` issue independently? |

### 3. Write the report

Save to `docs/reports/retro/YYYY-MM-DD-process-retro.md` using this structure:

```markdown
# Process Retrospective

**Date:** YYYY-MM-DD
**Period:** [date of last retro or project start] to today
**Sessions reviewed:** [list session numbers/dates]

## What went well

- [Things that worked — keep doing these]

## What needs improving

- [Problems observed, with evidence from the data gathered]

## Actions from previous retro

| Action | Status | Notes |
|--------|--------|-------|
| [action from last retro] | Done / Partial / Not started | [what happened] |

## New actions

| # | Action | Addresses |
|---|--------|-----------|
| 1 | [concrete action] | [which problem] |

## Process health scorecard

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Backlog hygiene | Green / Amber / Red | [brief explanation] |
| Definition of done | Green / Amber / Red | |
| Commit discipline | Green / Amber / Red | |
| Session continuity | Green / Amber / Red | |
| Drift management | Green / Amber / Red | |
| Multi-agent readiness | Green / Amber / Red | |
```

### 4. Run drift scan

After writing the retro report, run `edf:drift-scan` to produce a fresh drift report. Reference
the drift findings in the retro report's "What needs improving" section if any Critical or
Warning items are found. This replaces the previous practice of carrying "run drift scan" as
a retro action.

### 5. Execute quick-win actions in-session

Any retro action that takes <5 minutes (e.g., move issues on board, update a status field,
add a CLAUDE.md line) should be executed during the retro session itself, not carried as
future work. Update the actions table to show them as **Done**.

### 6. Summarise

Present:
- The health scorecard
- Top 3 actions to take (max 3 — if it doesn't make the cut, do it now or drop it)
- Comparison with previous retro (if one exists)
- The file path to the full report
