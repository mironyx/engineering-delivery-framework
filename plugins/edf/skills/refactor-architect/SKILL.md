---
name: refactor-architect
description: Decompose a refactor (smell, tech debt, audit finding, or freeform intent) into well-formed GitHub issue(s). Produces one task issue by default, or an epic + N task issues for refactors too large for a single PR. The parallel of /architect for refactor work — same decomposition discipline, reuses /architect's GH-issue-body templates and gh-issue-manager dispatch; only the refactor-specific bits live here. Does not author new LLDs (refactors update existing ones via the sweep mechanism). Use when there is a structural smell, duplicated pattern, contract impedance, or tech debt that needs filing — not when there is a feature to build (use /architect) or a bug symptom to investigate (use /bug).
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite
---

# Refactor-Architect — Refactor Decomposition

Entry point for the refactor lifecycle defined in the cross-cutting-refactor-lld-discipline ADR. Takes a smell description, audit finding, or freeform refactor intent and produces well-formed GitHub issue(s) ready for `/feature`.

**Model:** Use Opus (latest Claude model). Pass `model: "opus"` for any sub-agents. Exception: leave `edf:gh-issue-manager` on its pinned (smaller) model.

## What this skill adds over /architect

This skill **reuses** `/architect`'s GitHub-issue-body templates, agent dispatching, and board placement. It defines **only** the refactor-specific bits — different inputs, different discovery (find affected files and LLDs from a smell instead of from a plan), and a few refactor-specific issue-body sections.

### Where things live (the word "template" is overloaded — disambiguating)

`/architect` itself **delegates LLD authoring to `/lld`** but owns the GH-issue-body templates that this skill reuses. Concrete map of who owns what:

