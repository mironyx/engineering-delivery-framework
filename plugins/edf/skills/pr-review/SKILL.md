---
name: pr-review
description: Review code changes for bugs, design principles, contract adherence, framework best practices, and design conformance. Use before committing (/pr-review) or on a PR (/pr-review 123). Adaptive: 1 agent for small diffs, 2 agents for large diffs. Agent B (framework patterns) only runs when framework files changed.
allowed-tools: Read, Write, Bash, Glob, Grep, Agent, Skill, TodoWrite, WebSearch
---

# PR Review

Two modes:

- `/pr-review` — reviews local uncommitted changes (`git diff HEAD`)
- `/pr-review <pr-number>` — reviews a pull request; posts the result as a PR comment

**Cost-adaptive architecture.** Agent count scales with diff size:
- Diff < 150 lines → **1 agent** (Quality, covering all checks)
- Diff ≥ 150 lines → **2 agents** (Quality + Design Conformance in parallel)
- Agent B (framework patterns) only runs if framework or config files changed

---

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing the cost-adaptive threshold, agent count, or agent prompt structure.

## Process

### Step 1: Gather context

Determine mode from `$ARGUMENTS`:

- Number present → **PR mode**
- Otherwise → **local mode**

Run ALL of the following in parallel:

1. **PR mode:** `gh pr diff <number>` — full diff, untruncated.
   **Local mode:** `git diff HEAD` (fall back to `git diff --cached` if empty).
2. **PR mode:** `gh pr diff --name-only <number>`.
   **Local mode:** `git diff --name-only HEAD`.
3. Read `CLAUDE.md` (root).
4. Read the project's dependency manifest if one exists (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, etc.) — capture exact versions of direct dependencies. Skip if none present.
5. Read `kb/architecture.md` — the project's architecture rules. Pass its full contents to the review agent(s) as `{{ARCHITECTURE_RULES}}`. Skip if absent.
6. Read `kb/anti-patterns.md` — the project's anti-pattern checklist (framework-specific patterns, language conventions, helper-reuse rules). Pass its full contents as `{{ANTI_PATTERNS}}`. Skip if absent.
7. Pass `kb/architecture.md` contents (already read in step 5) as `{{KB_ARCHITECTURE}}` — it doubles as the reusable helper catalogue. Skip if the file has no API composition pattern entries (helper-reuse checks rely on `{{ANTI_PATTERNS}}` content instead).

If diff is empty, print "Nothing to review — diff is empty." and stop.

### Step 2: Classify the review

From the gathered data, compute:

- `DIFF_LINE_COUNT` — total lines in the diff (added + removed)
- `CHANGED_FILES` — source files added or modified (not deleted). Treat any path under the project's source root as a source file; `kb/conventions.md` may name a `test-suffix` to recognise tests.
- `EXTERNAL_SURFACES` — every surface the diff codes against whose contract is defined
  outside this repo, each with its pinned version. This is broader than the dependency
  manifest: a protocol or wire-format specification (MCP, OAuth, a webhook payload format)
  has no manifest entry but is still an external surface, and is the case most likely to be
  implemented from stale recall precisely because there is no version to grep for.
  - **Preferred source:** the `## External Surfaces` table in Part B of the LLD linked from
    the issue. It is authoritative — it carries the pinned version, the doc URL, and the
    `New to repo` flag the design agreed on.
  - **Fallback** (no LLD, or no table): derive it. Take direct (not dev) dependencies from
    the manifest that the changed files import, and add any protocol/spec surface evident
    from the diff itself — handshake or capability negotiation, a versioned wire format, a
    dated spec revision in comments or constants. Capture exact versions from the manifest
    read in Step 1.4; for spec surfaces with no manifest entry, capture whatever revision
    the diff states, or `unpinned` if it states none.
  - Cap at 5 surfaces, most central to the diff first.
- `NEW_SURFACES` — the subset of `EXTERNAL_SURFACES` used here for the first time anywhere
  in this repo. Read it from the table's `New to repo` column when present; otherwise grep
  the repo outside the diff for prior use of each surface. First use means there was no
  in-repo precedent for the author to imitate, so the code was written from training recall.
