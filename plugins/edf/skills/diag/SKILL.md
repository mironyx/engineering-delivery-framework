---
name: diag
description: Run CodeScene health checks on changed files, plus SonarQube MCP analysis when `sonar` is passed, then check diagnostics-exporter output if `.diagnostics/` exists. Use when the user wants to check code quality, review diagnostics, or before committing code.
allowed-tools: Read, Write, Edit, MultiEdit, Glob, Bash, Skill, mcp__codescene__code_health_review, mcp__codescene__code_health_score, mcp__sonarqube__analyze_code_snippet, mcp__sonarqube__analyze_file_list, mcp__sonarqube__run_advanced_code_analysis
---

# Check Diagnostics — On-Demand Code Quality Check

Checks changed files with CodeScene MCP and, on request, SonarQube MCP. Reads the
diagnostics-exporter output from `.diagnostics/` last, and only if it exists. Use for a
batch check across multiple files, e.g., before committing.

## Scope: default vs. `sonar`

- **No `sonar` argument:** run Steps 1, 2 and 4 (CodeScene + diagnostics-exporter). Cheap —
  the right choice for a fix-and-recheck loop.
- **`sonar` in `$ARGUMENTS`:** also run Step 3 — SonarQube MCP analysis of the changed
  files, before anything is pushed. Callers run it once after the local loop is clean, not
  on every iteration.

CodeScene (Step 2) and SonarQube (Step 3) are the checks that matter. The
diagnostics-exporter (Step 4) is an editor convenience: a missing `.diagnostics/` is never
a reason to stop or skip the other steps.

## How diagnostics are generated

The `diagnostics-exporter` extension exports diagnostics for files that are **open in the editor**, into `.diagnostics/` of the folder VS Code has open. A PostToolUse hook fires after every Write/Edit, waits 3 s, then reads whatever the extension has exported. If the file is not open in the editor, the extension has nothing to export — the `.diagnostics/` file is either missing or reflects an earlier open session. In a git worktree (a separate folder VS Code does not have open), in CI, or without an editor, `.diagnostics/` does not exist at all.

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing the step order, CodeScene MCP integration, SonarQube MCP analysis, or the fix-and-recheck loop.

## Instructions

1. **Identify target files.**
   - File paths in `$ARGUMENTS` (anything other than `sonar` and `--verbose`): check only
     those files.
   - Otherwise run `git diff --name-only` and `git diff --cached --name-only` and take the
     modified source files (`.ts`, `.tsx`, `.js`, `.jsx`, `.py`) under **both `src/` and
     `tests/`**. Test files are analysed by CodeScene and must be included — do not restrict
     to `src/` only. Skip generated code.

2. **CodeScene MCP code health check.**

   Run `mcp__codescene__code_health_score` on each target file (absolute paths, forward slashes). This works independently of the editor and of `.diagnostics/`.

   - **Score > 9.8 (green/optimal):** clean — no action needed. Target 10.0.
   - **Score 4.0–9.8 (yellow):** run `mcp__codescene__code_health_review` for the detailed smell breakdown. **Attempt to fix every finding.** Only skip a finding if the fix would require changes to >5 unrelated files, touch infrastructure/config outside the feature scope, or involve generated code. In those cases, document the finding and the specific reason for skipping. Do NOT skip with a generic "pre-existing" label — that's not a reason.
   - **Score < 4.0 (red):** blocking — run `mcp__codescene__code_health_review`, fix all findings, and re-check until the score is at least 4.0 (ideally 10.0). Even here, document any finding you genuinely cannot fix rather than silently moving on.

   Report:

   ```text
   ### Code Health (MCP)
   - `src/foo/bar.ts` — 10.0 ✓
   - `src/foo/baz.ts` — 7.2 ⚠ (complex conditional, bumpy road — fixed)
   - `tests/foo/bar.test.ts` — 9.5 ✓
   ```

   **If any file scores ≤ 9.8**, include the detailed review findings in the report and fix them, re-checking the score after each fix.

