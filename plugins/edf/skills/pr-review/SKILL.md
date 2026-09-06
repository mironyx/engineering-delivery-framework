---
name: pr-review
description: Review code changes for bugs, design principles, contract adherence, external surface currency, and design conformance. Use before committing (/pr-review) or on a PR (/pr-review 123). Adaptive: 1 agent for small diffs, 2 agents for large diffs. Agent B (surface currency) runs on either path, only on first use of an external surface or when dependency/config files changed.
allowed-tools: Read, Write, Bash, Glob, Grep, Agent, Skill, TodoWrite, WebFetch, WebSearch
---

# PR Review

Two modes:

- `/pr-review` — reviews local uncommitted changes (`git diff HEAD`)
- `/pr-review <pr-number>` — reviews a pull request; posts the result as a PR comment

**Cost-adaptive architecture.** Agent count scales with diff size:
- Diff < 150 lines → **1 agent** (Quality, covering all checks)
- Diff ≥ 150 lines → **2 agents** (Quality + Design Conformance in parallel)
- Agent B (surface currency) runs on either path, but only on first use of an external surface, or when dependency/config files changed

---

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing the cost-adaptive threshold, agent count, or agent prompt structure.

## Process

### Step 1: Gather context

Determine mode from `$ARGUMENTS`:

- Number present → **PR mode**
- Otherwise → **local mode**

Build the review package first, then run the rest in parallel.

1. **Build the review package.** The diff never enters this session's context — it goes
   to a git-ignored file that the review agents read for themselves.

   ```bash
   # PR mode
   bash ${CLAUDE_PLUGIN_ROOT}/bin/review-package.sh --pr <number>
   # Local mode
   bash ${CLAUDE_PLUGIN_ROOT}/bin/review-package.sh --local
   ```

   The script prints `package: <path>` followed by a `numstat:` table — one
   `added<TAB>removed<TAB>path` row per changed file. That path is `{{DIFF_FILE}}`, and
   the numstat table is the only diff-derived data allowed in this session: it supplies
   both the changed-file list and the line counts Step 2 needs.

   **Never `cat`, `Read`, `gh pr diff`, or `git diff` the change yourself.** Reading the
   diff here puts it in context for every remaining turn and defeats the package — the
   agents each read the file directly instead.

   Exit code 3 means the diff is empty: print "Nothing to review — diff is empty." and stop.

2. Read `CLAUDE.md` (root).
3. Read the project's dependency manifest if one exists (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, etc.) — capture exact versions of direct dependencies. Skip if none present.
4. Read `kb/architecture.md` — the project's architecture rules. Pass its full contents to the review agent(s) as `{{ARCHITECTURE_RULES}}`. Skip if absent.
5. Read `kb/anti-patterns.md` — the project's anti-pattern checklist (framework-specific patterns, language conventions, helper-reuse rules). Pass its full contents as `{{ANTI_PATTERNS}}`. Skip if absent.
6. Pass `kb/architecture.md` contents (already read in step 4) as `{{KB_ARCHITECTURE}}` — it doubles as the reusable helper catalogue. Skip if the file has no API composition pattern entries (helper-reuse checks rely on `{{ANTI_PATTERNS}}` content instead).

### Step 2: Classify the review

From the numstat table printed in Step 1 (never from a fresh diff command), compute:

- `CHANGED_FILES` — source files added or modified (not deleted). Treat any path under the
  project's source root as a source file; `kb/conventions.md` may name a `test-suffix` to
  recognise tests. **If `kb/conventions.md` is absent or names no `test-suffix`**, fall back
  to this built-in pattern set so test files are still excluded rather than silently
  miscounted as source: paths containing `/__tests__/`, `/test/`, or `/tests/`, or matching
  `*.test.*`, `*.spec.*`, `test_*.py`, or `*_test.py`.