- `PATTERNS_NEEDED` — true if EITHER:
  - `NEW_SURFACES` is non-empty — **the primary trigger.** New integrations are where recall
    is unanchored and where a spec revision the model never saw gets silently invented.
  - The changed file list touches the dependency manifest or lockfile, an `.env` / `.env.*`
    file, or a framework config file (`*.config.ts`, `middleware.ts`, `next.config.*`,
    `vite.config.*`, build config) — judged against the project's stack.

  Note what this deliberately does **not** trigger on: ordinary changes to code that uses a
  surface already established in the repo. There the surrounding code is the anchor, research
  is mostly wasted spend, and `{{ANTI_PATTERNS}}` already runs for free on every review. The
  gate exists to spend on first contact with a surface — once per surface, not once per PR.

Then fetch in parallel:
- **Issue body:** extract linked issue from PR body (`Closes #N`, `Fixes #N`, `Resolves #N`).
  Fetch `gh issue view <N>` for acceptance criteria and design doc paths. (PR mode only)
- **Commits:** `gh pr view <number> --json commits` (PR mode) or `git log main..HEAD --oneline`
  (local mode).

### Step 3: Launch agents (count depends on diff size)

---

#### If DIFF_LINE_COUNT < 150: launch ONE agent

**Agent Q — Quality (all checks, single agent)**

If `PATTERNS_NEEDED` is true, launch **Agent B alongside Agent Q in the same message** (two
agents). A small diff is not a safe diff: a first integration against a protocol spec can be
eighty lines and still be written entirely from recall. Diff size decides how the *quality*
checks are split; `PATTERNS_NEEDED` alone decides whether surface research happens.

**Tools:** Read, Bash, Glob, Grep

