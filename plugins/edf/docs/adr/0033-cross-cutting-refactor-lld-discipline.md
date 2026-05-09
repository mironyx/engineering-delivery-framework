# 0033. Cross-Cutting Refactor LLD Discipline

**Date:** 2026-05-07
**Status:** Proposed
**Deciders:** LS / Claude

## Context

[ADR-0030](0030-lld-revisions-via-architect-addendum-and-lld-sync-reconciliation.md)
established how requirements changes are absorbed into LLDs (`/architect`
appends a `## Pending changes — Rev N` block; `/lld-sync` reconciles after
merge). It assumes the unit of change is one feature task → one LLD section.

It does not cover **cross-cutting refactors** — work whose primary goal is
structural change touching multiple LLD sections, or multiple LLDs, or
multiple source files with no shared LLD owner.

V12 Epic E12.2 surfaced four such refactors in a row (#498, #499, #500,
#503), all driven by smells that compounded across tasks T2.1–T2.9:

- `scoreAllAnswers` adapter (`scoring-path.ts`) — exists only because the
  engine takes array indices and PRCC has UUIDs. Introduced silently in T2.5.
- DB query patterns scattered across three PRCC files with bespoke
  `makeMockDb` scaffolding per file. No repository layer.
- `triggerPrccRubricGeneration` is a structural twin of `triggerRubricGeneration`,
  introduced as a copy in T2.2 instead of generalising the original.

Implementation of T2.8 (#475) was stopped because designing the debounce/regen
path on this foundation would calcify all three smells. The four refactors
need to land before T2.8 resumes.

Two gaps this exposed:

1. **No defined process** for refactor work. A refactor isn't a feature task;
   it isn't a requirements revision. The existing skills (`/architect`,
   `/feature`, `/lld-sync`) don't have a clean entry point for it.
2. **No mechanism to catch the smells earlier.** The three Epic 2 smells were
   each authored at LLD time and slipped through review. Implementation
   surfaced them only after the next task built on top.

## Decision

The decision separates two concerns ADR-0033's first draft conflated:

- **Triggers** — how a refactor need is detected (smells, audit findings,
  manual spotting). Detection is agnostic to source.
- **Process** — what happens once a refactor is detected (issue creation,
  scope-based decomposition, LLD sweep, reconciliation).

This mirrors ADR-0030's structure (delta detection separate from Rev X
format separate from skill obligations).

### The refactor lifecycle

Once a refactor need is detected:

1. The detecting skill (or human) **surfaces the finding** — smell
   description, audit details, affected files — and stops. Skills do not
   auto-invoke other skills; the human is the router.
2. The human invokes **`/refactor-architect`** — a forthcoming skill that
   mirrors `/architect` for refactor work — passing the finding as input.
3. `/refactor-architect` assesses scope and produces either one issue
   (small refactor) or one epic + N task issues (large refactor), analogous
   to how `/architect` decomposes a feature epic. The human reviews the
   proposed decomposition before issues are created, exactly as with
   `/architect`.
4. The human runs `/feature` to implement each issue. Each implementing PR
   sweeps the LLD sections it invalidates.
5. `/lld-sync` reconciles each affected LLD after merge.

Steps 1–5 are independent of *what triggered* the lifecycle. Each
transition is a human decision — this matches how feature work flows today
(`/architect` → `/feature` → `/feature-end` → `/lld-sync`, each invoked
separately).

### Triggers — when the lifecycle starts

The lifecycle is initiated by any of these signals:

- **Smell 1 — pure-translation helper.** A new helper whose only job is to
  convert between two shapes (array index ↔ UUID, near-identical types, one
  DTO to another). No domain logic; it exists only because the shared
  code's contract is the wrong shape for this consumer.
- **Smell 2 — pattern already lives elsewhere.** The DB query, fetch
  sequence, or conversion you're about to write already exists in one or
  more sibling files — you'd be writing the next copy.
- **Smell 3 — Boundary Contract Audit finding.** `/lld` runs a Boundary
  Contract Audit when an LLD section claims "shared X reused unchanged"
  (format below). If the audit names an impedance requiring generalisation
  of the shared component, the LLD does not ship — the finding triggers the
  lifecycle.
