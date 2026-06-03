---
name: diag
description: Check diagnostics-exporter output for changed files, run CodeScene health checks, and SonarQube quality gate. Use when the user wants to check code quality, review diagnostics, or before committing code.
allowed-tools: Read, Write, Edit, MultiEdit, Glob, Bash, Skill, mcp__codescene__code_health_review, mcp__codescene__code_health_score
---

# Check Diagnostics — On-Demand Code Quality Check

Reads diagnostics exported by the diagnostics-exporter extension from `.diagnostics/`. Use for a batch check across multiple files, e.g., before committing.

## How diagnostics are generated

The `diagnostics-exporter` extension exports diagnostics for files that are **open in the editor**. A PostToolUse hook fires after every Write/Edit, waits 3 s, then reads whatever the extension has exported. If the file is not open in the editor, the hook fires but the extension has nothing to export — the `.diagnostics/` file is either missing or reflects an earlier open session.

This means: after making fixes in a CLI session, the diagnostics file may be **stale** (shows old issues) or **missing** entirely. The fix is to open the file in the editor using `bash ${CLAUDE_PLUGIN_ROOT}/hooks/open-in-editor.sh <file>`, which triggers a fresh CodeScene pass, then wait for the export.

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing the diagnostics reading flow, CodeScene MCP integration, SonarQube quality gate, or fix-and-recheck loop.

## Instructions

1. **Identify target files.**
   - If arguments are provided (`$ARGUMENTS`), check only those files.
   - Otherwise, check **all** files that have a diagnostics export: list every `.json` file under `.diagnostics/` (these are the files the extension has analysed). Also run `git diff --name-only` and `git diff --cached --name-only` to find modified source files (`.ts`, `.tsx`, `.js`, `.jsx`, `.py`) under **both `src/` and `tests/`** that may not have a diagnostics file yet. Union both sets. Test files are analysed by CodeScene and must be included — do not restrict to `src/` only.

2. **Pre-check: does `.diagnostics/` exist?**

   ```bash
   test -d .diagnostics && echo "EXISTS" || echo "MISSING"
   ```

   **If MISSING** (worktree, CI, or non-editor environment): skip Steps 3–5 entirely.
   The diagnostics-exporter extension only runs when files are open in a VS Code editor.
   Report this clearly and proceed directly to Step 6 (CodeScene MCP):

   ```
   ### Diagnostics-exporter
   **Skipped** — `.diagnostics/` directory not found (worktree or non-editor environment).
   CodeScene and SonarQube checks will still run.
   ```

   **If EXISTS**, continue to Step 3.

3. **Open all target files in the editor immediately.**

   Do this **before reading diagnostics or making any fixes**. Once a file is open, the editor detects every subsequent on-disk save and triggers a fresh CodeScene pass automatically — so diagnostics will be live as you edit.

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/hooks/open-in-editor.sh src/foo/service.ts src/lib/bar/client.ts
   sleep 5
   ```

   The `sleep 5` gives the initial analysis time to complete before you read diagnostics.

4. **Read diagnostics for each file.** For each source file:
   - Look for `.diagnostics/<relative-path>.json`
   - Read the JSON file if it exists
   - Parse the diagnostics array: `{source, severity, message, line, column, code}`

5. **Report findings, then fix them all.**
   - Total files checked vs files with diagnostics available
   - **Errors and Warnings:** always report, grouped by severity (Errors first, then Warnings)
   - **Info / Hints:** suppress from output. Only include if `--verbose` was passed as an argument.
   - For each reported issue: `file:line:column [source/code] — message`
   - Files with no diagnostics file: wait another 5 s and retry once
   - Files with empty diagnostics: clean
   - **If there are any Errors, flag this clearly at the top of the report.**

   After listing all findings, fix every one of them before proceeding. Do not stop at "documenting" a warning — fix it or, if it genuinely cannot be fixed without a major cross-file refactor, add an explicit `// Justification:` comment explaining why.

