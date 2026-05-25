---
name: feature-core
description: Core implementation cycle: read design, TDD, verify, diagnostics, commit, PR, CI probe, review, report. Called by /feature and /feature-team skills after branch setup.
allowed-tools: Read, Write, Edit, MultiEdit, Bash, Glob, Grep, Agent, Skill, TodoWrite
---

# Feature Core — Implementation Cycle

Executes the implementation cycle from design reading through PR review. Called after:

- The feature branch is checked out and current
- The board item is set to In Progress
- The session has been tagged

**Usage:** `/feature-core <issue-number>` — not typically invoked directly; called by `/feature` and `/feature-team` skills.

## Critical rules

These override any conflicting instinct. Violations are the top cost drivers.

1. **Resolve `${EDF_SCRIPTS}` before running any command.** Read `.env` in the project root and substitute the actual value of `EDF_SCRIPTS`. If unset or `.env` is missing, default to `scripts`.
2. **Never run `${EDF_SCRIPTS}/run-tests.sh` without a file filter in Step 4.** Use `${EDF_SCRIPTS}/run-tests.sh <test-file>`. The full suite runs once in Step 5 — nowhere else.
3. **Step 5 uses `edf:test-runner` agent, not Bash.** All verification commands run inside the agent — zero test output reaches the main context. This applies to single-file runs during the fix loop too.
4. **Pass pointers to sub-agents, not content.** File paths, issue numbers, LLD paths. Never paste diffs or file contents into agent prompts.
5. **Never invoke `/simplify`.** Only if the user explicitly asks.
6. **Do not move the board item to Done.** `/feature-end` handles that.

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing step order, adding/removing agent spawns, or modifying branching logic.

## Steps — Shared preamble

Execute sequentially. Do not skip steps. Do not ask for confirmation — only pause on blockers.

### Step 3: Read design context

1. Read the issue body: `gh issue view <issue-number>`.
2. **Epic guard:** Check the issue labels. If the issue has the `epic` label, stop: "Issue #N is an epic, not a task. Use `/feature epic <N>` to pick a task within it."
3. Read all files referenced in the issue body (design docs, LLDs, type files, related source).
4. Read any existing source files in the target directory.
5. Understand the contract: inputs, outputs, types, error cases.

### Step 3b: Pick the simplest approach

Before writing any code, list 2-3 approaches in 1-2 sentences each. Pick the one that fixes the root cause with the least code. State why. Prefer fixing data at the source over adding complexity downstream (CLAUDE.md: "Simplicity first").

**Critically evaluate the LLD — do not follow it blindly.** LLD sections are written before
implementation; reality may reveal a simpler path, an incorrect assumption, an outdated pattern,
or a better structural fit. Before coding, explicitly ask: is the LLD approach still the best one?
Deviation is expected and welcome whenever you have a good reason. You must:

1. State what the LLD recommended.
2. State what you are doing instead and why it is better (simpler, more correct, better fit).
3. Note the deviation in the PR body under a `## Design deviations` section so `/lld-sync` can
   reconcile the LLD later.

Do not deviate silently — traceability matters. `/lld-sync` reads the PR body to pick up these
notes and update the design doc accordingly.

### Step 3c: Classify change pressure

After picking the approach but before writing code, estimate the change size and set the
**pressure tier**. This determines which track you follow for the rest of the pipeline.

**How to estimate:** Count the lines of production code you expect to add or modify (exclude
tests, docs, config). Use your approach from Step 3b as the basis — you know the fix by now.

| Tier | Estimated src lines | Files touched | Track |
|------|-------------------|---------------|-------|
| **Light** | < 30 lines | <= 3 files | Inline tests, no sub-agents, `/diag` on `src/` only, skip evaluator |
| **Standard** | 30-150 lines | any | Interface -> test-author -> implement, full `/diag`, evaluator |
| **Heavy** | 150+ lines | any | Same as Standard; consider splitting into sub-issues |

