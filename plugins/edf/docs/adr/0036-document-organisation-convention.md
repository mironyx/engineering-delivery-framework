# 0036. Document Organisation Convention

**Date:** 2026-05-20
**Status:** Proposed
**Deciders:** LS / Claude

## Context

The pipeline produces documents across three directories:

```
docs/
  design/     # HLDs, LLDs, coverage manifests, visuals
  requirements/  # Structured requirements per version
  sessions/   # Session logs
```

Currently all three are flat — every document at the root of its directory.
At 60+ design files, 80+ session logs, and growing, browsing and scanning
become friction. The problem compounds because design mixes multiple artifact
types (HLDs, LLDs, spikes, coverage manifests, visuals) in one flat space.

## Decision

### Design: grouped by version

```
docs/design/
  kernel.md                         # Cross-cutting design docs stay at root
  frontend-system.md                #   (version-independent, few in number)
  v1/
    v1-design.md
  v11/
    v11-design.md
    lld-v11-e11-1-project-management.md
    lld-v11-e11-2-fcs-scoped-to-projects.md
    lld-v11-e11-3-project-context-config.md
    lld-v11-e11-4-navigation-routing.md
    coverage-v11-e11-1.yaml
    coverage-v11-e11-2.yaml
    coverage-v11-e11-3.yaml
    coverage-v11-e11-4.yaml
  v18/
    v18-design.md
    lld-v18-e1-gcp-foundations.md
    lld-v18-e2-prod-external-services.md
    vis-v18-answer-page-skipped.html
    vis-v18-assessment-detail.png
    coverage-v18-e1.yaml
    coverage-v18-e2.yaml
```

- Each version gets a `v{N}/` folder containing all design artifacts for that version.
- Visual specs use the `vis-` prefix (matching the `lld-` convention) and live
  inside the version folder — no separate `visuals/` subfolder.
- Cross-cutting, version-independent documents stay at the `design/` root.
  These should be rare; if a root document grows version-specific sections, it
  belongs in a version folder.

### Requirements: left flat

```
docs/requirements/
  v1-requirements.md
  v2-requirements.md
  ...
  v19-requirements.md
```

Requirements documents are one file per version with no associated artifacts
(amendments are appended to the same file). A flat directory with a consistent
`v{N}-` prefix stays scannable. No change needed.

### Sessions: grouped by month

```
docs/sessions/
  2026-03/
    03-session-1.md
    04-session-2.md
    ...
  2026-04/
    01-session-1-frontend-deps.md
    ...
```

Sessions are chronological. Monthly folders keep each folder to ~20-30 files
and match how sessions are browsed ("what happened in March?"). Day-level
folders would be too granular (most days have 1-2 sessions).

### Migration rule

| Directory | Existing files | New files |
|-----------|---------------|-----------|
| `design/` | Stay where they are | Go into `v{N}/` folder |
| `requirements/` | Stay where they are (already fine) | Same |
| `sessions/` | Move into monthly folders | Same |

The reason existing design files stay put: source code contains hundreds of
`// Design reference: docs/design/lld-*.md` comments. Moving those files would
break every reference. New versions use the versioned path from the start, so
references are naturally correct.

Session logs have no outbound references from source code and can be moved
retroactively.

## Consequences

- **Design browsing improves immediately for new versions.** Opening
  `docs/design/v19/` shows every artifact for that version — HLD, LLDs,
  coverage, visuals — without noise from other versions.
- **Flat requirements stay simple.** No restructuring overhead for a directory
  that doesn't need it.
- **Session discovery improves.** Monthly grouping matches how sessions are
  browsed chronologically.
- **Source code references don't break.** Old LLDs stay at their current paths.
  References drift over ~6 months as old versions become less relevant.
- **Skill output paths change.** The `requirements`, `kickoff`, and `lld` skills
  need one-line path updates to write into `v{N}/` for new versions. The
  version number is already a parameter these skills receive.
- **Framework ADR numbering.** This ADR claims 0036 for the EDF framework.
  Consuming projects should skip 0036 for project-local ADRs.
