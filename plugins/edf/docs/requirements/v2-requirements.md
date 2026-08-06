# EDF Process Reliability — V2 Requirements

## Document Control

| Field | Value |
|-------|-------|
| Version | 0.1 |
| Status | Draft — Complete |
| Author | LS / Claude |
| Created | 2026-08-05 |
| Last updated | 2026-08-05 |

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-08-05 | LS / Claude | Initial draft — epics, stories, roles |
| 0.2 | 2026-08-05 | LS / Claude | Structure review fixes; added Implementation grouping note (ship as one item) |
| 0.3 | 2026-08-05 | LS / Claude | Acceptance criteria for all 7 stories; clarified solo-run in-place path in Story 1.1 |

---

## Context / Background

A review of ~20 session logs, 5 retrospectives, and drift reports in the `feature-comprehension-score`
project surfaced a consistent pattern: agents are not following instructions, and the process does not
guarantee the artefacts it claims to. The EDF plugin's skills declare mandatory steps ("MANDATORY — do not
skip") but nothing verifies they happened; parallel team runs corrupt shared design documents; retrospective
actions loop for months without moving; and problems discovered during implementation are mentioned in logs
and then lost.

This version hardens the delivery pipeline itself: design-sync becomes conflict-free in team runs, mandatory
steps get machine-checkable post-conditions, discovered problems become tracked issues, retro actions that
stall get filed, and sub-step skills stop ending silently mid-pipeline. Every change is to the plugin's own
skills, agents, and docs — the deliverable is process reliability, not a product feature.

The plugin's pipeline documents live under `plugins/edf/docs/` (per the repo CLAUDE.md). V1 requirements
(`v1-requirements.md`, Final) covered LLD diagram improvements and the review VSCode extension — a different
scope; nothing carries forward.

## Glossary

| Term | Definition |
|------|-----------|
| **Canonical LLD** | The main Low-Level Design document for an epic (`docs/design/v*/lld-*.md`) that teams read and reconcile against. |
| **Per-task sync file** | A temporary markdown file written by a teammate at `feature-end` in a worktree, recording the LLD delta for one issue, reconciled later by the lead. |
| **Post-condition gate** | A hard, machine-checkable check a skill must pass before proceeding (e.g. session log exists) — converts "mandatory" from assertion to verification. |
| **Retro carry** | An action from a previous retro still marked "Not started" in the current retro. Consecutive carries indicate the action is being re-flagged without moving. |
| **Sub-step skill** | A skill invoked mid-pipeline by another skill (e.g. `lld-sync` by `feature-end`) rather than from a human prompt. |
| **Problems & follow-ups** | A session-log section recording real defects/gaps found during implementation that are outside the current issue's scope. |
| **FEATURE_ID** | `$EDF_FEATURE_PREFIX-<issue-number>` (ADR-0037) — identifies a feature across session logs and sync artefacts. |

## Design Principles / Constraints

1. **Verified, not asserted** — every "mandatory" step has a checkable post-condition. An agent that cannot
   prove the step happened must not be allowed to skip it.
2. **Single-writer for shared artefacts** — parallel writers of the same document conflict (observed: 30
   Document Control conflicts across team runs). In team runs, teammates write isolated per-task files; one
   owner (the lead) reconciles them.
3. **Nothing lost** — every real problem discovered during implementation is recorded in a session log and,
   for team runs, promoted to a tracked issue. Problems must not depend on someone remembering them.
4. **Proportionate ceremony** — gates and checks are added only where past failures justify them. A Light
   single-file fix does not carry team-run machinery.
5. **Process survives the session** — artefacts the process depends on (team session logs, reconciled LLDs)
   are committed, not left in the working tree to be lost at session end.

## Roles

| Role | Type | Description |
|------|------|-----------|
| **Plugin Maintainer** | Persistent | Develops the EDF plugin itself. Applies the delivery pipeline to plugin changes and hardens the skills. Primary beneficiary of every story. |
| **Feature-team Lead** | Contextual | Orchestrates parallel implementation via `/feature-team`. Defines tasks, spawns teammates, reconciles shared artefacts at the end of a run. |
| **Teammate** | Contextual | A Claude Code session implementing one issue autonomously in its own worktree. Runs `feature-core` and `feature-end` without confirmation prompts. |
| **Retro Facilitator** | Contextual | Runs `/retro`. Assesses process health and is responsible for driving previous actions to completion or filing them. |