**Bug fixes default to Light** unless the fix is genuinely complex (multi-file refactor,
new module, schema change). A 3-line query fix does not need a 256-line test file from
a sub-agent.

State the tier and reasoning in one line before proceeding, then follow the corresponding track:
> **Pressure: Light** — 3-line query filter change in one file.

---

## Light track — bug fixes, <30 src lines, <=3 files

No sub-agents. Write the fix and regression tests in one pass.

### Step 4L: Implement with inline tests

1. **Write the fix** directly in the source file.
2. **Write 2-5 focused regression tests** in the target test file. Each test should:
   - Reference the issue number in a comment or test name
   - Test through the public interface, not internals
   - Include at least one test that would fail on the pre-fix behaviour (for bug fixes)
   - Match the style of neighbouring test files (grep for sibling tests first)
3. **Run the target test file** to confirm tests pass:
   ```bash
   ${EDF_SCRIPTS}/run-tests.sh <test-file>
   ```
   Runs only the affected test file (the script takes an optional path argument). Do not launch a sub-agent for this — the output is compact and belongs in the main context.

Proceed to Step 5.

---

## Full track — features, >=30 src lines

Tests must be written by a separate agent against the spec only, before implementation.

Flow: interface -> independent tests -> implementation -> green.

### Step 4aF: Write the interface, not the behaviour

Main agent writes only the *public surface* of the unit under change: exported types,
schemas, function signatures, and stub bodies that throw `not implemented`. No
behaviour logic, no happy-path code, no error handling. The surface is derived from the
LLD or issue contract, not from any implementation choice.

For bug fixes the interface usually already exists — skip to Step 4bF. If the bug fix
requires a new signature (e.g. adding a parameter), commit the signature change first.

The PostToolUse hook opens edited files in the editor automatically for diagnostics analysis.
If the hook fires with inline findings, address them before moving on.

### Step 4bF: Hand off to the `edf:test-author` sub-agent

**HTTP mocking constraint:** instruct the sub-agent to use the project's HTTP mocking convention as declared in CLAUDE.md (e.g. MSW for TypeScript, `respx` or `pytest-httpx` for Python) — not manual stubs, spies, or monkeypatching. The CLAUDE.md convention is authoritative; do not override it in the agent prompt.

Launch the `edf:test-author` agent with:

```
Launch Agent: edf:test-author
Input:
  issue_number: <N>
  requirements_paths: <list of paths, e.g. ["docs/requirements/v1-requirements.md"]>
  lld_path: <path or "none">
  target_test_file: <tests/.../<unit>.test.ts>
  unit_under_test: <src/.../<unit>.ts>
  mode: "feature" | "bugfix"
  pressure: "standard"
```

For `requirements_paths`: pass the project requirements doc plus any per-feature
requirements files the issue or LLD references.

**If the sub-agent reports fewer than three observable properties** or reports unresolved
spec gaps, **stop and escalate to the user** — the spec is too vague to implement against.
Do not write the tests yourself.

### Step 4cF: Implement against the tests

Main agent reads the test file written by the sub-agent and implements the stub bodies
to make the tests pass.

- You MAY NOT modify the tests to match what you built, except for: fixing typos in
  test names, fixing imports the sub-agent got wrong, and renaming a test for clarity
  without changing its assertion.
- If a test looks semantically wrong (sub-agent misread the spec), stop and report to the user.
- If a test is uncompilable because a type is wrong, fix the type annotation but keep the assertion.

Run only the target test file after each increment:

```
Launch Agent: edf:test-runner
Input: command="${EDF_SCRIPTS}/run-tests.sh <test-file>"
```

### Step 4dF: Self-check coverage before Step 5

