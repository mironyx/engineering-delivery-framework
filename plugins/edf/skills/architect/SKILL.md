---
name: architect
description: Read a plan document and produce all design artefacts in one pass (ADRs, LLDs, design doc updates, enriched issue bodies), so /feature agents can implement against approved designs.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill, TodoWrite
---

# Architect — Batch Design Artefact Generator

Reads a plan file and produces the design artefacts needed for each item, so `/feature` can implement against approved designs.

**Model:** Use Opus (the latest Claude model) for this skill and all sub-agents it spawns. When launching agents, pass `model: "opus"`. Exception: purely-mechanical agents whose frontmatter pins a smaller model (e.g. `gh-issue-manager` runs on Haiku because it only executes pre-assembled `gh` commands and string substitution) — leave their pinned model alone.

**Usage:**

- `/architect` — reads the most recent plan in `docs/plans/`, processes all epics
- `/architect docs/plans/2026-03-29-mvp-phase2-plan.md` — reads a specific plan, processes all epics
- `/architect --epics E2,E3` — processes only epics in Phases 2 and 3
- `/architect --epics E2.1,E2.3,E3.1` — processes only the listed epics
- `/architect docs/plans/plan.md --epics E4` — specific plan, only Phase 4 epics
- `/architect review <issue-number>` — reviews existing design for an issue (see Review mode below)

### Epic filter syntax

The `--epics` flag accepts a comma-separated list of epic identifiers. Two forms:

- **Phase-level:** `E2` matches all epics in Phase 2 (E2.1, E2.2, E2.3, etc.)
- **Individual:** `E2.1` matches only that specific epic

Examples:
- `--epics E2` → E2.1, E2.2, E2.3
- `--epics E2,E3` → all epics in Phases 2 and 3
- `--epics E2.1,E3.3` → only E2.1 and E3.3
- `--epics E2,E3.1` → all of Phase 2 plus E3.1

When `--epics` is omitted, all epics in the plan are processed.

---

## Review Mode

If `$ARGUMENTS` starts with `review`, extract the issue number and run the review process instead of the creation process.

**Purpose:** Audit an existing design before handing off to `/feature`. Catches stale references, gaps in contract detail, and contradictions introduced since the design was written.

### Review Step 1: Read the issue and its design artefacts

Run `gh issue view <number>` to get the issue body. Then read all linked artefacts:

- LLD sections referenced in the issue body (`docs/design/`)
- ADRs referenced (`docs/adr/`)
- Requirements (`docs/requirements/`)
- Relevant source files in `src/` — compare actual file paths and patterns against what the LLD specifies

### Review Step 2: Assess design health

Check each of the following and note findings:

| Check | What to look for |
|-------|-----------------|
| **Stale file paths** | LLD references files that have been moved, renamed, or deleted |
| **Pattern drift** | Codebase has adopted new patterns (new helpers, request-context abstractions, framework upgrades) that the LLD predates |
| **ADR conflicts** | Design contradicts a decision recorded in `docs/adr/` after the design was written |
| **Thin contracts** | Function signatures, types, or internal decomposition are vague or missing — would block a `/feature` agent |
| **Missing BDD specs** | No `describe`/`it` blocks for an agent to implement against |
| **Uncovered acceptance criteria** | Acceptance criteria in the issue have no corresponding design detail |
| **Missing behavioural flows** | Multi-component interactions lack sequence diagrams — reviewer cannot build theory from text alone |
| **Missing structural overview** | Task introduces/modifies module boundaries but has no structural diagram showing dependencies |
| **Unverifiable invariants** | Constraints listed without a verification method (test, type check, grep), or invariants scattered inline instead of collected in the Invariants table |

### Review Step 3: Report and optionally patch

Present a concise health report:

```
## Design health — #<issue>: <title>

### Findings
| # | Severity | Check | Detail |
|---|----------|-------|--------|
| 1 | High/Med/Low | <check> | <what's wrong and where> |

### Verdict
Ready for /feature | Needs patches before /feature
```

Severity guide: **High** = would cause a `/feature` agent to implement incorrectly or get stuck. **Med** = gap or ambiguity that needs resolving. **Low** = minor stale reference, cosmetic.

