---
name: lld-sync
description: Sync the LLD back to the implementation after a feature is complete. Reads the design spec and the actual code, produces a structured diff, and updates the LLD in-place. Run after implementation, before feature-end.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, Skill, TodoWrite
---

# LLD Sync — Post-Implementation Design Feedback Loop

Updates the Low-Level Design document to reflect what was actually built, capturing implementation
learnings back into the design so future features start from accurate specs.

**Run after implementation is complete, before `/feature-end`.**

This is the symmetric complement to `/lld` (which generates design _before_ implementation). Together
they close the Theory Building loop: design informs implementation, implementation corrects design.

## Arguments

`$ARGUMENTS` is the issue number (e.g., `52`). If omitted, infer from the current branch name
(`feat/<slug>` → look for `Closes #N` in the most recent PR or branch commits).

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing mode detection, the delta analysis categories, or the manifest update logic.

## Process

Check the issue's labels: `gh issue view <number> --json labels`.

- **Refactor mode** if the issue body has a `## Trigger` section (per the cross-cutting-refactor-lld-discipline ADR), or if the issue has `kind:refactor` label. Behaviour is preserved by definition (no Rev N blocks). The process is **directive** — apply the sweep targets the issue body lists.
- **Feature mode** otherwise. Process is **reactive** — analyse what was built vs spec; existing behaviour.

Refactor-mode adjustments per step are tagged **[refactor]**. When unmarked, both modes share the step.

### Step 1: Gather context

1. Determine the issue number from `$ARGUMENTS` or from `git log --oneline -10 | grep -oP '#\d+'`.
2. Read the issue body: `gh issue view <number>`.
   - Extract `## Design references` (plural — multi-target list, refactor task bodies). If absent, fall back to legacy `## Design reference` (singular — feature tasks predating the refactor ADR) or scan for an inline LLD reference (e.g. `§2.2 Task 3`).
   - Extract the **acceptance criteria** and **BDD specs**.
   - **[refactor]** Read every listed LLD anchor; the task body's `## Design references` enumerates all sections this PR sweeps. Treat the list as exhaustive.
3. Identify which LLD file covers this issue:
   - Look for LLD files: search `docs/design/v*/lld-*.md` (new versioned), `docs/design/lld-*.md` (legacy flat), and `docs/design/lld-phase-*.md` (legacy phase).
   - Read the relevant section (use Grep to find the task number/title).
4. Read the PR body for this branch:
   - `gh pr view --json body -q '.body'` (or `gh pr view <number> --json body -q '.body'`).
   - Look for a `## Design deviations` section — these are deliberate departures from the LLD
     that the implementer documented during `/feature-core` Step 3b.
   - Each deviation note explains what the LLD recommended, what was built instead, and why.
     Use these as the primary source for **Corrections** in Step 2.
5. Read all source files created or modified by this feature:
   - Use `git diff --name-only main...HEAD` to get the changed file list.
   - Read each `src/` file that changed.
6. Read the test file(s) to understand what behaviour was actually tested.

### Step 2: Analyse the delta

**[refactor]** Refactors are behaviour-preserving by definition; no Corrections expected (and no Rev N blocks). Skip the four-category analysis. Instead verify:
- **Additions match spec:** the new shared component (interface, factory, mock helper) matches the refactor LLD's "Interface and types" / "Mock helper API" sections.
- **Files were edited:** every entry in the issue body's `## Files to create/modify` was actually touched by the PR (use `git diff --name-only main...HEAD`).
- **Sweeps were applied:** every LLD section in `## Design references` was edited in this PR.
- If a Correction is genuinely needed (impl diverged from refactor LLD spec): treat as a feature-mode Correction and proceed with Step 3 — but flag this in the sync report; refactor PRs that diverge from their LLD spec usually indicate a design issue to retro.

**[feature]** Compare what the LLD specified vs what was actually built. For each category, list findings:

**Additions** — things built that were not in the LLD spec (new files, new patterns, new decisions):
- Capture the _why_ from commit messages, PR description, or code comments.

**Corrections** — things the LLD got wrong that were fixed during implementation:
- Wrong client types, incorrect file structure, missing constraints, etc.
- These are the most important — they indicate where the design was inadequate.

**Omissions** — things the LLD specified that were not built (deferred, descoped, or superseded):
- Note whether each is deferred to a future issue or permanently dropped.

**Confirmations** — things the LLD specified that were built exactly as designed.
- Only note these if they are non-obvious (worth confirming for future readers).

### Step 3: Update the LLD