**Role relationships:** The Feature-team Lead and Teammates are the roles whose failures created the
observed problems; the Plugin Maintainer fixes the skills those roles follow. There are no permission
boundaries — every role is a developer running Claude Code.

---

## Implementation grouping

**Ship as one item.** Despite the four-epic structure below, all stories in this document are
implemented as **one cohesive change** — a single feature branch, a single PR, and a single plugin
version bump (0.10.26 → 0.10.27). Every story edits overlapping skill files (`lld-sync`,
`feature-end`, `feature-team`, `feature-core`, `retro`); splitting delivery would fragment the diff,
re-touch the same files, and re-do the version bump.

The epic/story decomposition exists so each behavioural change has **testable acceptance criteria** and
can be verified independently — it is not a delivery plan. Downstream stages (`/kickoff`, `/architect`,
`/feature`) treat this document as a single implementation item, not as separate epics to schedule.

---

## Epic 1: LLD Sync in Team Runs [Priority: High]

Eliminates the parallel Document Control conflict tax. In worktrees, teammates write per-task sync files
instead of editing the canonical LLD; the lead reconciles them into the LLD(s) at the end of the run.

<a id="REQ-lld-sync-team-runs-per-task-sync-files-in-worktrees"></a>

### Story 1.1: Per-task LLD sync files in worktrees

**As a** Teammate,
**I want to** write my LLD delta to a per-task sync file instead of editing the canonical LLD when working in
a worktree,
**so that** parallel teammates never edit the same LLD and rebases stop conflicting on additive Document
Control changes.

**Worktree detection:** `lld-sync` and `feature-end` detect a worktree via the existing method from
feature-team Step 1b — `git rev-parse --git-common-dir` differs from `git rev-parse --show-toplevel`.
When that check fails (running in the main repo), the in-place path is used instead.

**Solo runs are unaffected:** a solo `/feature` + `/feature-end` run stays in the main repo working copy, so
the check fails and the existing in-place apply is used — identical to today. Only worktrees (teammates in a
`/feature-team` run) take the deferral path. The agent needs no "am I a teammate" context — the worktree
state IS the signal.

**Acceptance Criteria:**

- Given `lld-sync` runs in a worktree (where `git rev-parse --git-common-dir` differs from
  `--show-toplevel`), when it completes, then no canonical LLD file under `docs/design/v*/lld-*.md` is
  modified, and a per-task file exists at `docs/design/lld-sync/<FEATURE_ID>-<slug>.md`.
- Given a per-task file is written, then it records the issue number and slug, the **Target LLD(s)** from
  the issue body's `## Design references`, the four-category delta (Corrections / Additions / Omissions /
  Confirmations), and any deferred kb / coverage-manifest / Rev-N cleanup notes.
- Given `lld-sync` runs in a worktree, when Step 4 produces the sync report, then the `### LLD updated` block
  states "Target LLD(s) + Pending lead reconcile — version bump deferred" and does not claim a version bump.
- Given `lld-sync` runs in the main repo (detection fails), when it completes, then the existing in-place
  path applies — the canonical LLD is edited and its Document Control bumped, unchanged from current behaviour.
- Given two teammates run `lld-sync` in their own worktrees for different issues in the same run, when both
  feature-ends finish, then neither touched the canonical LLD — no Document Control conflict on either rebase.

**Notes:** filenames use FEATURE_ID per ADR-0037; the slug is cosmetic since FEATURE_ID is unique per issue
(Open Question 3).

---

<a id="REQ-lld-sync-team-runs-lead-reconciles-llds"></a>

### Story 1.2: Team lead reconciles LLD(s) at end of run

**As the** Feature-team Lead,
**I want to** reconcile every teammate's per-task sync file into the canonical LLD(s) after all PRs are
merged,
**so that** the design documents reflect everything that shipped and the per-task files do not accumulate.