If there are High or Med findings, offer to patch the affected docs in place. **Wait for user confirmation before making any changes.**

After patching, commit:

```bash
git add <specific-files>
git commit -m "docs: design health patch for #<issue> — <summary>"
```

**Stop after the report (and any approved patches).** Do not proceed to the creation process.

---

## Revision Mode

If the user invokes `/architect` with an explicit compare-revisions intent —
e.g. a flag like `--compare-rev r9`, or prompt phrasing like "update LLDs for
v11 rev 10 against rev 9" — and prior LLDs already exist, the skill operates
in **revision mode** instead of the greenfield creation process.

**Behaviour:**

1. **Diff the requirements file** across the two revisions (`git show <ref>:<path>`).
   Filter to REQ-anchored content. Trust agent judgement to ignore prose
   polishing, change-log churn, and frontmatter noise.
2. **For each affected story**, locate the LLD that owns the matching
   manifest entry. In that LLD:
   - **Part A** — update in place to reflect the new revision. At minimum,
     note the revision in a "Recent revisions" line. Beyond that: extend the
     AC list, BDD specs, invariants, and behavioural flows wherever Rev N
     introduces new stories or changes that belong in human-reviewable
     Part A — do not treat the Rev N section in Part B as a substitute for
     missing Part A content.
   - **Part B** — append `## Pending changes — Rev N` at the end of the file,
     where `N` is the next available revision number (r2, r3, …). Within that
     section, write one `### Story <REQ>` block per changed story, following
     the standard Part B style (file paths, component reuse, contracts, BDD
     specs).
3. **Manifest** — flip affected entries to `status: Revised`. Do **not**
   touch `lld_revision` here — that field is owned by `/lld-sync`.
4. **Stacking is allowed.** If a previous Rev N section already exists and
   has not yet shipped, append the new section alongside it.
5. **Commits per LLD touched** — same convention as the greenfield creation
   process.

For all LLD content rules and downstream steps (issue creation, enrichment,
execution waves, dependency graph, manifest update, commits, session log,
report) follow the standard Process below. Revision mode only changes
*where* new LLD content lands — a `## Pending changes — Rev N` section
instead of the body. Everything else (new issues for new work, board
placement, parallelisation analysis) is identical to greenfield.

---

## Decision Logic

For each item in the plan, determine the artefact type:

| Item type | Repo artefact (source of truth) | Issue update |
|-----------|--------------------------------|--------------|
| Cross-cutting decision (new technology, convention) | ADR in `docs/adr/` via `/create-adr` | Reference ADR |
| Implementation item with contracts | LLD in `docs/design/v{N}/` (new) or `docs/design/` (legacy, flat) | Reference LLD section |
| Design doc update (existing doc needs correction) | Edit to existing `docs/design/` file | Reference updated section |
| Simple bug fix (already covered by existing LLD) | None needed | Add BDD specs, reference existing LLD |
| Small feature (no existing LLD coverage) | LLD section for the item | Reference LLD section |

## Process

Execute these steps sequentially.

### Step 1: Read the plan, parse epic filter, and check existing state

**Parse arguments.** Scan `$ARGUMENTS` for:

1. **A file path** — if present, use it as the input file. Otherwise find the most recent `docs/plans/*.md` file by modification date.
2. **Input detection.** The input may be either a plan file (`docs/plans/`) or a requirements document (`docs/requirements/`). If it is a requirements document, treat each epic and its stories as the work items to design — extract epics, stories, priorities, and acceptance criteria the same way you would from a plan. The `--epics` filter works identically (filter by epic number). Skip `/kickoff`-specific concerns (HLD creation, ADR discovery, phase sequencing) — the requirements doc is the authority for scope. See ADR-0022 for the tiered process rationale.
3. **`--epics` flag** — if present, extract the comma-separated list of epic identifiers. Parse each:
   - Phase-level (e.g. `E2`) — expand to all epics matching `E2.*` in the plan.
   - Individual (e.g. `E2.1`) — match that exact epic.
   - Store the resolved set of epic identifiers (e.g. `{E2.1, E2.2, E2.3, E3.1}`).
4. If `--epics` is not provided, all epics in the plan are in scope.