**[refactor]** Edits are mechanical (file path renames, function renames, internal-decomposition block updates) per the issue body's `## Design references`. DO NOT add Rev N blocks; refactors don't introduce them. DO NOT auto-modify `docs/design/lld-refactor-*.md` — those are spec artefacts the implementing PR followed; they are managed at refactor-LLD lifecycle time (Step 3d). For each existing LLD section listed in `## Design references`: open it, find the prose / code blocks / file lists that referenced the old path/name/structure, replace with the new (post-refactor) form. Preserve `<a id="LLD-...">` anchors per ADR-0026.

**[feature]** Edit the LLD in-place. Be surgical — do not rewrite sections that were correct.

For each Correction and Addition:
1. Update the relevant prose, code snippet, or file structure list.
2. Add a callout where the spec was materially wrong, using this format:
   ```
   > **Implementation note (issue #N):** [What was actually built and why it differed from the spec.]
   ```
3. For file structure changes, update the directory listing.
4. For type/interface changes, update the function signatures or type definitions.

For each Omission:
1. Mark deferred items with: `_(deferred → issue #N)_` or `_(descoped)_`.
2. Do not delete them — future readers benefit from knowing what was considered.

**Stable LLD anchors (per ADR-0026):**

- **Preserve** every existing `<a id="LLD-<epic-id>-<section-slug>"></a>` anchor when editing a
  Part B section in-place. Anchors are stable identifiers — moving or renaming them breaks links
  from the coverage manifest and any external reference.
- If a Correction or Addition introduces a **new** Part B section, emit a new anchor for it
  using the format `LLD-<epic-id>-<section-slug>` derived from the LLD file name (`lld-<epic-id>-<short-name>.md`)
  and the new section heading.
- If a section is removed via Omission, leave the anchor in place above the deferred/descoped
  marker so the manifest entry still resolves; do not delete the anchor.

### Step 3a: Update the knowledge base

The kb is a living set of documents. `/lld-sync` updates the helper catalogue (`kb/architecture.md`) and anti-patterns (`kb/anti-patterns.md`) based on implementation learnings.

**[refactor]** The refactor LLD's "kb entry" subsection enumerates the entries this PR should land in the kb (typically: one row for the new shared component in `kb/architecture.md`, plus one or more anti-pattern entries in `kb/anti-patterns.md`). Verify each is present. If absent (e.g. `/feature` skipped the kb edit), add verbatim from the LLD. If already present (e.g. the implementing PR added them), no-op. Refactor mode is directive — do not invent entries beyond what the refactor LLD specifies.

**[feature]** Run these reactive checks:

1. **New reusable helper introduced.** If the implementation added a new exported symbol in a shared module (see `kb/file-map.md` for project-specific paths) that future features should reuse, add a one-line entry to `kb/architecture.md` (API composition pattern section). Bar for inclusion: would future LLDs cause drift if they re-implemented it? If yes, add it. If not (purely local utility), skip.
2. **Re-implementation pattern uncovered.** If a Correction in Step 2 was caused by the LLD inlining a query or behaviour that an existing reusable helper already covered, append the inlined-pattern → helper mapping to `kb/anti-patterns.md` (Helper reuse section). This prevents the same drift on the next epic.
3. **Reusable helper renamed or retired.** If the implementation renamed an exported reusable helper, update the entry in `kb/architecture.md`. If a helper was deleted, remove the entry — keep the kb a true reflection of the codebase.
4. **No changes needed.** If the diff did not touch any reusable surface, skip — do not edit the kb for cosmetic reasons.

When the kb changes, mention it in the sync report (Step 4).

### Step 3b: Update the coverage manifest

If a coverage manifest exists for this epic (at `docs/design/v*/coverage-<epic-slug>.yaml` per
ADR-0036 or `docs/design/coverage-<epic-slug>.yaml` legacy flat), update the entries that match
the LLD sections you just changed:

- For any section touched by a **Correction** (the spec was wrong and got rewritten), flip the
  matching entry's `status` from `Implemented` (or `Approved`) to `Revised`.
- For a **new** Part B section added under an Addition, append a new manifest entry pointing
  at the new anchor with `status: Revised` and the implementing files in `files:`.
- For each entry whose `### Story <REQ>` block was just deleted from a `## Pending changes — Rev N`
  section (Step 3c below), set `lld_revision` to the revision number that just shipped (e.g. `r2`)
  and flip `status` to `Implemented`. This is the only place `lld_revision` is written.
- Do **not** touch `files:` for entries unrelated to this issue — `/feature-end` owns the
  initial population.

Manifest ownership summary (for reference):

