# 0034. Design Review Gates

**Date:** 2026-05-18
**Status:** Proposed
**Deciders:** LS / Claude

## Context

The pipeline produces design artifacts at three stages:

```
/discovery → /requirements → /kickoff → /architect → /feature
                 req doc        HLD/ADRs      LLDs        code
```

Each stage feeds the next. A weak requirements doc produces a thin HLD.
A thin HLD produces incomplete LLDs. An incomplete LLD reaches `/feature`,
and the implementing agent either guesses (producing drift fixed later by
`/lld-sync`) or blocks (wasting a cycle). The cost of fixing a missing
acceptance criterion at implementation time is roughly 10× what it would
cost at requirements time.

Today, the only quality checks on design artifacts are:

| Check | Runs in | Limitation |
|-------|---------|------------|
| Self-critique pass | `/lld` Step 2.5 | Same model reviewing its own output — low signal |
| Drift scans | `/kickoff` Gates 1 & 2 | Coverage matrix only — checks whether requirements map to components, not whether the mapping is correct |
| `/architect review` | On-demand (`/architect review <N>`) | Not a pipeline gate — human must remember to invoke it |
| `[Review]` markers | `/requirements` | Human-only — no automated assist to spot gaps before the human reads |

Code review has `/pr-review` (launched in `/feature-core` Step 9) — independent
agents with structured checklists, severity-graded findings, blocking on serious
issues. Design artifacts have no equivalent.