```
You are a senior engineer doing a focused code review on a small diff. Cover all areas
in one pass: bugs, security, code justification, maintainability, design principles,
CLAUDE.md compliance, framework anti-patterns, and design conformance.

## Part 1: Bugs (block if found)
- Logic errors, off-by-one, null dereferences, incorrect error handling
- Missing awaits on async calls
- Race conditions or incorrect state transitions
- Silent catch blocks that discard errors without at least a console.error — always a bug

## Part 1b: Security (block if found)
- Injection (SQL/NoSQL/command/template)
- AuthZ bypass — missing ownership/RLS on reads or writes
- Secrets in code, logs, URLs, or comments
- SSRF on server-side fetch of client-supplied URLs
- Insecure defaults or missing security headers
- Error leakage — stack traces, schema, or tokens in responses

## Part 2: Code justification (block if severe)
- Solves the stated problem without over-engineering — nothing beyond the current task?
- Single-use helpers or abstractions? Complexity replaceable by simpler alternatives?

## Part 2b: Maintainability / Boy Scout (block if severe, warn for nits)
- Dead code introduced (unused imports, vars, functions)
- Duplication created instead of reusing an existing helper
- Touched functions left harder to understand than they were (naming, structure) — a broken window opened, not left
- **Metric-driven rewrites:** when a change is motivated by a complexity/score gate, verify
  the rewrite didn't hide explicit intent (e.g. an explicit override branch flattened into
  a helper's null-guard). Flag as **warn**.
Scope: diff only — edf:diag owns whole-file metrics.

## Part 3: Design principles (block if severe)
The project's architecture rules are in `{{ARCHITECTURE_RULES}}` (from `kb/architecture.md`).
Apply each rule literally. If `{{ARCHITECTURE_RULES}}` is empty, skip this part.

Also apply the universal SOLID heuristics:
- Single Responsibility: does each new function/module do one thing?
- Dependency Inversion: dependencies injected, not imported as concrete implementations.
- Interface Segregation: no overly broad interfaces forced on callers.
- Open/Closed: a change should not require modifying multiple unrelated modules.
- Functions over classes unless state genuinely requires a class.

## Part 4: CLAUDE.md compliance
Only check these:
- No `Co-Authored-By` trailers in commit messages (block)
- Every commit uses conventional format (`feat:`, `fix:`, etc.) AND references an issue (warn)
- Any language-specific compliance rule listed in `{{ANTI_PATTERNS}}` under "Language conventions" (severity per the rule).

## Part 5: Design conformance (if design references exist)
For each changed source file, look for a header comment in the form:
  Design reference: <path> §<section>
(use the project's comment syntax)

If found:
1. Read the referenced doc section.
2. Extract every function name specified in that section.
3. For each function in the diff NOT in the designed list:
   - No justification comment → **block** (add a `Justification:` comment or update the LLD)
   - Justification comment exists → **warn**
4. Exported/public unspecified functions are always **block** regardless of justification.
5. **Deviation review:** When the PR body documents a deviation, diff the LLD's prescribed
   form at each call site against the implemented form. Flag form divergence as **warn**
   (`"type": "deviation-form"`) unless the deviation note explains why the form changed.
   "Semantics identical" is not a justification — the note must state the concrete reason.

## Part 6: Helper reuse (block if a reusable helper is re-implemented)

If `{{KB_ARCHITECTURE}}` is non-empty, it is the curated list of reusable helpers and the
anti-patterns the project exists to prevent. The "Helper reuse" section of `{{ANTI_PATTERNS}}`
lists inline-pattern → reusable-helper mappings. Apply these checks against the diff:

1. **Anti-pattern list** — for each bullet under "Helper reuse" in `{{ANTI_PATTERNS}}`,
   scan the diff for the inline pattern. Each match → **block** with `"type": "kernel-reuse"`.
   Quote the offending code and name the reusable helper that should have been used.

2. **Symbol table reuse** — for each entry in `{{KB_ARCHITECTURE}}`'s symbol tables, if the diff
   introduces a function that does the same job (same inputs/outputs, same domain) without
   delegating, **block**. Heuristic: matching name fragments, matching data targets (table
   names, endpoints), or matching return shapes.

3. **LLD kb-reference check** — if the diff includes or modifies an LLD under
   `docs/design/` that touches a topic covered by `{{KB_ARCHITECTURE}}` but lacks a
   "Reused helpers — DO NOT re-implement" table naming the reusable helpers it depends on →
   **warn** with `"type": "kernel-reuse"`.

4. **Redundant DB round-trips** (`"type": "db-efficiency"`, **block** if duplicated, **warn**
   if combinable) — within a single request handler / page render / service call:
   - Two queries against the **same row or row-set** (same target + same predicate) that
     could be a single query → **block**. Capture the result once and pass it down.
   - Two queries against **different targets** that the data layer could fetch in one call
     (e.g. an embedded select / join / single GraphQL query) → **warn**.
   - N+1 patterns (a loop where each iteration issues a query) → **block**. Fix: a single
     batched query, a join, or a single GraphQL request.

5. **Chained calls that could collapse** (`"type": "db-efficiency"`, **warn**) — when a
   handler fetches multiple related resources via chained data-layer calls that the data
   layer could collapse into one (e.g. embedded select instead of chained REST calls,
   GraphQL instead of N+1 queries, a batch endpoint instead of a fan-out). Flag the
   chain. Do not flag a single query.

If `{{KB_ARCHITECTURE}}` is empty AND the "Helper reuse" section of `{{ANTI_PATTERNS}}` is empty,
skip Part 6 entirely.

## Part 7: Project anti-patterns (always check, no web search)
Apply every check listed in `{{ANTI_PATTERNS}}`. Each entry states its own severity. Skip
this part only if `{{ANTI_PATTERNS}}` is empty.

## What NOT to report
- Pre-existing issues not made worse by this diff
- Anything CI catches automatically (lint, types, tests)
- Nitpicks a senior engineer would wave through

## Confidence rule
Only report if you would stake your review reputation on it.

## Input

CLAUDE.md:
<claude_md>
{{CLAUDE_MD}}
</claude_md>

Architecture rules:
<architecture_rules>
{{ARCHITECTURE_RULES}}
</architecture_rules>

Anti-patterns checklist:
<anti_patterns>
{{ANTI_PATTERNS}}
</anti_patterns>

Kb (reusable helpers — block any re-implementation):
<kb_architecture>
{{KB_ARCHITECTURE}}
</kb_architecture>

Diff:
<diff>
{{DIFF}}
</diff>

Commits:
<commits>
{{COMMIT_MESSAGES}}
</commits>

Issue body:
<issue>
{{ISSUE_BODY}}
</issue>

## Output format

JSON array. Each element:
{
  "type": "bug" | "security" | "justification" | "maintainability" | "design-principle" | "compliance" | "unspecified-function" | "silent-swallow" | "deviation-form" | "anti-pattern" | "kernel-reuse" | "db-efficiency",
  "severity": "block" | "warn",
  "file": "relative/path.ts",
  "line": 42,
  "finding": "one sentence",
  "evidence": "quoted code or rule"
}

Return [] if nothing warrants reporting.
```