| Skill | Writes | Flips status to |
|-------|--------|-----------------|
| `/lld` | Creates manifest, one row per REQ- anchor, empty `files`, `status: Approved` | `Approved` |
| `/feature-end` | Populates `files:` after merge | `Implemented` |
| `/lld-sync` | Updates entries for sections changed by Corrections/Additions | `Revised` |
| `/lld-sync` | Removes shipped Rev X blocks; bumps `lld_revision` for those entries | `Implemented` |

Update the LLD's Document Control table:
- Bump `Version` (e.g., `0.1` → `0.2`).
- Change `Status` from `Draft` to `Revised` (or `Revised` → `Revised v2`).
- Add a `Revised` row: `| Revised | [today's date] | Issue #N |`

### Step 3c: Remove shipped Rev X blocks

After reconciling Part B against shipped code, locate any `## Pending changes —
Rev N` sections. For each `### Story <REQ>` block in those sections whose REQ
matches an entry Step 3b just touched:

- If the story is **completely new** (no existing Part B section in the body),
  promote the addendum block to a permanent Part B section first — refined to
  reflect what shipped, with a stable `<a id="LLD-<epic-id>-<story-slug>"></a>`
  anchor derived from the REQ. Update the manifest entry's `lld:` to point at
  the new anchor.
- Then delete the block from the `## Pending changes` section.

Leave unrelated blocks intact — partial sync is allowed. If a `## Pending
changes — Rev N` section becomes empty after deletions, delete the section
heading and its leading separator (`---`) too.

Step 3b handles `lld_revision` and `status` for both cases.

### Step 3d (refactor mode only): Refactor LLD lifecycle at epic close

If the issue is in refactor mode AND its parent epic (per `## Parent epic` in the body, or via `gh issue view <epic_n>`) has `epic` + (`kind:refactor` or `kind:lld-sweep`) labels AND **the parent epic's task checklist is now fully closed** (every `- [x]` line links to a closed issue), handle refactor LLD retirement per the cross-cutting-refactor-lld-discipline ADR §"Refactor LLD lifecycle". Otherwise (epic still has open tasks), skip this step.

If retirement applies:

1. **Verify durable references exist:**
   - `kb/architecture.md` entry for the new shared component (added by the foundation task).
   - `kb/anti-patterns.md` entries for any patterns the refactor eliminated (added during implementation).
   - Each consumer LLD listed in the refactor LLD's "LLD sweep targets" has a "Reused helpers — DO NOT re-implement" row pointing at the new component (added during T2-Tn migrations).
   - Surface any missing reference to the user as a blocker before proceeding.

2. **Prompt the user for retirement mode:**
   - **Retire (default):** delete the refactor LLD file. Pure consolidation refactors fit this — contract lives in source, mock helper in test util, kb/architecture.md has the entry, consumer LLDs got their reused-helpers rows.
   - **Promote to ADR:** the refactor LLD contains durable architectural rationale (alternatives considered, load-bearing decisions). Spin out a new ADR with the durable content; then delete the refactor LLD.
   - **Persist as canonical component LLD:** rare. The shared component is non-trivial with ongoing design questions. Rename `lld-refactor-<slug>.md` → `lld-component-<slug>.md`; strip transitional sections (Step order, Per-task decomposition, BCA results); keep durable ones (Interface, types, ongoing rationale).

3. **Apply the chosen mode.** Mention in the sync report (Step 4).

This step does not apply in feature mode.

### Step 4: Produce the sync report

Print the report below to the agent's output (stdout). **`/feature-end` Step 2 picks it up from the conversation context and pastes it verbatim into the session log under a `## LLD Sync report` heading.** Do not write to a file yourself — single-writer model, `/feature-end` owns the session log.

```
## LLD Sync — Issue #N: [title]

### Corrections (spec was wrong)
- [item]: [what the spec said] → [what was built] — [why]

### Additions (not in spec)
- [item]: [what was added and why]

### Omissions (in spec but not built)
- [item]: [deferred/descoped]

### Confirmations (notable)
- [item]: built as specified

### LLD updated
File: docs/design/v{N}/lld-<epic-id>-<short-name>.md §B.N (or legacy flat path)
Version: 0.1 → 0.2
```

If there are no Corrections or Additions (spec was fully accurate), say so explicitly — this is
valuable signal that the LLD process is working well.

## Guidelines

- Do not change the LLD's overall structure or rewrite sections that were correct.
- Do not add opinions or recommendations — only record facts about what was built.
- If the LLD covered a section that hasn't been implemented yet (future phase), do not touch it.
- If the issue has no LLD reference, note this and scan for the most relevant LLD section by
  matching file paths and function names.
- Use British English in all documentation.
- The goal is accuracy, not coverage — a short, correct LLD is better than a long, wrong one.