The gap is not theoretical. ADR-0033 documented four refactors (#498, #499, #500,
#503) where LLD-level smells — an adapter that existed only because of a contract
mismatch, bespoke DB query scaffolding copied across files — slipped through design
review and compounded across tasks before surfacing at implementation time. A
Boundary Contract Audit at LLD time would have caught them. The audit is one
check; this ADR establishes the general mechanism for adding such checks at every
design stage.

## Decision

Add an **automated review gate before each human gate** in the design pipeline.
Each review is performed by an independent sub-agent with an artifact-specific
checklist. The review report informs the human gate — blockers must be fixed
before the artifact proceeds downstream.

### Pattern

```
Artifact draft → Review agent (independent context) → Findings (block/warn) → Fix blockers → Human gate (review report visible)
```

The pattern is consistent across all three artifact stages. What varies is the
checklist.

Key differences from `/pr-review`:

- Reviews **specifications**, not implementations.
- Checks **forward-completeness** — will the next pipeline stage have what it
  needs to proceed without guessing?
- Checks **cross-artifact traceability** — req→hld→lld chain integrity.
- Runs **before the artifact is finalised**, not after implementation.
- Feeds into a **human gate** — the review informs the human's decision, it does
  not replace it.

### 1. Requirements Review — before Gates 1 & 2 in `/requirements`

**Agent:** `edf:requirements-review`

**Before Gate 1 (structure):**
- INVEST compliance on every story (Independent, Negotiable, Valuable,
  Estimable, Small, Testable). Flag violations with suggested fixes.
- REQ- anchor presence — every story has a stable anchor per ADR-0026.
- Cross-reference completeness — every discovery feature or input requirement
  maps to at least one story or is explicitly deferred.
- Internal consistency — no duplicate stories, no contradictory scope
  statements, priority ordering is defensible.

**Before Gate 2 (complete):**
- All of the above, re-checked after ACs are written.
- AC testability — vague qualifiers ("appropriate", "fast", "user-friendly")
  flagged; missing negative cases called out.
- AC specificity — every AC states a concrete, observable outcome with clear
  pass/fail conditions.

The review report is presented alongside the gate summary. The human can
override warnings but not skip blockers.

### 2. HLD Review — after Step 2 in `/kickoff`, before Gate 1

**Agent:** `edf:hld-review`

- Capability-to-component traceability — every capability has at least one
  owning component. Flag uncovered capabilities.
- Component boundary completeness — every component has non-responsibilities
  defined. Flag components with only responsibilities listed.
- Interaction coverage — sequence diagrams cover the primary happy path and at
  least one error path per trust boundary.
- Trust boundary explicitness — components that cross trust boundaries state
  the boundary explicitly in their description.
- ADR trigger detection — load-bearing decisions that lack an ADR are flagged
  for the human to decide (escalate to ADR or note as deferred).
- Delta-mode reference resolution — every `See [prior HLD §anchor]` reference
  resolves to a real anchor in the prior HLD file.
- Technology-free component naming — no component is named after a technology
  (e.g. "PostgresStore" → should be "DataStore").

This fills the gap between the current coverage-only drift scan and a quality
review. The drift scan checks that requirements *map* to capabilities; the HLD
review checks that the mapping is *sound*.

### 3. LLD Review — after `/lld` Step 2.5, before task breakdown (Step 3)

**Agent:** `edf:lld-review`

This is the highest-leverage review because LLDs directly drive `/feature`
agent behaviour. Launched after the self-critique pass as an independent
second pair of eyes.

- **Contract completeness** — every non-trivial function or component has a
  named signature. "Service does X" prose without a concrete function name is
  a blocker.
- **BDD ↔ AC coverage** — every acceptance criterion maps to at least one BDD
  spec. Flag gaps.
- **Invariant verifiability** — every invariant has an executable verification
  method (test, type check, grep, lint rule). "Code review" or "manual check"
  is not a verification method — flag as blocker.
- **Helper reuse compliance** — no re-implementation of existing helpers from
  `kb/architecture.md`. The "Reused helpers — DO NOT re-implement" table is
  present when the LLD touches topics covered by the kb.
- **File path resolution** — all referenced source files exist in the repo
  (or are explicitly noted as to-be-created). Broken paths are blockers.
- **Task sizing** — no task exceeds an estimated ~200 lines of diff. Oversized
  tasks flagged for splitting.
- **Layer placement** — primary enforcement layer is explicit for each
  behaviour. DB constraints in DB layer, API guards in BE, UI validation in
  FE. Defence-in-depth is acceptable but the primary layer must be stated.
- **Error paths** — at least one BDD spec per non-trivial error case. Happy-
  path-only LLDs are flagged.
- **Boundary Contract Audit** — per ADR-0033, when an LLD section claims
  "shared X reused unchanged", the audit table is present and each row has a
  non-empty Impedance column.

The self-critique pass (same model) remains as a first pass — it catches
obvious omissions cheaply. The review agent (independent context) catches what
self-critique cannot: blind spots the model doesn't know it has.

### Integration summary

| Stage | Review runs | Blocks on | Human sees |
|-------|------------|-----------|------------|
| `/requirements` Step 3 | Before Gate 1 | INVEST failures, missing anchors | Review report + structure summary |
| `/requirements` Step 5 | Before Gate 2 | Untestable ACs, missing negative cases | Review report + full document |
| `/kickoff` Step 3 | After HLD draft, before Gate 1 | Uncovered capabilities, broken references, missing non-responsibilities | Review report + drift matrix |
| `/lld` Step 2.5 | After self-critique, before Step 3 | Thin contracts, missing BDD, oversized tasks, unverifiable invariants | Review report + task breakdown |

### What stays the same

- **Human gates remain.** The review informs the human's decision; it does not
  replace it. Warnings can be overridden; blockers require a fix or an explicit
  human waiver recorded in the artifact.
- **Drift scans in `/kickoff` remain.** They check coverage (does every
  requirement map to a component?); the HLD review checks quality (is the
  mapping sound?). The two are complementary.
- **`/architect review` remains** as an on-demand deep-dive for issues that
  need more scrutiny than the automated LLD review gate provides.
- **`/pr-review` is unchanged.** It reviews code; these gates review design.
- **`/lld-sync` is unchanged.** It reconciles implementation learnings back
  into LLDs post-merge. Design review gates catch gaps before implementation;
  `/lld-sync` catches gaps discovered during implementation.

### Agent design

Each review agent:
- Is launched as a sub-agent (separate context = independent judgment).
- Receives the artifact, its checklist, and the upstream artifacts needed for
  cross-reference.
- Returns structured findings — same severity model as `/pr-review` (`block`
  | `warn`, with file/line/section references).
- Does not edit the artifact — findings are reported; the parent skill applies
  fixes and re-runs the review if blockers were found.

## Consequences

- Each design artifact gets an independent quality check before it is consumed
  by the next pipeline stage. The same principle that `/pr-review` applies to
  code now applies to specifications.
- Blocker findings at requirements time prevent under-specified stories from
  reaching `/architect`. Blocker findings at LLD time prevent thin contracts
  from reaching `/feature`.
- Three additional agent spawns per full pipeline run (one per stage). At
  ~2–5K input tokens and ~500–1500 output tokens each, the total review cost
  is roughly one `/pr-review` run. The return is in prevented implementation
  rework — a single bad `/feature` cycle costs ~100K+ tokens.
- The self-critique pass in `/lld` is no longer the only quality check on
  LLDs — it is now the first of two, with the review agent providing an
  independent second opinion.
- Review checklists are version-controlled in the skill definitions, not in
  the agents themselves. Adding a new check (e.g. a project-specific
  anti-pattern discovered during retro) means updating the skill's checklist,
  not rewriting the agent.
- Human gates remain the final authority. The review agent is an advisor, not
  a gatekeeper — it surfaces issues; the human decides.

## Alternatives considered

- **Add review checks to the existing self-critique pass instead of a separate
  agent.** Rejected — same-model review is the core limitation. An independent
  agent context catches blind spots the authoring model misses.
- **A single `/design-review` skill invoked manually.** Rejected — relies on
  the human remembering to invoke it. Embedding review at each pipeline stage
  makes it automatic and unavoidable, like `/pr-review` in `/feature-core`.
- **Review agents that auto-fix issues rather than reporting them.** Rejected —
  auto-fixing design artifacts without human review risks compounding errors.
  The agent suggests; the human (or parent skill with human approval) fixes.
- **Skip HLD review and rely on the LLD review to catch everything.** Rejected —
  HLD-level issues (missing non-responsibilities, unstated trust boundaries)
  are cheaper to fix before LLDs are written against a flawed HLD.