| Artefact | Owned by | Where |
|----------|---------|-------|
| LLD document structure (Document Control, Part A, Part B) | `/lld` | `template.md` next to `/lld`'s SKILL.md |
| LLD task entry format (`### Task N: [Short title]` block inside an LLD's `## Tasks` section) | `/lld` | `/lld` SKILL.md Step 3 |
| **GH issue task body template** | `/architect` | `/architect` SKILL.md Step 4 sub-step 3 |
| **GH epic body template** | `/architect` | `/architect` SKILL.md Step 4 sub-step 3 |

`/refactor-architect` does **not** author new LLDs — refactors update existing ones via the sweep mechanism (Step 3). So `/lld`'s templates are not relevant here. Only the GH-issue-body templates from `/architect` (the bottom two rows) are reused.

### Delta from /architect

| Concern | `/architect` (canonical) | This skill |
|---------|------------------------|-----------|
| Input | Plan section / requirements doc | Smell description, file path(s), audit finding, or freeform intent |
| Source-file discovery | Plan declares files | Skill greps the codebase from the smell |
| LLD handling | Authors new LLD sections (via delegation to `/lld`) | Discovers existing LLD sections to **sweep** (with prose-reference caveat — see Step 3); does not author new LLDs |
| GH issue task body | Owns the canonical template | Reuses `/architect`'s template + refactor-specific section deltas (see Step 6) |
| GH epic body | Owns the canonical template | Reuses `/architect`'s template + uses `kind:lld-sweep` label |
| Decomposition | Per-plan-section, see `/architect` Step 2b | Default one issue; escalate by PR size (see Step 4) |
| Issue creation | `edf:gh-issue-manager` (batch) / `${CLAUDE_PLUGIN_ROOT}/bin/gh-create-issue.sh` (single) | Same — see Step 6 |
| Board placement | Todo column via `${CLAUDE_PLUGIN_ROOT}/bin/gh-create-issue.sh` / agent | Same |

If a behaviour isn't named below, it inherits from `/architect`. Maintenance happens in one place.

## When to invoke

Per the cross-cutting-refactor-lld-discipline ADR §"Triggers — when the lifecycle starts":

1. **Smell 1** — pure-translation helper (an adapter that exists only to convert between two shapes, no domain logic).
2. **Smell 2** — pattern already lives elsewhere (the DB query / fetch / conversion you're about to write already exists in ≥ 1 sibling files).
3. **Smell 3** — Boundary Contract Audit finding from `/lld`.
4. **Manual** — human spots tech debt and runs this skill directly.

Skills do not invoke this skill automatically. The human is the router (per the ADR §"The refactor lifecycle").

## Usage

Inputs combine freely. The recommended shape is **file path(s) + textual description** in the same call.

- `/refactor-architect src/lib/prcc/scoring-path.ts "DB queries scattered across PRCC files; should live in a repository module"` — recommended: file(s) + description.
- `/refactor-architect "scoreAnswers takes array index but PRCC has UUIDs — adapter exists only to bridge"` — freeform; skill greps to identify affected files.
- `/refactor-architect src/lib/prcc/scoring-path.ts` — file only; skill asks for the smell description.
- `/refactor-architect --finding "<paste BCA row from /lld>"` — audit handoff.
- `/refactor-architect #N` — refine an existing placeholder refactor issue.

## Process

Steps 1–5 are refactor-specific. Step 6 reuses `/architect`'s machinery; Step 7 is the stop point.

### Step 1: Parse input and orient

Inputs may **combine**. Identify each component present:

- **File path(s)** — one or more starting points.
- **Free-form description** — the smell in the user's own words.
- **Audit finding** — pasted Boundary Contract Audit row with "Generalise first" outcome.
- **Issue number** — refine an existing placeholder issue.

State the smell in one sentence and identify which trigger category it matches. If ambiguous, ask before continuing.

### Step 2: Identify affected source files

Build a confirmed list of source files the refactor will touch:

- File named in input → include it; ask whether siblings are also affected.
- Function/symbol described → grep for definitions and call sites.
- Pattern described (e.g. "scattered DB queries") → grep, present matches, ask which are in scope.

Output: explicit list of source-file paths.

### Step 3: Discover affected LLD sections

For each affected source file, grep `docs/design/lld-*.md` for references to:
- The file path itself.
- The symbols (functions, types, classes) it exports.

**Prose-reference caveat (specific to refactor work):** file-path grep alone misses references buried in prose — deviation notes ("Implementation note: X function does Y"), cross-references, and reused-helper descriptions. After the grep, read each match and look one or two paragraphs around it for prose that names the affected symbols. These prose references are exactly what refactor sweeps must update; the cross-cutting-refactor ADR was motivated in part by their being missed.

For each LLD anchor found, capture:
- The LLD file and anchor (`#LLD-<slug>`).
- Whether the section names the file in a "Files to create/modify" list.
- Prose references the refactor will invalidate.
- Any "shared X reused" claims that warrant a Boundary Contract Audit update.

Also consult `docs/design/coverage-*.yaml` and `docs/design/kernel.md` (or equivalent shared-helpers doc).

Output: full **Design references** list — `(LLD anchor)+ (kernel-doc row)*`.

### Step 4: Decide decomposition

**Default — one issue.** Most refactors fit in one PR and produce one issue (`kind:task`). The implementing PR sweeps every affected LLD inline.

**Escalate to epic + N tasks only when warranted.** Use judgement, not a count threshold. Signals that warrant escalation:
- Estimated PR diff size > ~300 lines (production + tests + LLD edits).
- Natural seam between consumers — each independently testable / shippable.
- Migration would otherwise leave the codebase mid-state mid-PR.

LLD count is a useful proxy (more LLDs usually = more diff) but not the bright line. Most refactors here touch 3–4 LLDs and remain one issue.

Present the decomposition decision **with rationale** to the user. Wait for confirmation. The user may collapse a proposed epic back into one issue, or expand a single issue into multiple if seams reveal themselves.

### Step 5: Author refactor-specific design content

Two cases:

**Case A — refactor introduces a new shared component** (repository module, generic engine function, helper consumed by ≥ 2 files).

Produce these refactor-specific artefacts (used by Step 6 to populate the issue body):

1. **Boundary Contract Audit table** — format defined in the cross-cutting-refactor-lld-discipline ADR §"Boundary Contract Audit format". Do not duplicate the table format here; reference the ADR.
2. **TypeScript interface signature** — full method signatures with parameter and return types. Copy from source where consumers exist; invent only where genuinely new.
3. **DTOs / row shapes** — re-export current shapes by default; reshape only with explicit reason.
4. **Mock helper API** — recommend a plain factory `make<Name>(overrides?: Partial<Interface>)` returning vitest-spied stubs.
5. **Step order within the implementing PR** — e.g. "interface → implementation → mock helper → migrate consumer 1 → migrate consumer 2 → grep no-old-pattern → sweep LLDs". Without this, `/feature` invents structure.

**Case B — refactor is pure removal of duplication** (no new shared component). Skip 1–4. Note in the issue body: "Pure removal/consolidation; no new abstraction introduced."

### Step 6: Author bodies and create issues

This step **reuses `/architect`'s templates and creation machinery** with refactor-specific deltas listed below.

#### Task body — inherit from /architect's "Task body template"

See `/architect` SKILL.md §"Task body template". Apply these deltas for refactor tasks:

- Replace `## Stories` → **`## Trigger`** — name the smell category (Smell 1/2/3/Manual) and one-line detail.
- Replace `## Design reference` (singular) → **`## Design references`** — anchor list of LLD sections the implementing PR will sweep (from Step 3).
- Omit `## HLD reference` — refactors don't reference HLDs.
- Omit `## Parent epic` if the refactor is a standalone task (not in an epic).
- Add `## Boundary Contract Audit` — Case A only, format per the cross-cutting-refactor ADR.
- Add `## Interface and types` — Case A only (Step 5.2–3 output).
- Add `## Mock helper` — Case A only (Step 5.4 output).
- Add `## Step order within the implementing PR` — Case A only (Step 5.5 output).
- Acceptance criteria must include the ADR sweep checklist: `Every LLD section in **Design references** above is updated in the same PR`.

All other fields (`## What`, `## Acceptance criteria`, `## BDD specs`, `## Files to create/modify`, `## Layer`, `## Depends on`) inherit verbatim from `/architect`'s template.

#### Epic body (only when escalated) — inherit from /architect's "Epic body template"

See `/architect` SKILL.md §"Epic body template". Apply these deltas for refactor epics:

- Title prefix: `Epic: refactor — <title>` (instead of `Epic: V<N> E<X>.<Y>`).
- Replace `### Requirements`, `### HLD reference`, `### Stories` → single **`### Trigger`** section naming the smell.
- `### Design references` is cumulative across all child tasks (each child task body has its subset).
- `### Related ADRs` always includes the cross-cutting-refactor-lld-discipline ADR.
- Labels: `epic` + `kind:lld-sweep` (instead of feature-area labels).
- All other fields (`### Tasks`, `### Dependency graph`, `### Execution waves`, `### Exit criteria`) inherit from `/architect`.

#### Issue creation — reuse /architect's machinery verbatim

- **Single task issue** → `${CLAUDE_PLUGIN_ROOT}/bin/gh-create-issue.sh` (deduplicates and adds to board). See `/architect` for invocation form.
- **Epic + tasks (batch)** → dispatch the `edf:gh-issue-manager` Agent with the `epic_number`, `tasks: [...]`, and `epic_body` payload. See `/architect` SKILL.md §"Step 4 sub-step 3" for the exact agent prompt format. Use `T1`, `T2`, … placeholders in cross-task `Depends on` references; the agent substitutes real numbers.

Board placement (Todo column) is handled by `${CLAUDE_PLUGIN_ROOT}/bin/gh-create-issue.sh` and `edf:gh-issue-manager` automatically.

### Step 7: Stop

Implementation is `/feature`'s job. Do not write code. Do not invoke other skills.

Report what was created and the recommended next step:

> "Created refactor task issue #N (or epic #N + tasks #M..#M+k). Next: review the issue body, then run `/feature` on the first task."

## Guidelines

- **Reuse, don't duplicate.** Templates, agent dispatching, and board placement live in `/architect`. This skill carries only refactor-specific deltas. If a delta would mostly restate `/architect`, point at `/architect` instead.
- **Do not implement.** This skill produces issues only.
- **Do not invoke other skills.** Skills surface findings; the human routes work (per the cross-cutting-refactor ADR).
- **Lock symbol names at issue-creation time.** Method names, interface names, file paths in the issue body are the contract for `/feature`. They cannot drift between issue creation and implementation.
- **British English** in all documentation and issue bodies.
- **Default to one issue.** Escalation to epic+tasks is the exception, not the norm.

## Project conventions

This skill inherits the project conventions documented in `/architect` SKILL.md (LLD path patterns, coverage manifests, kernel doc, project board scripts, label set, `edf:gh-issue-manager` agent). It adds only:

- **ADR reference:** The cross-cutting-refactor-lld-discipline ADR defines the refactor lifecycle, smells, Boundary Contract Audit format, and decomposition guideline. When porting to a project that records the refactor lifecycle in a different ADR, re-anchor accordingly.
- **Label:** `kind:lld-sweep` for refactor epics. Create on first use if not present.