**Scope:** the reconcile runs once per team run on `main`. It collates the run's per-task sync files (glob
`docs/design/lld-sync/<FEATURE_ID>-*.md`), applies each delta to its target LLD(s) reusing the existing
in-place apply logic from `lld-sync` Steps 3/3a/3b/3c, bumps each touched LLD's Document Control, and deletes
the applied files. A run may touch multiple LLDs; each file's target list comes from its `## Design
references`.

**Acceptance Criteria:**

- Given a team run has completed with per-task sync files at `docs/design/lld-sync/<FEATURE_ID>-*.md`, when
  the lead runs the reconcile (feature-team Step 7.5), then every Correction and Addition is applied to its
  target LLD with a `> **Implementation note (issue #N):**` callout, preserving stable `<a id="LLD-...">`
  anchors per ADR-0026.
- Given a target LLD is touched, then its Document Control is bumped — Version/Status updated and a
  `| Revised | [date] | Issue #N |` row added — per `lld-sync` Step 3b.
- Given a sync file records deferred kb or coverage-manifest deltas, when reconciled, then they are applied
  to `kb/architecture.md`, `kb/anti-patterns.md`, and the coverage manifest.
- Given a sync file's delta is applied, when processed, then the file is deleted from `docs/design/lld-sync/`.
- Given the reconcile completes, then the LLD/kb/manifest edits and file deletions are committed on `main`,
  and no `docs/design/lld-sync/<FEATURE_ID>-*.md` files remain for the run.
- Given a run touched multiple LLDs, when reconciled, then every LLD named in the sync files' Target LLD(s)
  is updated — none left pending.

---

## Epic 2: Verified Completion & Issue Hygiene [Priority: High]

Converts mandatory-but-skippable steps into verified gates and guarantees discovered problems become
tracked issues.

<a id="REQ-verified-completion-issue-hygiene-feature-end-post-condition-gates"></a>

### Story 2.1: Feature-end post-condition gates before merge

**As the** Plugin Maintainer,
**I want to** prevent `feature-end` from merging when the session log or lld-sync evidence is missing,
**so that** "mandatory" steps are enforced by verification, not by the agent's willingness.

**Scope:** applies to all `feature-end` runs — solo Standard/Heavy runs and team-run worktree sessions alike.
The session-log gate is a file existence check (ADR-0037 find-by-feature-ID); the lld-sync gate checks for
the evidence appropriate to the run mode (per-task sync file in a worktree, Document Control `Revised` row in
the main repo). See Open Question 2 for the block-vs-auto-write behaviour.

**Acceptance Criteria:**

- Given `feature-end` is invoked, when it reaches the pre-commit gate (Step 2.7), then a session log matching
  `docs/sessions/YYYY-MM/*-<FEATURE_ID>.md` exists, found by feature ID per ADR-0037; if absent, the gate
  reports the missing artefact by feature ID and feature-end writes it before proceeding — the skip is
  visible, not masked.
- Given the issue has an LLD reference, when the gate runs, then lld-sync evidence is present: a per-task
  sync file in a worktree, or a Document Control `Revised` row in the main repo; if absent, feature-end
  re-runs `lld-sync` before proceeding.
- Given the issue has no LLD reference, when the gate runs, then feature-end records that fact and passes the
  lld-sync check.
- Given either gate check fails, when feature-end continues, then the merge (Step 4) does not proceed until
  the check passes.
- Given a gate check passes, when feature-end proceeds, then no additional prompts are introduced — the check
  is a verification step, not a new approval point.

**Notes:** block-vs-auto-write behaviour defaults to block-with-visible-write (Open Question 2).

---

<a id="REQ-verified-completion-issue-hygiene-session-logs-record-problems"></a>

### Story 2.2: Session logs record Problems & follow-ups

**As the** Plugin Maintainer,
**I want to** require every session log to carry a Problems & follow-ups section populated whenever a real
defect outside the current issue is found,
**so that** problems are recorded at the moment they are discovered and are not lost when context compacts.

**Acceptance Criteria:**

- Given feature-core Step 3dF creates a session log, then the template includes a `## Problems & follow-ups`
  section with a note to record out-of-scope defects instead of silently fixing them.
- Given a real defect or gap outside the current issue is found during implementation, then the agent records
  it in Problems & follow-ups as a title plus one-line description before proceeding — not silently
  fixed-and-forgotten.
- Given feature-end Step 2 appends the narrative sections, when it finalises the log, then it also summarises
  the final Problems & follow-ups state into the log.
- Given an issue had no out-of-scope problems, when the log is finalised, then the section states `none`
  rather than being absent.
- Given a recorded problem later becomes a tracked issue (feature-team Step 7.5b), then the session-log entry
  is cross-referenceable to that issue number.

---

<a id="REQ-verified-completion-issue-hygiene-team-log-committed-follow-ups-filed"></a>

### Story 2.3: Team session log committed; follow-ups filed as issues

**As the** Feature-team Lead,
**I want to** commit the team session log and file every recorded follow-up as a tracked GitHub issue at the
end of a run,
**so that** the team's orchestration context and its problems survive the session.

**Depends on:** Story 2.2 — the team log's Problems & follow-ups section (fed by each per-issue log's
Problems & follow-ups) is the source of the issues this story files.