- `DIFF_LINE_COUNT` — lines added + removed **in source files only** (per `CHANGED_FILES`'s
  test-suffix rule above, including its fallback) — excludes test files. A large test-only
  diff (e.g. an evaluator's adversarial tests, or a bulk fixture update) must not push a
  small source change onto the more expensive 2-agent path. Sum the added and removed
  columns of the Step 1 numstat table, counting only the rows for non-test files.
- `EXTERNAL_SURFACES` — every surface the diff codes against whose contract is defined
  outside this repo, each with its pinned version. Broader than the dependency manifest: a
  protocol or wire-format spec (MCP, OAuth, a webhook payload format) has no manifest entry
  yet is the case most likely to be written from stale recall, precisely because there is no
  version to grep for. Cap at 5, most central to the diff first.
  - **Source:** the `## External Surfaces` table in Part B of the LLD linked from the issue —
    authoritative, and already carries version, doc URL, and `New to repo`.
  - **No LLD or no table:** derive it. Direct (not dev) dependencies the changed files
    import, plus any spec surface evident from the diff — handshake or capability
    negotiation, a versioned wire format, a dated revision in comments or constants.
    Versions come from the manifest read in Step 1.3; for spec surfaces, whatever revision
    the diff states, or `unpinned` if it states none.
- `NEW_SURFACES` — the subset used here for the first time anywhere in this repo. Read the
  table's `New to repo` column, or grep outside the diff for prior use. First use means the
  author had no in-repo precedent to imitate, so the code came from training recall.
- `SURFACE_RESEARCH` — true if EITHER:
  - `NEW_SURFACES` is non-empty — **the primary trigger.**
  - The changed files touch the dependency manifest or lockfile, an `.env` / `.env.*` file,
    or a framework config file (`*.config.ts`, `middleware.ts`, `next.config.*`,
    `vite.config.*`, build config) — judged against the project's stack.

  It deliberately does **not** fire on ordinary changes to code using an already-established
  surface: there the surrounding code is the anchor, research is wasted spend, and
  `{{ANTI_PATTERNS}}` already runs free on every review. Spend on first contact — once per
  surface, not once per PR.

Then fetch in parallel:
- **Issue body:** extract linked issue from PR body (`Closes #N`, `Fixes #N`, `Resolves #N`).
  Fetch `gh issue view <N>` for acceptance criteria and design doc paths. (PR mode only)
- **Commits:** `gh pr view <number> --json commits` (PR mode) or `git log main..HEAD --oneline`
  (local mode).

### Step 3: Launch agents (count depends on diff size)

All agent prompts live in `prompts/` next to this file, not inline here — they only need to
be read by the spawned agent, not loaded into this session's context on every invocation.
Every prompt file below is read by its agent via the Read tool; this session never opens
them itself.

For each agent, spawn it with `Agent({ prompt: <text> })` where `<text>` is:

```
Follow the instructions in ${CLAUDE_PLUGIN_ROOT}/skills/pr-review/prompts/<file>.md exactly —
read that file first with the Read tool, then apply it to this review. Substitute these
values wherever the file's {{...}} placeholders appear:

{{PLACEHOLDER}} = <value>
...
```

with `<file>` and the placeholder values as given per agent below.

---

#### If DIFF_LINE_COUNT < 150: launch ONE agent

**Agent Q — Quality (all checks, single agent)** — `prompts/agent-q.md`

If `SURFACE_RESEARCH` is true, launch **Agent B alongside Agent Q in the same message**. Diff
size decides how the *quality* checks are split; `SURFACE_RESEARCH` alone decides whether
surface research happens — a first integration can be eighty lines and still be invented.

**Tools:** Read, Bash, Glob, Grep

Substitute: `{{CLAUDE_MD}}` (Step 1.2), `{{ARCHITECTURE_RULES}}` (Step 1.4, or empty),
`{{ANTI_PATTERNS}}` (Step 1.5, or empty), `{{KB_ARCHITECTURE}}` (Step 1.6, or empty),
`{{DIFF_FILE}}` (Step 1.1), `{{COMMIT_MESSAGES}}` (Step 2), `{{ISSUE_BODY}}` (Step 2, or empty).

Skip to **Step 4** with the single agent's output. Do not launch Agent A or Agent C.

---

#### If DIFF_LINE_COUNT ≥ 150: launch TWO agents in parallel (single message)

**Agent A — Code Quality & Correctness** — `prompts/agent-a.md`

**Tools:** Read, Bash, Glob, Grep

Substitute: `{{CLAUDE_MD}}` (Step 1.2), `{{ARCHITECTURE_RULES}}` (Step 1.4, or empty),
`{{ANTI_PATTERNS}}` (Step 1.5, or empty), `{{DIFF_FILE}}` (Step 1.1), `{{COMMIT_MESSAGES}}`
(Step 2), `{{ISSUE_BODY}}` (Step 2, or empty).

---

**Agent C — Design Conformance** — `prompts/agent-c.md`

**Tools:** Read, Bash, Glob, Grep

Substitute: `{{ANTI_PATTERNS}}` (Step 1.5, or empty), `{{KB_ARCHITECTURE}}` (Step 1.6, or
empty), `{{DIFF_FILE}}` (Step 1.1), `{{CHANGED_FILES}}` (Step 2).

---

#### Agent B — External Surface Currency (ONLY if SURFACE_RESEARCH is true) — `prompts/agent-b.md`

**Tools:** Read, Bash, Glob, Grep, WebFetch, WebSearch

If `SURFACE_RESEARCH` is false, **skip Agent B entirely.**

If `SURFACE_RESEARCH` is true, launch Agent B on **either** size path, in the same message as
the other agents — alongside Agent Q under 150 lines, or alongside Agent A and Agent C at or
above it.

Substitute: `{{ANTI_PATTERNS}}` (Step 1.5, or empty), `{{DIFF_FILE}}` (Step 1.1),
`{{ISSUE_BODY}}` (Step 2, or empty), `{{EXTERNAL_SURFACES}}` (Step 2), `{{NEW_SURFACES}}` (Step 2).

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
- In the ≥ 150 line path: launch Agent A and Agent C (and Agent B if SURFACE_RESEARCH)
  in the **same message** so they run concurrently. In the < 150 line path: launch Agent Q
  (and Agent B if SURFACE_RESEARCH) the same way. Agent B's trigger is independent of diff
  size — a first integration against an external spec can be small and still be invented.
- If the diff is empty, `review-package.sh` exits 3 without writing a package: report
  "Nothing to review — diff is empty." and stop.
- The review package is scratch, written to a self-ignoring `.edf/review/` at the repo
  root. It is never committed, and there is nothing to clean up.
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