**Read the input file fully.** Extract the list of epics with their priorities, dependencies, and design needs. **Filter to only the in-scope epics.** Report which epics are in scope and which are being skipped.

**Consume kickoff's parallelisation map (if present).** If the plan was produced by `/kickoff`, it includes a `Parallelisation Map` section and per-epic `Owns (components)` / `Touches (components)` / `Parallelisable with` fields. Treat these as the upstream claim about epic-level parallelism — useful when planning waves across multiple epics in scope. File-level analysis in Step 2 may **refine or contradict** kickoff's claim once actual file paths are known. If you contradict it (e.g. two epics kickoff marked parallel-safe both write to the same migration file), call this out in the Step 2 summary and the Step 7 report so the plan can be patched.

**Before creating anything**, check what already exists:

1. **Issues:** Run `gh issue list --state open --limit 100` to see all open issues. Do not create issues that already exist.
2. **Design docs:** Check `docs/design/`, `docs/adr/`, and `docs/requirements/` for existing coverage of each item.
3. **Source of truth rule:** Design detail must live in version-controlled repo docs (`docs/design/`, `docs/adr/`, `docs/requirements/`), not only in GitHub issue bodies. Issue bodies should reference repo docs, not replace them. If an item has detail only in an issue body, it needs a repo doc artefact (LLD section, design doc update, or requirements update).
4. **Issue structure check:** For each existing issue that this run will enrich or create tasks for, run `gh issue view <number> --json labels,title` and check:
   - If the issue contains **multiple stories** (i.e. the decomposition assessment in Step 2b will produce ≥ 2 task issues), the issue must carry the `epic` label. If it does not, flag this in the Step 2 summary table under a "Label fix needed" column and correct it before producing any artefacts — use `gh issue edit <number> --add-label "epic" --remove-label "kind:task"` and update the title to `epic: <name>` format.
   - If the issue is a single-task item, it should carry `kind:task` and have a `## Parent epic` section. If no parent epic exists, flag it and ask the user whether to create one or proceed without.
   - **Never enrich a multi-story issue without first fixing its label.** Enriching a `kind:task` issue with story tables creates the exact structural inconsistency this check is designed to prevent.

### Step 2: Analyse and present overview

For each in-scope epic, determine:

1. **Artefact type** — which row in the decision logic table applies.
2. **Input sources** — what files, issues, or design docs to read.
3. **Output** — what artefact will be produced and where.
4. **Decomposition** — see Step 2b below.

Present a summary table to the user:

```
| # | Epic | Artefact type | Output path | Depends on | Split? |
|---|------|---------------|-------------|------------|--------|
```

Include a preliminary execution waves proposal below the table:

```
### Proposed execution waves

| Wave | Items | Blocked by | Notes |
|------|-------|------------|-------|
| 1 | #1, #2 | — | Parallelisable |
| 2 | #3 | Wave 1 (#1) | |
```

Include a Mermaid dependency graph below the waves table:

```mermaid
graph LR
  A["#N · Task title\n(layer)"]
  B["#M · Task title\n(layer)"]
  C["#P · Task title\n(layer)"]
  A --> C
  B --> C
```

Nodes use the format `#<issue> · <short title>\n(<layer>)`. Dashed arrows (`-.->` with label) indicate soft coupling such as a shared migration. Nodes that have no incoming arrows are parallelisable from the start. Add a plain-English summary below the diagram stating which tasks can start immediately in parallel and which must be sequential.

**Hard rule — shared files force sequential waves:** Any two tasks that both write to the same source file (e.g. `tables.sql`, `functions.sql`, any shared migration) must be placed in different waves, even if their logical coupling is soft. Parallel PRs on the same file always produce a merge conflict. Encode this as a solid arrow in the dependency graph, not a dashed one.

**Wait for user confirmation** before producing artefacts. The user may re-prioritise, skip items, redirect artefact types, adjust wave assignments, or reject a proposed split.

### Step 2b: Decomposition assessment

For each epic, assess whether it should be split into multiple task issues. The bar is high — splitting has overhead (extra issues, PRs, dependency tracking) and should only happen when there is clear rationale.

**Split if and only if both conditions hold:**