3. **SonarQube MCP analysis (only when `sonar` is in `$ARGUMENTS`).**

   Analyse the changed files through the SonarQube MCP server so issues are fixed before the
   PR. Do not use the project quality gate or issue search for this: SonarCloud only holds
   analyses of what CI pushed, so on a feature branch they describe `main`, not this change —
   zero issues there means "not analysed", not "clean".

   1. **List changed lines** (source files only — skip generated code):

      ```bash
      bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/changed-lines.py
      ```

   2. **Analyse** with whichever SonarQube MCP analysis tool this session exposes. The
      server registers different ones depending on its configuration; check in this order:
      - `mcp__sonarqube__analyze_file_list` (SonarQube for IDE connected) — one call with
        the absolute paths of all changed files.
      - `mcp__sonarqube__analyze_code_snippet` — one call per file. Read the file and pass
        its full content as `fileContent`, plus `language` and `scope` (`TEST` for test
        files, else `MAIN`). This works from any folder, including worktrees, because the
        server never needs to see the file system.
      - `mcp__sonarqube__run_advanced_code_analysis` (needs a Vortex subscription and the
        workspace mounted into the server) — one call per file with `projectKey`,
        `branch` (`git branch --show-current`), `filePath` relative to the repo root, and
        `fileScope`. If it fails because Vortex is not enabled, or the file is not found in
        the mounted workspace, treat it as unavailable.

      **Never** fall back to the `sonar` CLI (`sonar analyze …`) or to server-side issue
      search — the CLI needs Vortex and fails with a 403, and server data does not cover
      this branch. If no analysis tool is available, report the line below and move on to
      Step 4; do not block:

      ```text
      SonarQube: skipped — the SonarQube MCP exposes no analysis tool in this session
      (needs analyze_code_snippet: start the server with SONARQUBE_FORCE_LOCAL_ANALYSIS=true
      and the `analysis` toolset, or connect SonarQube for IDE for analyze_file_list).
      ```

   3. **Sort each issue:**
      - **New** — its line is in the file's changed-line ranges. **Fix all of them.**
      - **Pre-existing** — any other line in a changed file. **Fix the top 2 across all
        files** by severity (Blocker, then Critical/High, then Major), boy-scout style. Skip
        one whose fix would reach outside the changed files and take the next. Report the
        rest as a count only — do not list or investigate them.
   4. **Re-analyse once** after fixes to confirm the new issues are gone. Do not loop further;
      a new issue you genuinely cannot fix gets a one-line reason in the report.

   Report:

   ```text
   ### SonarQube (MCP, changed files)
   - Tool: analyze_code_snippet
   - New: 2 found, 2 fixed
   - Pre-existing: 2 fixed (src/foo/bar.ts:88 S3776, src/foo/baz.ts:12 S1854); 7 others left
   ```

4. **Diagnostics-exporter (last; only if `.diagnostics/` exists).**

   ```bash
   test -d "$(git rev-parse --show-toplevel)/.diagnostics" && echo "EXISTS" || echo "MISSING"
   ```

   **If MISSING:** report the line below and finish. This is normal in worktrees, CI and
   non-editor sessions — not an error, and not a reason to re-run or skip anything else.

   ```text
   ### Diagnostics-exporter
   Skipped — no `.diagnostics/` (worktree or non-editor environment).
   ```

   **If EXISTS:**

   1. **Open the target files in the editor** so the extension exports fresh diagnostics,
      including for edits made in Steps 2–3:

      ```bash
      bash ${CLAUDE_PLUGIN_ROOT}/hooks/open-in-editor.sh src/foo/service.ts src/lib/bar/client.ts
      sleep 5
      ```

   2. **Read diagnostics** for each target file from `.diagnostics/<relative-path>.json`
      (format below) and parse the `diagnostics` array.
   3. **Report findings, then fix them all.**
      - **Errors and Warnings:** always report, grouped by severity (Errors first, then
        Warnings). Flag any Errors clearly at the top of the report.
      - **Info / Hints:** suppress unless `--verbose` was passed.
      - Each issue: `file:line:column [source/code] — message`
      - No diagnostics file for a target: wait another 5 s and retry once, then list it
        under "No diagnostics available".
      - Empty diagnostics: clean.

      Fix every finding — or, if it genuinely cannot be fixed without a major cross-file
      refactor, add an explicit `// Justification:` comment explaining why.
   4. **Confirm resolution.** Re-read the diagnostics files; the files are open, so each save
      produced a fresh export. If a file's `analyzedAt` has not advanced since your edits,
      run `open-in-editor.sh <file>` and `sleep 5`, then re-read once more. Re-run Step 2
      on any file you changed here.

## Diagnostics JSON Format

```json
{
  "file": "relative/path/to/source.ts",
  "analyzedAt": "2026-03-12T11:53:41.861Z",
  "diagnostics": [
    {
      "source": "ts",
      "severity": "Error",
      "message": "Description of the issue",
      "line": 42,
      "column": 5,
      "code": 1214
    }
  ]
}
```

## Example Output

```text
## Diagnostics Report

**Files checked:** 3

### Code Health (MCP)
- `src/foo/bar.ts` — 7.2 ⚠ (complex conditional, bumpy road — fixed)
- `src/foo/types.ts` — 10.0 ✓
- `tests/helpers/baz.test.ts` — 10.0 ✓

### SonarQube (MCP, changed files)
- Tool: analyze_code_snippet
- New: 0
- Pre-existing: 1 fixed (src/foo/bar.ts:15 S1481); 3 others left

### Diagnostics-exporter
#### Errors
- `src/foo/bar.ts:42:5` [ts/2304] — Cannot find name 'foo'
#### No diagnostics available
- `tests/helpers/baz.test.ts` — Extension has not exported diagnostics for this file
```