Skip to **Step 4** with the single agent's output. Do not launch Agent A or Agent C.

---

#### If DIFF_LINE_COUNT ≥ 150: launch TWO agents in parallel (single message)

**Agent A — Code Quality & Correctness**

**Tools:** Read, Bash, Glob, Grep

```
You are a senior engineer doing a code review. Your job: bugs, security, code
justification, maintainability, design principles, CLAUDE.md compliance, and known
framework anti-patterns. Design conformance (LLD matching) is handled by a separate agent.

## Bugs (block)
- Logic errors, off-by-one, null dereferences, incorrect error handling
- Missing awaits on async calls
- Race conditions or incorrect state transitions
- Silent catch blocks that discard errors without at least a console.error — always a bug

## Security (block if found)
- Injection (SQL/NoSQL/command/template)
- AuthZ bypass — missing ownership/RLS on reads or writes
- Secrets in code, logs, URLs, or comments
- SSRF on server-side fetch of client-supplied URLs
- Insecure defaults or missing security headers
- Error leakage — stack traces, schema, or tokens in responses

## Code justification (block if severe)
- Solves the stated problem without over-engineering — nothing beyond the current task?
- Single-use helpers or abstractions? Complexity replaceable by simpler alternatives?

## Maintainability / Boy Scout (block if severe, warn for nits)
- Dead code introduced (unused imports, vars, functions)
- Duplication created instead of reusing an existing helper
- Touched functions left harder to understand than they were (naming, structure) — a broken window opened, not left
- **Metric-driven rewrites:** when a change is motivated by a complexity/score gate, verify
  the rewrite didn't hide explicit intent (e.g. an explicit override branch flattened into
  a helper's null-guard). Flag as **warn**.
Scope: diff only — edf:diag owns whole-file metrics.

## Design principles (block if severe)
The project's architecture rules are in `{{ARCHITECTURE_RULES}}` (from `kb/architecture.md`).
Apply each rule literally. If `{{ARCHITECTURE_RULES}}` is empty, skip the project-specific
part and apply only the universal SOLID heuristics:
- Single Responsibility: does each new function/module do one thing?
- Dependency Inversion: dependencies injected, not imported as concrete implementations.
- Interface Segregation: no overly broad interfaces forced on callers.
- Open/Closed: a change should not require modifying multiple unrelated modules.
- Functions over classes unless state genuinely requires a class.

## CLAUDE.md compliance
Only check these:
- No `Co-Authored-By` trailers in commit messages (block)
- Every commit uses conventional format AND references an issue (warn)
- Any language-specific compliance rule listed in `{{ANTI_PATTERNS}}` under "Language conventions" (severity per the rule).

## Project anti-patterns (always check, no web search)
Apply every check listed in `{{ANTI_PATTERNS}}`. Each entry states its own severity. Skip
if `{{ANTI_PATTERNS}}` is empty.

## What NOT to report
- Pre-existing issues not made worse by this diff
- Anything CI catches automatically
- Nitpicks a senior engineer would wave through

## Confidence rule
Only report if you would stake your review reputation on it.

## Input

CLAUDE.md:
<claude_md>
{{CLAUDE_MD}}
</claude_md>

Architecture rules:
<architecture_rules>
{{ARCHITECTURE_RULES}}
</architecture_rules>

Anti-patterns checklist:
<anti_patterns>
{{ANTI_PATTERNS}}
</anti_patterns>

Diff:
<diff>
{{DIFF}}
</diff>

Commits:
<commits>
{{COMMIT_MESSAGES}}
</commits>

Issue body:
<issue>
{{ISSUE_BODY}}
</issue>

## Output format

JSON array. Each element:
{
  "type": "bug" | "security" | "justification" | "maintainability" | "design-principle" | "compliance" | "anti-pattern",
  "severity": "block" | "warn",
  "file": "relative/path.ts",
  "line": 42,
  "finding": "one sentence",
  "evidence": "quoted code or rule"
}

Return [] if nothing warrants reporting.
```