1. **Size** — estimated **total PR diff** exceeds 200 lines (production code + tests + fixtures + types). Rule of thumb: production code is ~30% of the total diff when following TDD with fixtures, so ~70 lines of production code ≈ 200-line PR. If you estimate 150 lines of production code, the PR will likely be 400–500 lines — that needs splitting.
2. **Natural seam** — there is an independently testable or independently deployable unit that does not share files with the remainder.

If only one condition holds (large but no clean seam, or clean seam but small), do **not** split. However, if the size vastly exceeds the limit (e.g. 3×+), prioritise splitting even if seams are imperfect — large PRs are harder to review than slightly awkward boundaries.

When a split is warranted, propose the task issues with explicit dependency order (A completes → B starts) and note which files each task touches. Tasks that do not share files and have no dependency can be assigned to the same execution wave for parallel implementation. Add the proposed split to the summary table and explain the rationale briefly. The user confirms or rejects before any issues are created.

**Schema-foundations rule.** Skip this rule if `migration-dir` is blank in the project's kb file-map (project does not use migrations).

If set, and the epic adds new tables, columns, RPCs, indexes, or CHECK changes (whether via `<schema-dir>` for declarative projects, or as new files in `<migration-dir>` for hand-authored projects), the LLD task breakdown **must** include a "DB schema foundations" task as Task 1. All schema additions for the epic land in that one task. Downstream tasks must be read-only on `<schema-dir>` (declarative) and must not add new files to `<migration-dir>` (either workflow).

Rationale: schema files in `<schema-dir>` are textually shared across tasks, and `<migration-dir>` files are timestamp-ordered. Parallel tasks editing schema produce both textual merge conflicts and migration-ordering ambiguity. One foundations task eliminates both.

### Step 3: Read all input sources

For each in-scope epic, read:

- Referenced GitHub issues: `gh issue view <number>`
- Referenced design docs in `docs/design/`
- Referenced ADRs in `docs/adr/`
- Relevant source files in `src/`
- Requirements in `docs/requirements/`

Read broadly — understanding the full context prevents design artefacts that contradict existing decisions.

### Step 4: Produce artefacts

Process epics in the order listed in the plan. For each epic, run these sub-steps in execution order:

1. **ADR** — produce any cross-cutting decisions first (LLD may reference them).
2. **LLD** — delegate to `/lld`; this produces the LLD file, the task list, and a draft coverage manifest with `issue: null`.
3. **Task issues** — read the LLD's `## Tasks` section and dispatch the `edf:gh-issue-manager` agent to create GitHub issues and update the epic body.
4. **Coverage manifest backfill** — patch the manifest with real issue numbers.
5. **Design doc update** — edit any pre-existing design docs (only when the decision logic flagged this).

The subsections below describe each in detail, in execution order. The "Epic body template" and "Task body template" subsections are reference material consumed by step 3, not separate steps.

#### 1. ADR (cross-cutting decision)

Use `/create-adr` to produce the ADR. Provide the context, options, and recommended decision based on what the plan says and what you read in Step 3.

#### 2. LLD (implementation item with contracts)

Delegate to the `/lld` skill:

```
Skill({skill: "lld", args: "epic <epic-issue-number> v<version> --non-interactive"})
```

`<epic-issue-number>` is the GitHub issue number of the epic. `<version>` is the project version slug (`v11`, `v12`, …). The `--non-interactive` flag skips `/lld`'s Step 1 overview — `/architect`'s Step 2 already obtained user approval on the batch.

`/lld` produces:
- `docs/design/v<N>/lld-<epic-id>-<short-name>.md` — the LLD with Part A, Part B, self-critique pass, `## Tasks`, and execution order.
- `docs/design/v<N>/coverage-<epic-id>.yaml` — the coverage manifest with `issue: null` placeholders.

`<epic-id>` is the canonical epic identifier — see `/lld` Step 2 for the format. `<short-name>` is a 1–3-word lower-kebab phrase capturing the epic's domain concept; see `/lld` Step 2 for the derivation rule.

After `/lld` returns: read the produced LLD to extract task definitions for the next sub-step, and verify each non-null `lld:` value in the coverage manifest resolves to an actual `<a id="LLD-...">` anchor in the LLD file.

#### 3. Task issues (from LLD task breakdown)