- **Manual.** A human spots a smell or tech debt while reading code and
  invokes `/refactor-architect` directly.

Line counts and similar numerics are not triggers — *shape* is. A 5-line
transform doing real domain work is fine. A 30-line module translating
shapes between mismatched contracts is the smell, regardless of length.

If uncertain whether what you're seeing is a smell, surface it to the human
rather than guessing. The skills do not have to enforce these alone.

### Process — what `/refactor-architect` produces

Mirrors `/architect`'s decomposition logic, applied to refactor work
instead of feature work.

**Scope assessment.** The skill identifies which LLD sections the refactor
will invalidate — by inspecting referenced source files, kernel docs, and
existing reused-helpers tables in the affected LLDs.

**Decomposition guideline (not a rigid rule).**

Default to **one issue** (`kind:task`). The implementing PR sweeps every
affected LLD inline. This is the right answer for the vast majority of
refactors.

Escalate to **one epic + N task issues** only when judgement warrants —
not by mechanical count.

| Output | When | Labels |
|--------|------|--------|
| One issue | Default. Refactor fits in a single reviewable PR (rough guide: < ~300 lines diff including LLD edits). | `kind:task` |
| Epic + N tasks | Refactor would produce an unwieldy PR, **or** has natural seams between consumers each independently shippable. | Epic: `epic` + `kind:lld-sweep`. Tasks: `kind:task`. |

The primary signal is **estimated PR diff size**, not a count threshold.
LLD count and source-file count are useful proxies; refactors touching
many LLDs (e.g. > 5) often (but not always) cross the size threshold.
Judge each case rather than applying a count mechanically — most
refactors here touch 3–4 LLDs and remain one issue.

When escalated: each task PR sweeps its own LLD sections. The epic must
close before any new feature work starts on the refactored area.

**Issue body.** Every issue produced has:
- `## Design references` listing the LLD sections it sweeps (anchor form).
- `## Boundary Contract Audit` table where applicable.
- `## Acceptance criteria` including the LLD-sweep checklist (every
  Design-references section is updated in the same PR).

### LLD update mechanics (per affected section)

For each LLD section a refactor PR sweeps:

- **Mechanical change** (rename, file path, import) → edit the LLD body
  directly. No Rev N block.
- **Behavioural or contract change** → append a `## Pending changes —
  Rev N` block per [ADR-0030](0030-lld-revisions-via-architect-addendum-and-lld-sync-reconciliation.md).
  `/lld-sync` removes the block on merge and reconciles the body.

ADR-0033 reuses ADR-0030's Rev N mechanism unchanged; it only extends the
mechanism's applicability from requirements-driven revisions to
refactor-driven ones.

### Boundary Contract Audit format

When an LLD section introduces a new consumer of a shared component, Part
B includes a Boundary Contract Audit subsection in this form:

