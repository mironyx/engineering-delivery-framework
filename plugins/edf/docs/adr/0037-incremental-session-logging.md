# 0037. Incremental Session Logging with Feature-ID Filename

**Date:** 2026-06-04
**Status:** Proposed
**Deciders:** LS / Claude

## Context

Session logs are written post-hoc by `/feature-end` (Step 2), well after the
feature's implementation is complete. By that point, context has often been
compacted multiple times. Details that are expensive or impossible to
reconstruct from git log alone — the reasoning behind an approach choice, why
an LLD prescription was deviated from, the number of red→green fix cycles —
are lost.

Separately, cost retrospectives (Step 2.6) currently estimate per-phase cost
from git log and commit patterns. Without checkpoints, there is no way to
decompose "why did this feature cost 2x the estimate?" into answers like
"58% of tokens went into the Step 4cF fix loop." The per-session Prometheus
data is one aggregate bucket; the cost retro needs phase-level granularity.

Finally, session logs use a filename convention (`YYYY-MM-DD-session-N-<slug>.md`)
without any stable feature identifier. Grepping for an issue number finds
partial matches; a feature ID is precise and stable across the lifecycle.

## Decision

### Feature ID in session log filenames

Session logs for feature implementation include the feature ID derived from
`$EDF_FEATURE_PREFIX-<issue-number>` (the same derivation used by
`tag-session.py` and `create-feature-pr.sh`):

```
docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md
```

Example: `2026-06-04-session-3-add-auth-middleware-FCS-730.md`

The feature ID is computed inline from `$EDF_FEATURE_PREFIX-<issue-number>`.
The prefix is read from `$env:EDF_FEATURE_PREFIX` and falls back to `.env`.

### File created early, appended incrementally (Full track only)

`/feature-core` creates the session log at Step 3dF (immediately after
pressure classification), writes the approach rationale and a cost checkpoint
table header, then appends a cost row after each major phase boundary.
`/feature-end` appends the remaining sections (narrative summary, LLD sync
report, cost retrospective) and closes the file. There is no rename — the file
is the session log from creation.

**Light track:** exempt. Bug fixes under 30 lines skip this entirely —
`/feature-end` writes the log in one shot as it does today (with the feature
ID added to the filename).

**Note on naming:** the `-draft` suffix is reserved for the compaction hook's
pre-compaction snapshot. This ADR does not use it — the file is the live
session log from the moment `/feature-core` creates it.

### File format

Created by `/feature-core` Step 3dF:

```markdown
# Session log — [FEATURE_ID]

## Approach rationale
- **Issue:** #<N>
- **Approach chosen:** <1-2 sentences>
- **LLD deviations:** <what changed and why, or "none">
- **Pressure:** <light | standard | heavy> — <reasoning>

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c   | 14:22:15  | $0.42              | 12,400               | pressure: heavy |
```

### Cost checkpoint append points

`/feature-core` appends a single table row after each phase boundary. No
narrative — just the data row. The gaps between rows are the cost buckets
the cost retro analyzes.

| After step | Label | Meaning |
|------------|-------|---------|
| 5 (first green) | `green on attempt N` | Captures implementation friction — every re-run between 3c and green costs tokens |
| 8 (PR created) | `PR <url>` | Pre-review total — what the feature cost to build |
| 9 (review resolved) | `review clean` | Post-review rework — what fixing review findings added |

Token and cost values are queried from Prometheus via the session IDs already
registered by `tag-session.py`. If the query fails, note `unavailable` — don't
block the pipeline on a cost metric.

### `/feature-end` Step 2 reads and completes

Step 2 finds the session log by feature ID:

```
ls docs/sessions/YYYY-MM/*-<FEATURE_ID>.md
```

If found: read it, append the remaining sections (work completed, decisions,
LLD sync report, cost retrospective). If not found (Light track, or crash
recovery where the file wasn't created): write the full log in one shot with
the feature ID in the filename, matching today's behaviour.

### Cost retrospective reads the checkpoint table

Step 2.6 reads the `## Cost checkpoints` table. Instead of reconstructing
phase costs from git log guesses, it can state:

> "Step 4cF→5 consumed 58% of tokens (green on attempt 3). Step 9 review fixes
> added 12%."

This is data-backed decomposing, enabled by the incremental checkpoints.

### Contract between skills

| Skill | Obligation |
|-------|-----------|
| `/feature-core` | Full track: create log at Step 3dF with rationale + cost table header; append cost row at Steps 5, 8, 9 |
| `/feature-end` | Step 2: find log by feature ID, append remaining sections; if not found, write one-shot |
| `/feature-end` | Step 2.6: read checkpoint table for cost retro |

No new scripts. The file is a standard session log written by two skills in
sequence. Feature ID is computed inline; cost values are read from Prometheus.

## Consequences

- **Approach rationale is never lost to compaction.** Written immediately
  after Step 3c, before any sub-agent or verification work.
- **Cost retros become data-backed.** Phase-level decomposition replaces
  git-log guesswork.
- **Feature-ID in filenames makes logs precisely grepable.** No false matches
  from issue numbers appearing in unrelated prose.
- **Light track unaffected.** Bug fixes skip the incremental mechanism entirely.
- **Operational risk:** if a Full-track feature gets compacted between creating
  the file and the first checkpoint append, later checkpoints are missing.
  Mitigation: the cost retro treats gaps as "unknown — lost to compaction" rather
  than fabricating numbers.
- **Crash recovery (Step 1 / `--cont` in feature-end):** the feature ID is
  stable across sessions — the recovery session can find and continue the log,
  appending new checkpoints under the same feature ID.

## Relationship to existing ADRs

- **ADR-0022** (tiered feature process): this ADR scopes incremental logging
  to Standard and Heavy tiers only, matching the existing pressure-tiered model.
- **ADR-0026** (stable IDs): feature ID (`FCS-730`) extends the ID philosophy
  to session log filenames.
- **ADR-0036** (document organisation): session logs remain in
  `docs/sessions/YYYY-MM/` per the month-foldered convention.
  `-<FEATURE_ID>` is appended to the existing filename pattern, not a new
  directory.