Read the LLD's `## Tasks` section. Each task entry becomes one GitHub issue.

Pre-assemble the task bodies and the updated epic body (see templates below) using **placeholder task IDs** (`T1`, `T2`, …). The `edf:gh-issue-manager` agent will substitute real `#N` numbers into both the Tasks checklist and the dependency-graph nodes after creating the issues.

Then dispatch the agent using the `Agent` tool:

```
Agent({
  subagent_type: "edf:gh-issue-manager",
  description: "Create task issues for epic #<N>",
  prompt: |
    epic_number: <epic-issue-number>

    tasks:
      - id: T1
        title: <task title from LLD>
        labels: <phase-label>,<area-label>,kind:task
        body: |
          <task body — see Task body template below>
      - id: T2
        ...

    epic_body: |
      <full epic body with T1, T2 placeholders in the Tasks checklist
       and the dependency graph — see Epic body template below>
})
```

The agent runs `gh issue create` per task (via `${CLAUDE_PLUGIN_ROOT}/bin/gh-create-issue.sh`, which deduplicates and adds to the board), captures each result (`created:<N>` or `exists:<N>`), substitutes the real numbers everywhere `T1`/`T2`/… appear in `epic_body`, and runs `gh issue edit <epic_number> --body ...`. No per-issue confirmations.

##### Task body template

```
## Parent epic
#<epic-issue-number>

## Stories
- Story X.Y: <one-line from LLD>

## Design reference
[docs/design/v<N>/lld-<epic-id>-<short-name>.md §B.N](docs/design/v<N>/lld-<epic-id>-<short-name>.md#LLD-<epic-id>-<section-slug>)

## HLD reference
[v<N>-design.md §section](docs/design/v<N>/v<N>-design.md)

## What
<1-2 sentences from LLD task>

## Acceptance criteria
- [ ] <from LLD>

## BDD specs
<BDD specs from LLD>

## Files to create/modify
- `path` — <purpose>

## Layer
DB | BE | FE

## Depends on
<from LLD; reference dependent tasks by their `T<N>` placeholder so the agent can resolve them to real issue numbers>
```

##### Epic body template

```
## Epic: V<N> E<X>.<Y> — <title>
<1-2 sentence summary>

### Requirements
[v<N>-requirements.md §Epic X](docs/requirements/v<N>-requirements.md#epic-x-…)

### Design reference
[docs/design/v<N>/lld-<epic-id>-<short-name>.md](docs/design/v<N>/lld-<epic-id>-<short-name>.md)

### HLD reference
[v<N>-design.md §sections](docs/design/v<N>/v<N>-design.md)

### Related ADRs
- [ADR-NNNN](docs/adr/NNNN-….md) — one-line description

### Stories
- Story X.Y: <one-line summary>

### Tasks
- [ ] T1 — <title>
- [ ] T2 — <title>

### Dependency graph
```mermaid
graph LR
  T1["T1 · title\n(layer)"] --> T2["T2 · title\n(layer)"]
```

### Execution waves
| Wave | Tasks | Notes |
|------|-------|-------|
| 1 | T1 | … |
| 2 | T2 | blocked by T1 |

### Exit criteria
<from implementation plan>
```

The agent substitutes `T1` → `#<created-issue-number>`, `T2` → `#<created-issue-number>`, … in **both** the Tasks checklist and the dependency-graph node labels before running `gh issue edit`.

#### 4. Coverage manifest backfill