| Shared component | Source | Contract used | Impedance? |
|------------------|--------|---------------|-----------|
| `<name>` | `<path>` | `<signature copied from source>` | None / Adapter ≤ 10 lines (with rationale documented inline) / Generalise first (link to filed refactor issue #N) |

The "Generalise first" outcome is a Smell 3 trigger — `/lld` surfaces the
audit and stops; the human invokes `/refactor-architect` to file the
prerequisite refactor issue before this LLD ships. The audit row links to
the filed issue once it exists.

The Epic 2 LLD said "engine reused unchanged" for §B.5 (T2.5) without
auditing `ParticipantAnswer.questionIndex` against PRCC's UUID model. A
five-line table at LLD time would have produced #500 as a precondition,
not a post-hoc refactor.

### Skill obligations

| Skill | Obligation |
|-------|-----------|
| `/refactor-architect` (new) | Invoked by the human with a smell description or audit finding as input. Produces issue or epic+tasks; populates Design references and Boundary Contract Audit. Decomposition mirrors `/architect`. |
| `/lld` (modified) | Runs Boundary Contract Audit on any section claiming "shared X reused unchanged". On Smell 3 finding, surfaces the audit detail and **stops the LLD pass**. The human decides whether to ship the LLD with an adapter justification or to invoke `/refactor-architect` first. |
| `/feature-core` (modified) | When Smell 1 or Smell 2 is detected during implementation, **stops feature work and surfaces the finding** (smell type, affected files, recommended next step). Does not invoke other skills. The human decides: continue with a justified workaround, or invoke `/refactor-architect` and re-run `/feature-core` after the refactor merges. |
| `/lld-sync` (modified) | Reads `## Design references` from the merged issue body to know exactly which sections to reconcile. Removes shipped Rev N blocks (existing). |
| `/feature-end` (modified) | Post-merge LLD-reference scan — greps `lld-*.md` for stale references to source files the PR moved, renamed, or deleted. Reports stale references to the human. |
| `/bug` (modified) | When investigation reveals the root cause is structural (not a single-file fix), **surfaces this to the human** and recommends invoking `/refactor-architect` rather than continuing to author a single-file bug-fix issue. Does not auto-route. |

In every case, the skill detecting the issue surfaces it and stops. The
human decides what runs next; skills do not invoke other skills.

These are clarifications and additions to existing skill responsibilities.
Implementation tracked in
[docs/plans/2026-05-07-skill-updates-from-adr-0033.md](../plans/2026-05-07-skill-updates-from-adr-0033.md).

## Consequences

- The refactor lifecycle has a single entry point (`/refactor-architect`)
  regardless of who detected the smell — agent, human, or audit. This
  removes the ad-hoc "create a refactor issue somehow" pattern that
  produced #498/#500/#503 with inconsistent shape.
- Refactor PRs that touch ≤ 5 LLDs become slightly larger (LLD edits inline)
  but remain reviewable as a single change.
- The Boundary Contract Audit adds a section to LLDs that introduce new
  consumers — small upfront cost; saves whole post-hoc refactors when it
  catches an impedance.
- Smell-driven refactor-first creates short-term feature delays at the
  moment a smell is hit. Net cost is lower than the four-refactor cleanup
  pattern Epic 2 produced.
- Tooling deferred: the skill changes (especially `/refactor-architect`)
  do not exist yet. Until they ship, humans run the lifecycle manually —
  spot smell, file refactor issue, sweep LLDs in the PR. Implementation
  is tracked in the skill-updates plan.

## Relationship to ADR-0030

ADR-0030 covered **requirements-driven** LLD changes: when requirements
revise, `/architect` produces a `## Pending changes — Rev N` block,
`/lld-sync` reconciles after merge.

ADR-0033 covers **refactor-driven** LLD changes:

- Same Rev N mechanism for behavioural changes (no new artefact format).
- New entry-point skill (`/refactor-architect`) for the refactor lifecycle —
  parallel to `/architect` for the feature lifecycle.
- New Boundary Contract Audit format, owned by `/lld` and required when an
  LLD introduces a new consumer of a shared component.

ADR-0030's authorship boundary (`/architect` writes Rev N; `/lld-sync`
reconciles) carries through unchanged. ADR-0033 only adds an additional
producer of Rev N intent (`/refactor-architect` for refactor work).

## Alternatives considered

- **Treat refactors as ad-hoc tasks created by `/architect` or hand-rolled.**
  Status quo before this ADR. Rejected — produced the inconsistent issue
  shape across #498/#500/#503 that motivated the work.
- **Skip the new `/refactor-architect` skill; embed the rules in
  `/architect`.** Rejected — `/architect` is feature-driven (epic →
  tasks); refactor-driven decomposition has different inputs (smell or
  audit finding instead of plan section) and different outputs (no LLD
  authored, only updated). Conflating them grows `/architect` without
  benefit.
- **Always tracking-issue-only for refactor LLD updates.** Rejected —
  invites debt. Each Epic 2 refactor would have produced a tracking issue
  competing with feature work for board time, even when one PR could
  sweep the LLDs cleanly.
- **Always sweep-in-PR regardless of size.** Rejected — refactor PRs
  touching 10+ LLDs become unreviewable when LLD updates are bundled in.
- **Lint rule for adapter size or duplicate DB queries.** Possible future
  enhancement. The discipline is procedural first; lint can enforce a
  subset later.