6. **Confirm resolution.**

   After all fixes are applied, re-read the diagnostics files for the changed files. Because the files are already open in the editor (from Step 3), the extension will have exported fresh diagnostics after each save — no need to re-open. If any findings remain, fix them and re-check.

   If a file's diagnostics timestamp has not advanced since before your edits (stale), run:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/hooks/open-in-editor.sh <file>
   sleep 5
   ```
   then re-read once more as a safety net.

7. **CodeScene MCP code health check.**

   After the diagnostics-exporter pass (Steps 1–6), run `mcp__codescene__code_health_score` on each target source file (use absolute paths, forward slashes). This works independently of the editor — no need for files to be open.

   - **Score > 9.8 (green/optimal):** clean — no action needed. Target 10.0.
   - **Score 4.0–9.8 (yellow):** run `mcp__codescene__code_health_review` for the detailed smell breakdown. **Attempt to fix every finding.** Only skip a finding if the fix would require changes to >5 unrelated files, touch infrastructure/config outside the feature scope, or involve generated code. In those cases, document the finding and the specific reason for skipping. Do NOT skip with a generic "pre-existing" label — that's not a reason.
   - **Score < 4.0 (red):** blocking — run `mcp__codescene__code_health_review`, fix all findings, and re-check until the score is at least 4.0 (ideally 10.0). Even here, document any finding you genuinely cannot fix rather than silently moving on.

   Report MCP scores alongside the diagnostics-exporter findings:

   ```
   ### Code Health (MCP)
   - `src/foo/bar.ts` — 10.0 ✓
   - `src/foo/baz.ts` — 7.2 ⚠ (complex conditional, bumpy road — fixed)
   - `tests/foo/bar.test.ts` — 9.5 ✓
   ```

   **If any file scores ≤ 9.8**, include the detailed review findings in the report and fix them before proceeding, following the same fix-and-recheck loop as Step 5.

8. **SonarQube quality gate.**

   After the CodeScene MCP pass, run the SonarQube quality gate. This works independently of
   the editor and worktree status — no files need to be open, no editor required.

   **Important:** SonarQube is a project-level check, not a file-level check. It analyses the
   state of the branch, not individual files. Run it to catch issues that diagnostics-exporter
   and CodeScene may miss (security hotspots, vulnerability injections, coverage gaps, duplication).

   1. **Run the quality gate:** Invoke `sonarqube:sonar-quality-gate`.
      ```
      Skill: sonarqube:sonar-quality-gate
      ```
      - **Pass:** clean — no action needed.
      - **Fail:** the gate reported one or more failed conditions. Drill into issues (step 2).

   2. **If the gate fails, drill into issues:** Invoke `sonarqube:sonar-list-issues` scoped to
      the project. Filter to issues on the changed files (pass the file paths to focus the search).
      ```
      Skill: sonarqube:sonar-list-issues
      ```
      **Attempt to fix every finding.** Only skip a finding if the fix would:
      - Require changes to >5 unrelated files
      - Touch infrastructure/config outside the feature scope
      - Involve generated code or third-party vendored code
      - Require a coordinated migration across multiple services

      In those cases, document the finding and the specific reason for skipping.
      Do NOT skip with a generic "pre-existing" label — state what makes it unfixable now.

   3. **Confirm resolution:** Re-run `sonarqube:sonar-quality-gate` after fixes. If the gate
      still fails on issues you cannot fix (with documented reasons per step 2), note them
      in the report and proceed — do not block on documented, genuinely-unfixable debt.

   Report SonarQube results alongside the CodeScene scores:

   ```
   ### SonarQube Quality Gate
   - Quality Gate: **PASS** ✓
   - Bugs: 0 | Vulnerabilities: 0 | Code Smells: 0 | Coverage: 82%
   ```

   Or on failure:

   ```
   ### SonarQube Quality Gate
   - Quality Gate: **FAIL** ✗
   - Failed conditions: Coverage < 80% (actual: 76%), New Bugs > 0 (found: 2)
   - `src/foo/bar.ts:42` — Potential SQL injection (fixed)
   - `src/old/legacy.ts:15` — Unused parameter (skipped: requires refactor of 12 call sites across 3 packages)
   ```

   **This is a blocking gate** for issues you can fix. Issues with documented,
   genuine blockers are noted but do not block.

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

```
## Diagnostics Report

**Files checked:** 3 | **With issues:** 1 | **Clean:** 1 | **No diagnostics:** 1

### Errors
- `src/foo/bar.ts:42:5` [ts/2304] — Cannot find name 'foo'

### Warnings
- `src/foo/bar.ts:15:1` [codescene/brain-method] — Complex method detected

### Clean
- `src/foo/types.ts` — No issues

### No diagnostics available
- `tests/helpers/baz.test.ts` — Extension has not exported diagnostics for this file

### Code Health (MCP)
- `src/foo/bar.ts` — 7.2 ⚠ (complex conditional, bumpy road)
- `src/foo/types.ts` — 10.0 ✓

### SonarQube Quality Gate
- Quality Gate: **PASS** ✓
- Bugs: 0 | Vulnerabilities: 0 | Code Smells: 1 (skipped: requires refactor of 12 call sites across 3 packages) | Coverage: 82%
```