After `edf:gh-issue-manager` returns the mapping `{T1: #N, T2: #M, …}` (or the parent skill reads it from the agent's output), edit `docs/design/v<N>/coverage-<epic-id>.yaml` and replace each `issue: null` with the corresponding real number. Match by the LLD section anchor: every task in the LLD has one section anchor, and every coverage entry's `lld:` field points at one of those anchors — that's the join key.

```yaml
epic: <epic-id>
entries:
  - req: REQ-<anchor-from-requirements>
    lld: lld-<epic-id>-<short-name>.md#LLD-<epic-id>-<section-slug>
    issue: <number>
    files: []
    status: Approved # Draft | Approved | Implemented | Revised
    lld_revision: r1 # latest LLD revision shipped; bumped by /lld-sync
    # files: populated by /feature-end after merge
```

**Valid statuses and who sets them:**

| Status | Meaning | Set by |
|--------|---------|--------|
| `Draft` | Story deferred — no implementing LLD section yet | `/lld` or `/architect` at creation |
| `Approved` | LLD written, not yet implemented | `/lld` or `/architect` at creation |
| `Implemented` | PR merged, `files:` populated | `/feature-end` after merge |
| `Revised` | LLD corrected post-implementation (regression or design gap found) | `/lld-sync` on LLD patch |

Rules:
- One entry per REQ anchor in the requirements for stories covered by this epic.
- Do NOT add fields outside the schema. `fix_issue:`, `fix_pr:`, and similar are not valid fields. Use YAML comments for notes.
- Do NOT invent status values — `Regression`, `Pending`, etc. are not valid. Use `Revised` + a comment when an LLD is corrected.
- Stories already implemented by a prior epic get `status: Implemented` with the implementing epic's LLD and issue referenced. Add a comment noting the origin.
- Stories with no LLD section yet get `lld: null` and `status: Draft`.
- If `/kickoff` already created a coverage matrix for this epic, update it rather than creating a new file.

#### 5. Design doc update (only when decision logic flags it)

If the decision logic in Step 1 marked an item as "Design doc update" rather than LLD/ADR, edit the existing design doc directly. Add a change-log entry at the top noting the date and reason.

### Step 5: Commit each artefact

After producing each artefact, commit it individually:

```bash
git add <specific-files>
git commit -m "docs: design for #<issue> — <summary>"
```

One commit per item for granular review. Do not batch.

### Step 6: Write session log

Follow `.claude/skills/shared/session-log.md`. Use `<skill>=architect` and a `<slug>` identifying the epics or plan sections processed (e.g. `architect-e11-e17`).

### Step 7: Report

After all in-scope epics are processed, summarise:

- **Scope** — which epics were processed (and which were filtered out)
- What was produced (table of epics and their artefacts)
- **Execution waves** — final wave assignments showing which items can be implemented in parallel by `/feature-team`
- **Parallelism refinements vs. kickoff's map (if any)** — list any epic pairs kickoff marked `Parallelisable with` that file-level analysis revealed as conflicting (and the converse: pairs serialised in the plan that LLDs prove are actually parallel-safe). Recommend a plan patch where appropriate.
- Any items skipped and why
- Any open questions or ambiguities found during design
- Suggested next step: human reviews the artefacts, then `/feature` or `/feature-team` implements

**Stop here.** The user reviews all artefacts before implementation begins.

## Guidelines

- **Do not implement.** This skill produces design artefacts only — no production code.
- **Do not invent requirements.** If the plan is ambiguous, flag it and ask rather than assuming.
- **Reference, do not duplicate.** Link to existing design docs and ADRs rather than restating them.
- **British English** in all documentation.
- **Keep artefacts proportional.** A one-line bug fix with existing LLD coverage needs only BDD specs in the issue. A small feature without LLD coverage needs an LLD section. Do not over-engineer the design for trivial items.
- **Respect existing decisions.** Read ADRs before proposing new ones — the decision may already be recorded.
- **Repo docs are source of truth.** GitHub issue bodies are convenient but not version-controlled. Every item that `/feature` will implement must have its design detail (fix approach, BDD specs, acceptance criteria) traceable to a file in `docs/`. Issue bodies reference these docs — they do not replace them.
- **Check before creating.** Always check for existing issues and design docs before creating new ones. Duplicate artefacts cause confusion.
- **API route internal decomposition and reused helpers are `/lld`'s responsibility.** The `/lld` skill's template and self-critique pass already enforce API route internal decomposition, kb-based reused helpers tables, and no-raw-queries rules. `/architect` delegates to `/lld` — do not duplicate these rules here.
- **MCP tool handlers stay thin.** Tool handlers should parse inputs, delegate to a service function, and return. Business logic, store calls, and embedding work belong in services or store wrappers — not in the handler body. The LLD for any new tool must name the handler, the service function it delegates to, and the store/embedding boundaries it crosses.
- **One LLD per epic.** Each epic gets a single LLD file (`lld-<epic-id>-<short-name>.md`). Tasks within the epic are sections of that LLD, not separate files.