**Acceptance Criteria:**

- Given all waves complete, when the lead writes the team session log (Step 8), then it includes a
  **Follow-ups filed** section mapping each problem to its issue number and board status.
- Given the team log is written, then it is `git add`-ed, committed, and pushed immediately — it is not left
  uncommitted.
- Given a recorded follow-up has no tracking issue, when the run ends, then a GitHub issue
  `[Follow-up] <problem>` is created on the board Todo (via `gh-issue-manager`) and its number is cited in the
  team log.
- Given a follow-up already has a tracking issue, when the run ends, then no duplicate is created — the
  existing issue number is cited.
- Given no problems were recorded, when the run ends, then the Follow-ups filed section states `none` and no
  issues are created.

---

## Epic 3: Retro Carry Rule [Priority: Medium]

Breaks the deadlock where actions are re-flagged "Not started" retro after retro.

<a id="REQ-retro-carry-rule-two-carried-actions-filed"></a>

### Story 3.1: Two-carried retro actions filed as issues

**As the** Retro Facilitator,
**I want to** file any action still "Not started" for a second consecutive retro as a GitHub issue during the
retro session,
**so that** stalled actions become tracked work with owners instead of looping through carry cycles.

**Trigger default:** assumes Open Question 1 option (a) — two consecutive carries (the observed deadlock). If
the decision changes to total appearances, the trigger condition adjusts.

**Acceptance Criteria:**

- Given a retro runs, when the "Actions from previous retro" table is built, then every action carries a
  **Carry** count equal to the consecutive retros it has sat "Not started".
- Given an action is "Not started" with Carry ≥ 2 (consecutive), when Step 5 executes, then during the retro
  session it is filed as a GitHub issue `[Retro carry] <action>` on the board Todo (via `gh-issue-manager`)
  and the table row is replaced with `→ filed as #N`.
- Given an action is "Not started" with Carry = 1, when Step 5 executes, then it remains in the table as a
  carry (not filed yet).
- Given an action is Done or Partial, when the table is built, then it does not trigger the filing rule.
- Given a filed action appears in the following retro, when the previous-actions table is built, then it shows
  as filed with its issue reference, not re-flagged "Not started".

**Notes:** trigger assumes Open Question 1 option (a) — consecutive carries.

---

## Epic 4: Skill-Boundary Continuation [Priority: Medium]

Fixes agents stopping after a sub-step skill finishes, treating a report as a terminal deliverable.

<a id="REQ-skill-boundary-continuation-return-to-caller-tails"></a>

### Story 4.1: Sub-step skills end with a return-to-caller instruction

