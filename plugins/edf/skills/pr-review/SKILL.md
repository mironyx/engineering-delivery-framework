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
- `FRAMEWORK_DEPS` — top 5 packages/imports referenced in changed files that appear in the project's dependency manifest as direct (not dev) dependencies. Skip if no manifest.
- `PATTERNS_NEEDED` — true if ANY of these appear in the changed file list:
  - The project's dependency manifest or lockfile (e.g. `package.json`/`package-lock.json`, `pyproject.toml`/`uv.lock`, etc.)
  - Any `.env` / `.env.*` file
  - Any file importing a framework package named in `{{ANTI_PATTERNS}}`
  - Any framework config file (e.g. `*.config.ts`, `middleware.ts`, `next.config.*`, `vite.config.*`, `pyproject.toml` build config) — judged against the project's stack

Then fetch in parallel:
- **Issue body:** extract linked issue from PR body (`Closes #N`, `Fixes #N`, `Resolves #N`).
  Fetch `gh issue view <N>` for acceptance criteria and design doc paths. (PR mode only)
- **Commits:** `gh pr view <number> --json commits` (PR mode) or `git log main..HEAD --oneline`
  (local mode).

### Step 3: Launch agents (count depends on diff size)

---

#### If DIFF_LINE_COUNT < 150: launch ONE agent

**Agent Q — Quality (all checks, single agent)**

**Tools:** Read, Bash, Glob, Grep

```
You are a senior engineer doing a focused code review on a small diff. Cover all areas
in one pass: bugs, code justification, design principles, CLAUDE.md compliance, framework
anti-patterns, and design conformance.

## Part 1: Bugs (block if found)
- Logic errors, off-by-one, null dereferences, incorrect error handling
- Missing awaits on async calls
- Race conditions or incorrect state transitions
- Security issues (injection, credential exposure, missing auth checks)
- Silent catch blocks that discard errors without at least a console.error — always a bug

## Part 2: Code justification (block if severe)
- Does this code solve the stated problem without over-engineering?
- YAGNI: is anything added not required by the current task?
- Helpers or abstractions introduced for a single use?
- Complexity that could be replaced by simpler alternatives?

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

Also scan for silent catch blocks (error not passed to any logger) → **block**.

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
  "type": "bug" | "justification" | "design-principle" | "compliance" | "unspecified-function" | "silent-swallow" | "anti-pattern" | "kernel-reuse" | "db-efficiency",
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
You are a senior engineer doing a code review. Your job: bugs, code justification,
design principles, CLAUDE.md compliance, and known framework anti-patterns.
Design conformance (LLD matching) is handled by a separate agent.

## Bugs (block)
- Logic errors, off-by-one, null dereferences, incorrect error handling
- Missing awaits on async calls
- Race conditions or incorrect state transitions
- Security issues (injection, credential exposure, missing auth checks)
- Silent catch blocks that discard errors without at least a console.error — always a bug

## Code justification (block if severe)
- Does this code solve the stated problem without over-engineering?
- YAGNI: is anything added not required by the current task?
- Helpers or abstractions introduced for a single use?
- Complexity replaceable by simpler alternatives?

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
  "type": "bug" | "justification" | "design-principle" | "compliance" | "anti-pattern",
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

Note: the LLD is not infallible. Surface the gap — the resolution is a human decision.

Exported/public functions are higher risk than private helpers — note this in findings.

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
  "type": "unspecified-function" | "silent-swallow" | "diagnostic" | "kernel-reuse" | "db-efficiency",
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

#### Agent B — Framework Best Practices (ONLY if PATTERNS_NEEDED is true)

**Tools:** Read, Bash, Glob, Grep, WebSearch

If `PATTERNS_NEEDED` is false, **skip Agent B entirely.**

If `PATTERNS_NEEDED` is true, launch Agent B in the same message as Agent A and Agent C
(three parallel agents total).

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

## Part 2: Framework best practices (web search per framework)

For each framework package below, run ONE targeted web search. Frame each search as:
  "<package>@<version> best practices discouraged patterns <year>"
  or "<package>@<version> security recommendations current"

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

Packages to check:
{{FRAMEWORK_DEPS_WITH_VERSIONS}}

Maximum web searches: one per package, five packages max.

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
  "type": "design-contract" | "anti-pattern",
  "severity": "block" | "warn",
  "file": "relative/path.ts",
  "line": 42,
  "finding": "one sentence — include WHY this pattern is discouraged",
  "evidence": "quoted code from diff",
  "source_url": "URL of framework docs or community guidance, if found"
}

Return [] if nothing warrants reporting.
```

---

### Step 4: Consolidate and output

Collect JSON arrays from all agents that ran. Merge and deduplicate (keep the more specific
finding). Sort by severity: `block` items first, then `warn`.

**If no findings:**

```
### PR Review

No issues found. Checked: bugs, code justification, design principles, CLAUDE.md compliance,
kb reuse, DB efficiency, framework anti-patterns, design conformance.
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

Types: `[bug]`, `[justification]`, `[design-principle]`, `[compliance]`, `[kernel-reuse]`,
`[db-efficiency]`, `[design-contract]`, `[anti-pattern]`, `[unspecified-function]`,
`[silent-swallow]`, `[diagnostic]`.

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
  in the **same message** so they run concurrently.
- If the diff is empty, report "Nothing to review — diff is empty." and stop.
- The 150-line threshold is a guide. If a large diff is mostly trivial changes (whitespace,
  renames, generated code), use judgment and prefer the single-agent path.
- The static anti-pattern list (`kb/anti-patterns.md`, surfaced as `{{ANTI_PATTERNS}}`)
  runs on EVERY review at no extra cost — no web search, no extra agent. Agent B
  supplements this with framework-specific research only when framework files changed.
- Add new patterns to the project's `kb/anti-patterns.md` as the team discovers them. That
  file is the institutional memory of "things we've learned the hard way."
- Cost is reported in terminal only — never posted to GitHub. The label in the cost
  output ("pr-review — adaptive") identifies which review run produced the cost line.
