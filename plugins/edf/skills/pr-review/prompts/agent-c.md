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

Diff — read this file first with the Read tool. It holds the diffstat and the full
diff with 10 lines of context, and it is your view of the change. Those context
lines ARE the changed files: do not open a changed file separately unless a hunk you
must judge is cut off mid-function, and say so in your finding if you do. Do not run
`git diff` or `gh pr diff` to fetch the change yourself.
<diff_file>
{{DIFF_FILE}}
</diff_file>

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