**As the** Plugin Maintainer,
**I want to** give every sub-step skill an explicit closing instruction telling the agent what to do next
(continue the caller's pipeline or state the next step),
**so that** agents follow through to the end of the pipeline instead of idling after producing a report.

**Skills in scope (inventory of sub-step skills that end on a report):** `lld-sync` (by feature-end),
`diag` (by feature-core Step 6), `feature-evaluator` (by feature-core Step 6b), `drift-scan` (by retro Step 4),
`lld-review` (by /lld Step 2.5), `requirements-review` (by /requirements gates), `qa-contracts`,
`qa-coverage`, `qa-executor`, `qa-explorer` (by /qa). The `ci-probe` background agent already carries a
"continue with Step 9" tail (feature-core Step 9) — used as the model phrasing.

**Acceptance Criteria:**

- Given a skill in the inventory (`lld-sync`, `diag`, `feature-evaluator`, `drift-scan`, `lld-review`,
  `requirements-review`, `qa-contracts`, `qa-coverage`, `qa-executor`, `qa-explorer`), when its SKILL.md ends,
  then it carries a closing block stating what to do next — continue the caller's next step or the next
  `/command`.
- Given `lld-sync` is invoked from `feature-end`, then its tail instructs continuing with feature-end Step 2 —
  the agent does not stop after printing the sync report.
- Given `lld-sync` runs standalone, then its tail states that `/feature-end <N>` is the next step.
- Given every skill in the inventory is edited, then a grep for the return-to-caller tail matches each
  SKILL.md (mechanical, testable check).
- Given the tails are in place, when an agent runs a pipeline (e.g. feature-core → feature-end), then the
  session log records the steps completed in order with no user nudge between steps (observational proxy).

**Notes:** the behavioural outcome (agent follows through) is not deterministically testable; the ACs bound
the deliverable to the presence of the instruction text. If stalls persist after this change, a
PostToolUse-hook fallback is a documented future option.

---

## Cross-Cutting Concerns

### Security

- **No new privilege surface.** All changes are to skill instructions, docs, and process conventions.
  No new executable code, no network access, no credential handling. Story 2.3's issue creation uses the
  existing `gh-issue-manager` agent with the project's existing scopes.

### Performance

- **Proportionate checks.** Post-condition gates (Story 2.1) are single-file existence checks and LLD
  Document Control greps — sub-second, run once per feature-end. No measurable impact on pipeline throughput.
- **No added cost.** Per-task sync files (Story 1.1) replace in-place edits with a small write; the reconcile
  (Story 1.2) runs once per run. No new sub-agents beyond the existing `gh-issue-manager`.

### Observability

- **Carry counts visible.** The retro report's carry column (Story 3.1) makes stalled actions measurable
  across retros — the count that drives the filing rule is recorded, not just the status.
- **Follow-up provenance.** Every filed follow-up (Story 2.3) is cited in the team session log with its issue
  number, so a reader can trace problem → issue → outcome.

---

## What We Are NOT Building

- **A new CI/CD pipeline or hook framework.** Post-conditions are enforced in skill instructions, not via a
  new hook runtime. A PostToolUse-hook fallback for stall detection is explicitly noted as a future option
  if the text fix proves insufficient.
- **Changes to the canonical LLD's own format.** Reconciliation (Story 1.2) reuses the existing Document
  Control and `Implementation note` conventions; no new LLD schema.
- **Per-teammate session-log promotion.** Teammate `feature-end` logs remain per-issue; only the lead's team
  log gains the follow-ups-filed section. No new log type.
- **Retro action automation beyond filing.** Actions are still executed by people/agents; the rule only
  stops the silent re-flagging loop.
- **Rewrites of the sibling skills' process semantics.** The audit of sub-step skills (Story 4.1) adds
  continuation tails only — it does not redesign drift-scan, diag, or the review agents.

---

## Open Questions

| # | Question | Context | Options | Impact |
|---|----------|---------|---------|--------|
| 1 | Should the carry rule fire after 2 carries total or 2 consecutive carries? | A "Not started" action in retros R1 and R2 loops; an action started-and-reverted between retros is different. | (a) 2 consecutive carries; (b) 2 total appearances | Determines when the filing rule triggers. Default (a) — consecutive matches the observed deadlock. |
| 2 | Should feature-end block the merge outright when the session log is missing, or auto-write it? | The gate must not strand a merge, but auto-writing a log the agent skipped could mask the real failure (why did it skip?). | (a) Block and require an explicit agent write with reason; (b) auto-write silently | Determines whether skipped steps are visible. Default (a). |
| 3 | What slugs distinguish per-task sync files when multiple issues share a slug? | Two issues in one run may produce the same kebab slug. | (a) FEATURE_ID already disambiguates the filename — slug is cosmetic; (b) require unique slugs | Filename uniqueness. Default (a) — FEATURE_ID is unique per issue. |

---