Before running the full suite, re-read the sub-agent's report and confirm every listed
property maps to a passing test. If the sub-agent missed a property you can see in the
spec, add the test yourself and note this in the Step 10 report (so we can feed it back
into the sub-agent's prompt).

---

## Verification & diagnostics (both tracks)

### Step 5: Full verification

Delegate all checks to the `edf:test-runner` agent — **do not run these as Bash directly**.
This keeps verbose output out of the main context.

```
Launch Agent: edf:test-runner
Input: command="${EDF_SCRIPTS}/run-tests.sh && ${EDF_SCRIPTS}/run-typecheck.sh && ${EDF_SCRIPTS}/run-lint.sh"
```

Check whether E2E tests exist by reading `kb/conventions.md` for the `e2e-dir` value, then:
```bash
E2E_DIR=$(grep 'e2e-dir' kb/conventions.md | sed -n 's/.*| *e2e-dir *| *\([^|]*\) *|.*/\1/p' | sed 's/<!-- e.g. //; s/ -->//; s/`//g; s/^ *//; s/ *$//')
if [ -n "$E2E_DIR" ] && [ "$(ls -A "$E2E_DIR" 2>/dev/null)" ]; then
  echo "E2E tests found"
else
  echo "No E2E tests — skipping"
fi
```
If the directory exists and is non-empty, also run:

```
Launch Agent: edf:test-runner
Input: command="${EDF_SCRIPTS}/run-build.sh && ${EDF_SCRIPTS}/run-e2e.sh"
```

The project's `run-e2e.sh` is responsible for setting any environment variables the build or
test-runner needs (e.g. placeholder service URLs, test API keys, etc.). The script-contract
keeps that detail inside the project, not in the skill.

All must pass — zero failures, including integration tests — before proceeding.
If any fail, fix and re-run via `edf:test-runner`. If stuck after 3 attempts on the same failure, pause and report.

### Step 6: Diagnostics (blocking gate)

Run `/diag` on changed files. This is a **blocking gate** — do not proceed until clean.

**Scope by track:**

- **Light track:** Run `/diag` on changed `src/` files only. Skip test files.
- **Full track:** Run `/diag` on all changed files — including test files under `tests/`.

Then:

1. Run `/diag` on the scoped file set.
2. If any findings exist, fix them all. **Exception: ignore smells on generated files** (e.g. content under `<migration-dir>` for projects that generate migrations from a declarative schema).
3. After fixing, re-run `/diag` to confirm the findings are gone.
4. Repeat until `/diag` reports zero findings on non-generated files.
5. Re-run Step 5 (full verification) after any fixes.

### Step 6b: Evaluate (Full track only)

**Light track: skip this step.** Proceed to Step 7.

**Full track:** Launch the `edf:feature-evaluator` agent. Pass it:

- `requirements_paths` — same list passed to the edf:test-author in Step 4bF
- `lld_path` — the LLD file read in Step 3 (or the issue number if no LLD exists)
- `issue_number` — the current issue number
- `changed_files` — all `src/` files created or modified in this cycle
- `test_files` — all `tests/` files created or modified in this cycle (including the
  file the `edf:test-author` sub-agent produced in Step 4bF)

```
Launch Agent: edf:feature-evaluator
Input: requirements_paths=<list> lld_path=<path> issue_number=<N> changed_files=<list> test_files=<list>
```

**HTTP mocking check:** verify the test files use the project's HTTP mocking convention as declared in CLAUDE.md. If they use manual stubs, spies, or monkeypatching instead, flag it as a blocker — the tests must be rewritten before the feature can proceed.

**Triage the verdict:**

- **PASS** — every acceptance criterion maps to at least one passing test, no gaps. Proceed to Step 7.
- **PASS WITH WARNINGS** — minor gaps found, evaluator added a small number of adversarial tests. Review warnings, fix quick wins, note the rest in the PR body. Proceed to Step 7.
- **FAIL** — a criterion is uncovered or an adversarial test exposed a real defect. Fix the implementation, re-run Step 5 (verification) and Step 6 (`/diag`). Do NOT re-run the evaluator — proceed to Step 7 after verification passes.

If evaluator writes > 3 adversarial tests, note count in Step 10 report and PR body — but do not block.

Evaluator tests follow the project's test file convention, committed in Step 7.

---

## Shared delivery (Steps 7-10)

### Step 7: Commit

Stage and commit with a conventional commit message referencing the issue number:

```bash
git add <specific-files>
git commit -m "feat: <description> #<issue-number>"
```

One commit per issue. Do not batch multiple issues.

### Step 8: Push and create PR

```bash
git push -u origin HEAD
```

Create the PR using the script (handles PR body template, cost tracking, and session ID):

```bash
PR_URL=$(bash ${CLAUDE_PLUGIN_ROOT}/bin/create-feature-pr.sh \
  --issue <number> \
  --title "<short title>" \
  --summary "<1-3 bullet points>" \
  --design-ref "<path to design doc section>" \
  --tests-added <N> \
  --tests-total "<N (M test files)>")
PR_NUMBER=$(echo "$PR_URL" | grep -o '[0-9]*$')
```

If you deviated from the LLD (Step 3b), patch the PR body to add a `## Design deviations` section.

### Step 8b: CI probe (background)

Launch `edf:ci-probe` in the background (uses status polling). **Do not wait** — continue with Step 9.

```
Launch Agent: edf:ci-probe
Input: pr=<pr-number>
run_in_background: true
```

The background agent's completion notification only fires at a turn boundary, so the probe's report may not arrive before Step 9 starts. **Do not insert no-op tool calls to "advance turns" and force the notification** — Step 10 reconciles the CI outcome synchronously.

When the probe reports back during Step 9:

- **CI failure** — fix the root cause, push, note in the Step 10 report.
- **CI pass** — note in the Step 10 report.

### Step 9: Review

Run `/pr-review <pr-number>` on the PR just created. This posts a comment on the PR and
returns findings. Triage each finding:

- **Blocker / correctness issue** — fix it: update the code, re-run Step 5 (verification), add a commit, push.
- **Design contract mismatch** — check whether the design or the implementation is wrong:
  if the implementation is wrong, fix it; if the design is outdated, update the design doc in the same branch.
- **Non-blocking suggestion** — decide whether it is worth fixing now (quick win) or deferring. If deferring, note it in the Step 10 report.
- **Style / minor** — fix if trivial; otherwise note and move on.

After any fixes, re-run `/pr-review <pr-number>` to confirm no new issues were introduced.

### Step 10: Report

**Before summarising, reconcile CI outcome.** The Step 8b background probe may not have
reported back yet. Instead of waiting passively (which requires no-op tool calls to advance
turns and force the notification), check CI status directly with a single synchronous call:

```bash
gh pr checks <pr-number>
```

- Output shows per-check status (`pass` / `fail` / `pending`). If all complete and pass: note **CI pass** in the report.
- If any check failed: fix the root cause, push, then re-run `gh pr checks`. Note in the report.
- If any check is still pending (CI slower than the review cycle): wait synchronously with `gh pr checks <pr-number> --watch --interval 30` (foreground; no no-op turns needed). On completion, classify pass/fail.

Then summarise what was done:

- Issue number and title
- Branch and PR link
- Tests added / total
- Review outcome: what was found, what was fixed, what was deferred
- CI outcome: pass / fail (always known by this point — no "pending" in the report)
- Any warnings or notes (PR size, diagnostics findings, design drift)
- Suggested next item from the board

## Blocker policy

**Pause and report** (do not attempt workarounds) if:

- Design doc is missing or ambiguous for this issue
- Tests fail after 3 fix attempts on the same error
- Type errors that suggest a design contract mismatch
- External dependency is unavailable (e.g., a function from an unmerged PR)
- Issue has no acceptance criteria

**Do NOT pause for:** lint issues, minor test adjustments, missing exports, diagnostic warnings, PR slightly over 200 lines.