---

**Agent C — Design Conformance**

**Tools:** Read, Bash, Glob, Grep

```
You are checking whether the implementation matches its LLD design references, and scanning
for silent error swallowing and diagnostics issues.

## Step 1: Identify design references

For each changed source file, look for a header comment in the form:
  Design reference: <path> §<section>
(use the project's comment syntax)

If no such comment exists on a file, skip design-conformance checks for that file but still
run the silent-swallow and diagnostics checks.

## Step 2: Read the LLD and compare

For each design reference found:
1. Read the full referenced doc section.
2. Extract every function name explicitly specified (code blocks, bullet lists, "Internal
   decomposition" tables, signatures). Build DESIGNED_FUNCTIONS.
3. From the diff, collect every function declared in changed files. Build IMPLEMENTED_FUNCTIONS.

**If the LLD has an internal decomposition section:**
- Functions in IMPLEMENTED_FUNCTIONS not in DESIGNED_FUNCTIONS:
  - No justification comment → **block** (add a `Justification:` comment or update LLD)
  - Justification comment exists → **warn**

**If the LLD has NO internal decomposition section:**
- Unspecified private helpers → **warn** ("LLD gap — update internal decomposition")
- Unspecified exported/public functions → **block** regardless

Exported/public functions are higher risk than private helpers — note this in findings.

**Deviation review:** When the PR body or commits document a deviation from the LLD,
diff the LLD's prescribed form at each named call site against the implemented form.
Flag any form divergence as **warn** (`"type": "deviation-form"`) unless the deviation
note explicitly addresses why the form changed. "Semantics identical" (or equivalent)
is not a justification — the note must state the concrete reason (e.g. "extracted to
helper to reuse null-guard", "flattened for complexity gate").

## Step 3: Silent catch/swallow check

Scan the diff for `catch` blocks where the error is not passed to at least a
`console.error` / `logger.error` / `log.error` call.

For each match: **block** finding. Fallback behaviour does not excuse missing observability.

## Step 4: Helper reuse (reusable helpers — block re-implementation)

If `{{KB_ARCHITECTURE}}` is non-empty, it lists the project's reusable helpers. The
"Helper reuse" section of `{{ANTI_PATTERNS}}` lists inline-pattern → reusable-helper mappings.
Apply these checks:

1. **Anti-pattern list** — scan the diff for each bullet under "Helper reuse" in
   `{{ANTI_PATTERNS}}`. Each match → **block** with `"type": "kernel-reuse"`. Quote the
   offending code; name the reusable helper that should have been used.

2. **Symbol reuse** — for each new function in the diff, check whether a reusable helper in
   `{{KB_ARCHITECTURE}}` already does the same job. Heuristics: matching domain, matching data
   targets (table names, endpoints), matching return shapes. If yes and the new function
   does not delegate → **block** with `"type": "kernel-reuse"`.

3. **LLD kb-reference check** — if the diff includes an LLD under `docs/design/` that
   touches a kb topic but lacks a "Reused helpers — DO NOT re-implement" table naming
   the reusable helpers it depends on → **warn** with `"type": "kernel-reuse"`.

4. **Redundant DB round-trips** (`"type": "db-efficiency"`) — within a single request
   handler / page render / service call:
   - Two queries against the **same row or row-set** (same target + same predicate) that
     could be a single query → **block**. Capture once, pass down.
   - Two queries against **different targets** that the data layer could fetch in one call
     (embedded select / join / single GraphQL query) → **warn**.
   - N+1 patterns (loop issuing a query per iteration) → **block**. Fix: a single batched
     query, a join, or a single GraphQL request.

5. **Chained calls that could collapse** (`"type": "db-efficiency"`, **warn**) — when a
   handler fetches multiple related resources via chained data-layer calls that the data
   layer could collapse into one, flag the chain. Do not flag a single query.

If `{{KB_ARCHITECTURE}}` is empty AND the "Helper reuse" section of `{{ANTI_PATTERNS}}` is empty,
skip Step 4 entirely.

## Step 5: Diagnostics check

For each changed source file, check whether a diagnostics file exists at
`.diagnostics/<same relative path>`. If it exists, read it.

Surface any Error or Warning severity finding as a **warn**. Omit Info-level unless related
to a flagged function.

## Input

Anti-patterns checklist:
<anti_patterns>
{{ANTI_PATTERNS}}
</anti_patterns>

Kb (reusable helpers — block any re-implementation):
<kb_architecture>
{{KB_ARCHITECTURE}}
</kb_architecture>

Diff:
<diff>
{{DIFF}}
</diff>

Changed files:
<changed_files>
{{CHANGED_FILES}}
</changed_files>

## Output format

JSON array. Each element:
{
  "type": "unspecified-function" | "silent-swallow" | "deviation-form" | "diagnostic" | "kernel-reuse" | "db-efficiency",
  "severity": "block" | "warn",
  "file": "relative/path.ts",
  "line": 42,
  "finding": "one sentence",
  "evidence": "function name, quoted code, or diagnostic text"
}

For "unspecified-function" findings, include the LLD path in the "evidence" field.

Return [] if nothing warrants reporting.
```

---

#### Agent B — External Surface Currency (ONLY if PATTERNS_NEEDED is true)

**Tools:** Read, Bash, Glob, Grep, WebFetch, WebSearch

If `PATTERNS_NEEDED` is false, **skip Agent B entirely.**

If `PATTERNS_NEEDED` is true, launch Agent B on **either** size path, in the same message as
the other agents — alongside Agent Q under 150 lines, or alongside Agent A and Agent C at or
above it.

```
You are checking two things: (1) design contract adherence, and (2) whether the diff uses
outdated or discouraged patterns in the frameworks it touches — not just deprecated APIs,
but practices the framework community now considers harmful or superseded.

The distinction matters: a package can be current and non-deprecated while specific usage
patterns within it are wrong. Your job is to catch those patterns too.

## Part 1: Design contract

If the PR references a design doc:
1. Read the full design doc section.
2. Find renamed or deleted names in the diff.
3. Search the design doc for stale references not updated in this PR.
4. Verify function signatures, type shapes, API endpoint paths match the design.
5. Check acceptance criteria from the linked issue — are all addressed?

## Part 2: External surface currency (web research per surface)

Surfaces marked NEW below are used for the first time in this repo. There was no in-repo
precedent for the author to copy, so that code was written from training recall — which for
a spec revised after the model's training data is confidently wrong in a way that reads
perfectly consistent. **Research every NEW surface first, and never rely on your own
recollection of its contract to judge the diff.**

For a NEW surface that has a doc URL, `WebFetch` that URL and compare the diff against what
it actually says: message and field names, required and optional fields, handshake or
negotiation order, error shapes, and any capability the pinned revision added or removed.
For every other surface, run ONE targeted web search, framed as:
  "<surface> <version> best practices discouraged patterns <year>"
  or "<surface> <version> security recommendations current"

**The pinned version is the contract.** Judge the diff against the version or dated revision
stated below, not the version you remember as current. If the diff implements a different
revision than the one pinned — an older message shape, a field the pinned revision renamed
or dropped — report it as a block-severity finding: that is the exact failure this check
exists to catch. If a surface is marked `unpinned`, report that too; an external surface with
no pinned version cannot be reviewed for currency and cannot be tracked for drift.

Do NOT frame searches as just "deprecated APIs" — you are looking for:
- Security anti-patterns (e.g. using wrong key type server-side, insecure defaults)
- Patterns the framework has moved away from even if not formally deprecated
- Usage that works but violates the framework's current recommended approach
- Known footguns the community has documented

Cross-reference findings with the diff. Only report if the diff actively uses a discouraged
or insecure pattern. Do not report theoretical risks not present in the code.

The kinds of findings to look for: security anti-patterns (wrong credential type
server-side, insecure defaults), patterns the framework has formally moved away from,
usage that violates the framework's current recommended approach, and known footguns the
community has documented. The project's static checklist in `{{ANTI_PATTERNS}}` covers the
patterns the team has already learned to flag — Agent B supplements that with framework-
specific research.

Surfaces to check — each listed as `name | pinned version | doc URL | NEW or ESTABLISHED`:
{{EXTERNAL_SURFACES}}

Of these, first use in this repo (research these before anything else):
{{NEW_SURFACES}}

Budget: five surfaces max. One web search per surface, plus one `WebFetch` per NEW surface
that has a doc URL.

## Input

Diff:
<diff>
{{DIFF}}
</diff>

Issue body:
<issue>
{{ISSUE_BODY}}
</issue>

## Output format

JSON array. Each element:
{
  "type": "design-contract" | "anti-pattern" | "version-mismatch" | "unpinned-surface",
  "severity": "block" | "warn",
  "file": "relative/path.ts",
  "line": 42,
  "finding": "one sentence — include WHY this pattern is discouraged",
  "evidence": "quoted code from diff",
  "source_url": "URL of the docs or community guidance, if found"
}

For "version-mismatch", state both revisions in "finding" — the one pinned and the one the
diff implements — and cite the doc URL in "source_url". Severity is "block".

Return [] if nothing warrants reporting.
```

---

### Step 4: Consolidate and output

Collect JSON arrays from all agents that ran. Merge and deduplicate (keep the more specific
finding). Sort by severity: `block` items first, then `warn`.

**If no findings:**

```
### PR Review

No issues found. Checked: bugs, security, code justification, maintainability, design
principles, CLAUDE.md compliance, kb reuse, DB efficiency, framework anti-patterns, design conformance.
[Framework best practices: skipped — no framework files changed.]
```

**If findings exist:**

```
### PR Review

#### Blockers (N)

**[type] file.ts:line**
<finding>
> <evidence>

#### Warnings (N)

**[type] file.ts:line**
<finding>
> <evidence>
```

Types: `[bug]`, `[security]`, `[justification]`, `[maintainability]`, `[design-principle]`,
`[compliance]`, `[kernel-reuse]`, `[db-efficiency]`, `[design-contract]`, `[anti-pattern]`,
`[unspecified-function]`, `[silent-swallow]`, `[deviation-form]`, `[diagnostic]`.

**PR mode:** post as a PR comment:
```bash
gh pr comment <number> --body "<formatted report>"
```

### Step 5: Cost

After outputting the review (and posting the PR comment if in PR mode), run the cost script
for the current session and append the result to the terminal output. Do NOT apply labels —
reporting only.

```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/query-feature-cost.py "$(bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/get-session-id.py)"
```

If the script returns "Prometheus unreachable" or "No session data found", print the message
as-is — do not retry or error. Cost reporting is best-effort.

Append to terminal output (not to the PR comment):

```
---
### Review cost (pr-review — adaptive)
<script output>
```

---

## Notes

- Do not run builds, type-checks, or tests — CI handles those.
- In the ≥ 150 line path: launch Agent A and Agent C (and Agent B if PATTERNS_NEEDED)
  in the **same message** so they run concurrently. In the < 150 line path: launch Agent Q
  (and Agent B if PATTERNS_NEEDED) the same way. Agent B's trigger is independent of diff
  size — a first integration against an external spec can be small and still be invented.
- If the diff is empty, report "Nothing to review — diff is empty." and stop.
- The 150-line threshold is a guide. If a large diff is mostly trivial changes (whitespace,
  renames, generated code), use judgment and prefer the single-agent path.
- The static anti-pattern list (`kb/anti-patterns.md`, surfaced as `{{ANTI_PATTERNS}}`)
  runs on EVERY review at no extra cost — no web search, no extra agent. Agent B
  supplements it with live research only on first contact with an external surface, or when
  dependency/config files changed. Established surfaces are covered by the static list plus
  the in-repo precedent the author copied — that is where the cost saving comes from, and
  why the saving does not apply to a from-scratch integration.
- Add new patterns to the project's `kb/anti-patterns.md` as the team discovers them. That
  file is the institutional memory of "things we've learned the hard way."
- Cost is reported in terminal only — never posted to GitHub. The label in the cost
  output ("pr-review — adaptive") identifies which review run produced the cost line.
