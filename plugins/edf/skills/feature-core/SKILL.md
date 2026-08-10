---
name: feature-core
description: Core implementation cycle: read design, TDD, verify, diagnostics, commit, PR, CI probe, review, report. Called by edf:feature and edf:feature-team skills after branch setup.
allowed-tools: Read, Write, Edit, MultiEdit, Bash, Glob, Grep, Agent, Skill, TodoWrite, WebFetch, WebSearch
---

# Feature Core — Implementation Cycle

Executes the implementation cycle from design reading through PR review. Called after:

- The feature branch is checked out and current
- The board item is set to In Progress
- The session has been tagged

**Usage:** `/feature-core <issue-number>` — not typically invoked directly; called by `/feature` and `/feature-team` skills.

## Critical rules

These override any conflicting instinct. Violations are the top cost drivers.

1. **Pass fully-resolved `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-*.sh` commands to sub-agents.** `${CLAUDE_PLUGIN_ROOT}` is resolved by Claude Code in skill markdown. No `EDF_SCRIPTS` variable, no `.env` reading — the `bash` prefix avoids execute-bit issues.
2. **Never run tests without a file filter in Step 4.** Use `edf:test <test-file>`. The full suite runs once in Step 5 — nowhere else. The skill auto-infers language from file extensions.
3. **Step 5 uses `edf:test` skill.** All verification runs through the skill — zero test output reaches the main context. This applies to single-file runs during the fix loop too.
4. **Pass pointers to sub-agents, not content.** File paths, issue numbers, LLD paths. Never paste diffs or file contents into agent prompts.
5. **Review agents run in-process, not out-of-process.** All review agents (`edf:feature-evaluator`, `edf:pr-review`, `edf:ci-probe`, `edf:lld-review`, `edf:hld-review`, `edf:requirements-review`) are spawned via `Agent({subagent_type: "edf:xxx"})` — they run inside the calling session, share the CWD, and return findings directly to the caller. Only `edf:feature-team` teammates should be out-of-process (separate git worktree, separate session). Do not launch review agents with worktree isolation or as external processes.
6. **Never invoke `/simplify`.** Only if the user explicitly asks.
7. **Do not move the board item to Done.** `/feature-end` handles that.

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing step order, adding/removing agent spawns, or modifying branching logic.

## Managing technical debt

**Rule: if you knowingly leave something unfixed, leave a visible marker.**

When you defer a fix, skip a refactor, accept a rough edge, or hit a limitation that prevents
a full resolution — **leave a `TODO` comment in the code**. Tech debt that lives only in PR
comments or session logs is invisible to the next developer who reads the file. A `grep TODO`
in the source tree should surface everything that was intentionally deferred.

Each TODO must:
1. **Reference the issue or PR number** for traceability (e.g. `#42` or `PR #128`)
2. **Describe what should be done** and why it was deferred
3. **Be on its own line** so `grep -rn "TODO" src/` catches it without extra context

Pattern:
```
// TODO(#123): Refactor this cache once the shared invalidation layer lands (PR #456).
// Deferred — the fix here is correct but duplicated; consolidation is tracked separately.
```

Prefer `TODO` over `FIXME`, `HACK`, or `NOTE` — it is the single convention every editor
highlights and every grep finds. Keep them in source files (not test files, not config) so
they sit where the next developer will actually see them.

**When to leave a TODO (non-exhaustive):**
- A PR review finding was deferred (Step 9 non-blocking suggestion)
- A diagnostic finding was intentionally not fixed (Step 6 false positive or out-of-scope)
- A design deviation created a known gap that the LLD expects but was cut for scope
- A dependency or util doesn't exist yet and a stub was written instead
- A refactor opportunity was noted but is too large for the current PR

**Do NOT leave TODOs for:** things you plan to fix in the same PR, obvious typos, or
temporary debugging code (remove that before committing).

## Steps — Shared preamble

Execute sequentially. Do not skip steps. Do not ask for confirmation — only pause on blockers.

### Step 3: Read design context

1. Read the issue body: `gh issue view <issue-number>`.
2. **Epic guard:** Check the issue labels. If the issue has the `epic` label, stop: "Issue #N is an epic, not a task. Use `/feature epic <N>` to pick a task within it."
3. Read all files referenced in the issue body (design docs, LLDs, type files, related source).
   **Path resolution:** Issue body paths are repo-root-relative (e.g. `docs/design/v1/lld-foo.md`).
   Resolve them to absolute before passing to sub-agents — sub-agents may not share your CWD.
   ```bash
   REPO_ROOT=$(git rev-parse --show-toplevel)
   # Then read/use: $REPO_ROOT/docs/design/v1/lld-foo.md
   ```
4. Read any existing source files in the target directory.
5. Understand the contract: inputs, outputs, types, error cases.

### Step 3a: Verify external surfaces before coding against them

Read the `## External Surfaces` table at the top of Part B of the LLD. It pins every
surface whose contract is defined outside this repo — packages and SDKs, but also protocol
and wire-format specifications (MCP, OAuth, webhook formats), cloud/IaC providers, and
third-party HTTP APIs.

**The pinned version is binding.** Implement against the version or dated revision in the
table, not against whatever version you recall. If the table pins `MCP 2025-06-18`, the
implementation targets that revision even where your recollection of the protocol differs.

For each row, act on the `New to repo` and `Verified` columns:

| Row state | Action before writing code |
|-----------|---------------------------|
| `New to repo: Yes` | `WebFetch` the Doc URL and read the contract you are about to implement. Mandatory — there is no in-repo precedent to imitate, so the alternative is writing it from training recall. |
| `Verified: Unverified` | `WebFetch` the Doc URL, or `WebSearch` for the pinned version's docs if no URL is given. Resolve the claim before coding on it. |
| `New to repo: No` **and** `Verified: Yes` | No research. Follow the existing in-repo usage — grep for it and match the established pattern. This is the cheap path and it is the common case. |

Cost is bounded by design: a surface is `New to repo` once in the life of the repo, and
routine work on established surfaces triggers no fetches at all.

**If the LLD has no External Surfaces table** (written before this convention, or the issue
has no LLD) and this change codes against an external surface: identify the surface, grep
the repo for prior use, and if there is none, fetch its current docs before coding. Note the
gap in the PR body under `## Design deviations` so `/lld-sync` backfills the table.

State in one line which rows you fetched and which you skipped, so the choice is visible in
the session log.

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

**How to estimate:** Count the lines of production code you expect to add or modify —
every source file counts, including scripts, tooling, utilities, and migration helpers.
The only exclusions are test files, docs, and config. Use your approach from Step 3b
as the basis — you know the fix by now.

**Critical — "Files touched" means source files only.** Test files are excluded from
the file count. A change touching 1 source file and 5 test files counts as 1 file,
not 6. State both numbers explicitly: src lines, src files, and test files separately.

| Tier | Estimated src lines | Source files touched | Track |
|------|-------------------|---------------------|-------|
| **Light** | < 30 lines | <= 3 files | Inline tests, no sub-agents, `edf:diag` on `src/` only, skip evaluator |
| **Standard** | 30-150 lines | any | test-agent -> implement, full `edf:diag`, evaluator |
| **Heavy** | 150+ lines | any | Same as Standard; consider splitting into sub-issues |

**Do not default on instinct.** The table is the decision, not a suggestion. "It's just
tooling" or "it's a bug fix" are not tier criteria — line count and file count are.
Estimate both explicitly before picking a tier. If you find yourself reasoning backward
from a desired tier, stop and count.

**When in doubt, round up.** The cost of over-classification is a few extra steps. The
cost of under-classification means missing the test-author and evaluator sub-agents and
their coverage validation. If you are unsure between Light and Standard, pick Standard.

**Security-sensitive changes escalate verification.** If the change touches authN/Z,
payments, PII, secrets, or parsing untrusted external input, raise the *verification tier*
to Standard even if under 30 lines: Step 6 `edf:diag` runs on all changed files (not just
`src/`), and Step 6b `edf:feature-evaluator` runs its security-boundary adversarial pass.
Implementation stays inline (Step 4L) — this is verification depth, not process weight.

State the estimated line count, file count, tier, and reasoning before proceeding:
> **Pressure: Standard** — ~45 lines across 2 source files (3 test files).

### Step 3dF: Create session log

Create the session log **now**, before writing any code. This captures
design rationale before context compacts, and the cost checkpoint table is appended
incrementally through the pipeline. `/feature-end` will add the narrative sections
later.

1. Derive the feature ID:
   ```bash
   FEATURE_ID="${EDF_FEATURE_PREFIX}-<issue-number>"
   ```
   Read `${EDF_FEATURE_PREFIX}` from the project `.env`; it was set during `/setup`.
2. Derive the slug from the issue title (kebab-case, 2-4 words).
3. Determine N: count existing session logs for today in `docs/sessions/YYYY-MM/` and increment.
4. Create the file at `docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md`:
   ````markdown
   # Session log — [FEATURE_ID]

   ## Approach rationale
   - **Issue:** #<N>
   - **Approach chosen:** <1-2 sentences from Step 3b>
   - **LLD deviations:** <what changed and why, or "none">
   - **Pressure:** <standard | heavy> — <reasoning from Step 3c>

   ## Cost checkpoints
   | Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
   |------|-----------|--------------------|----------------------|------|
   ````
   Then immediately append the Step 3c checkpoint row with a live timestamp and cost query:
   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/append-checkpoint.py \
     --session-log "docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md" \
     --step "3c" \
     --note "pressure: <tier> — <reasoning>" \
     --issue <N>
   ```
   The script captures `date -u` and queries Prometheus at the moment it runs.
   Cost/token values are materialised immediately — no placeholders to fill later.
   **If cost is unavailable:** Prometheus is not configured or unreachable.
   The script writes "unavailable" for cost/tokens and continues. To enable cost
   tracking, set up a Prometheus instance scraping the node_exporter textfile
   collector from the directory in `EDF_FEATURE_PROM_DIR` (see `.env`).
5. Stage the file immediately so it survives:
   ```bash
   git add docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md
   ```
   Do NOT commit yet — the file is live and will be amended with cost checkpoints.

This file is the session log. No rename later — `/feature-end` appends the remaining
sections (work completed, LLD sync report, cost retrospective) into the same file.
Do NOT use a `-draft` suffix — that is reserved for the compaction hook.

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
   bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh <ts|p> <test-file>
   ```
   Runs only the affected test file (the script takes an optional path argument). Do not launch a sub-agent for this — the output is compact and belongs in the main context.
4. **Boy Scout rule** — when you edit a file, leave it cleaner than you found it: fix dead
   code, duplication, or obvious naming problems on the lines you touch; never leave the
   touched code worse than it was. Scoped to touched lines only — never refactor unrelated code.

Proceed to Step 5.

---

## Full track — features, >=30 src lines

Tests must be written by a separate agent against the spec only, before implementation.

Flow: test-agent writes tests against spec -> implement against tests.

### Step 4bF: Write stubs and hand off tests

**Write the public interface first.** Create the *public surface* of the unit under change:
exported types, schemas, function signatures, and stub bodies that throw `not implemented`.
No behaviour logic, no happy-path code, no error handling. The surface is derived from the
LLD or issue contract, not from any implementation choice.

For bug fixes the interface usually already exists — skip the stub step and go straight to
launching test-author. If the fix requires a new signature (e.g. adding a parameter), commit
the signature change first.

Then launch the `edf:test-author` agent with:

```
Launch Agent: edf:test-author
Input:
  issue_number: <N>
  requirements_paths: <list of absolute paths, e.g. ["/absolute/path/to/docs/requirements/v1-requirements.md"]>
  lld_path: <absolute path or "none"> (resolved in Step 3)
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

**Full track:** after the test-author returns, append a cost checkpoint row:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/append-checkpoint.py \
  --session-log "docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md" \
  --step "4bF" \
  --note "test-author complete — <N> BDD properties, <all covered | N gaps>" \
  --issue <N>
```

### Step 4cF: Implement against the tests

Main agent reads the test file written by the sub-agent and implements the stub bodies
to make the tests pass.

- You MAY NOT modify the tests to match what you built, except for: fixing typos in
  test names, fixing imports the sub-agent got wrong, and renaming a test for clarity
  without changing its assertion.
- If a test looks semantically wrong (sub-agent misread the spec), stop and report to the user.
- If a test is uncompilable because a type is wrong, fix the type annotation but keep the assertion.
- **Boy Scout rule** — when you edit a file, leave it cleaner than you found it: fix dead
  code, duplication, or obvious naming problems on the lines you touch; never leave the
  touched code worse than it was. Scoped to touched lines — no unrelated refactoring.

Run only the target test file after each increment:

```
Skill: edf:test <test-file>
```

### Step 4dF: Self-check coverage before Step 5

Before running the full suite, re-read the sub-agent's report and confirm every listed
property maps to a passing test. If the sub-agent missed a property you can see in the
spec, add the test yourself and note this in the Step 10 report (so we can feed it back
into the sub-agent's prompt).

**Full track:** after self-check passes, append a cost checkpoint row:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/append-checkpoint.py \
  --session-log "docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md" \
  --step "4dF" \
  --note "implementation complete" \
  --issue <N>
```

---

## Verification & diagnostics (both tracks)

### Step 5: Full verification

**CWD guard:** Confirm the shell is in the correct working directory *before* any
verification run. Subagent sessions can inherit the caller's CWD; running tests/typecheck
from the wrong directory silently corrupts results. Verify with:
```bash
git rev-parse --show-toplevel
# must be the repo (or the worktree, for team mode) you intend to verify
```

Delegate all checks to the `edf:test` skill — **do not run these as Bash directly**.
This keeps verbose output out of the main context.

```
Skill: edf:test full <ts|p>
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
Skill: edf:test e2e <ts|p>
```

The project's `run-e2e.sh` is responsible for setting any environment variables the build or
`edf:test` needs (e.g. placeholder service URLs, test API keys, etc.). The script-contract
keeps that detail inside the project, not in the skill.

Then run the dependency security audit:

```
Skill: edf:test audit <ts|p>
```

`run-audit.sh` fails only on high/critical vulnerabilities in production dependencies, and
self-skips (exit 0) when there is no lockfile/manifest, the tool is missing, or the registry
is unreachable — it cannot spuriously block. On audit failure: if the vulnerable dependency
is related to this change, fix it (bump/update); if the finding is pre-existing in the
dependency tree and unrelated, surface it to the user and record a documented deferral in
the PR body — never silently ignore it.

All must pass — zero failures, including integration tests — before proceeding.
If any fail, fix and re-run via `edf:test`. If stuck after 3 attempts on the same failure, pause and report.

After Step 5 passes, append a cost checkpoint row:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/append-checkpoint.py \
  --session-log "docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md" \
  --step "5" \
  --note "green on attempt <N>$(<any extra context like audit deferrals>)" \
  --issue <N>
```
Count the verification attempts since Step 4cF.

### Step 6: Diagnostics (blocking gate)

Run `edf:diag` on changed files. This is a **blocking gate** — do not proceed until clean.

**Scope by track:**

- **Light track:** Run `edf:diag` on changed `src/` files only. Skip test files.
- **Full track:** Run `edf:diag` on all changed files — including test files under `tests/`.

Then:

1. Run `edf:diag` on the scoped file set.
2. If any findings exist, fix them all. **Exception: ignore smells on generated files** (e.g. content under `<migration-dir>` for projects that generate migrations from a declarative schema).
3. After fixing, re-run `edf:diag` to confirm the findings are gone.
4. Repeat until `edf:diag` reports zero findings on non-generated files.
5. Re-run Step 5 (full verification) after any fixes.

**Both tracks:** after diagnostics pass clean, append a cost checkpoint row:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/append-checkpoint.py \
  --session-log "docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md" \
  --step "6" \
  --note "diag pass$(<concise findings summary if notable>)" \
  --issue <N>
```

### Step 6b: Evaluate (Full track only)

**Light track: skip this step.** Proceed to Step 7.

**Full track:** Launch the `edf:feature-evaluator` agent. Pass it:

- `requirements_paths` — same absolute list passed to the edf:test-author in Step 4bF
- `lld_path` — the LLD file absolute path from Step 3 (or the issue number if no LLD exists)
- `issue_number` — the current issue number
- `changed_files` — all `src/` files created or modified in this cycle (absolute paths)
- `test_files` — all `tests/` files created or modified in this cycle (absolute paths; including the
  file the `edf:test-author` sub-agent produced in Step 4bF)

```
Launch Agent: edf:feature-evaluator
Input: requirements_paths=<absolute list> lld_path=<absolute path> issue_number=<N> changed_files=<absolute list> test_files=<absolute list>
```

**HTTP mocking check:** verify the test files use the project's HTTP mocking convention as declared in CLAUDE.md. If they use manual stubs, spies, or monkeypatching instead, flag it as a blocker — the tests must be rewritten before the feature can proceed.

**Triage the verdict:**

- **PASS** — every acceptance criterion maps to at least one passing test, no gaps. Proceed to Step 7.
- **PASS WITH WARNINGS** — minor gaps found, evaluator added a small number of adversarial tests. Review warnings, fix quick wins, note the rest in the PR body. Proceed to Step 7.
- **FAIL** — a criterion is uncovered or an adversarial test exposed a real defect. Fix the implementation, re-run Step 5 (verification) and Step 6 (`edf:diag`), then re-run the evaluator once to confirm the previously-uncovered criteria now pass. PASS or PASS WITH WARNINGS → proceed to Step 7. FAIL again → pause and report. One re-run only — if it still fails, stop.

If evaluator writes > 3 adversarial tests, note count in Step 10 report and PR body — but do not block.

Evaluator tests follow the project's test file convention, committed in Step 7.

**Full track:** after the evaluator verdict, append a cost checkpoint row:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/append-checkpoint.py \
  --session-log "docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md" \
  --step "6b" \
  --note "evaluator: <verdict>$(<concise blocker summary if any>)" \
  --issue <N>
```

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

**PR body patch guard:** When editing the PR body, **append** to the existing body — never replace it.
The `create-feature-pr.sh` script auto-generates a `Closes #<N>` reference in the PR body.
Replacing the body silently drops that reference, which means the GitHub issue won't auto-close on merge.

How to append safely:
```bash
gh pr view <pr-number> --json body -q '.body' > updated-body.md  # capture existing body
cat >> updated-body.md << 'EOF'

## Design deviations
...
EOF
gh api repos/$(gh repo view --json nameWithOwner -q '.nameWithOwner')/pulls/<pr-number> \
  --method PATCH -F "body=@updated-body.md"
```
Note: the file must contain the **full** body (existing + appended). Read the existing body first,
concatenate, then push.

After patching, verify the closing reference is intact:
```bash
gh pr view <pr-number> --json body -q '.body' | grep -c 'Closes #<N>'
```
Must return `>= 1`. If not, fix immediately.

Append a cost checkpoint row:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/append-checkpoint.py \
  --session-log "docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md" \
  --step "8" \
  --note "[PR #<pr-number>](<pr-url>)" \
  --issue <N>
```
The PR number and URL are available from the `create-feature-pr.sh` output above.

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

Run `edf:pr-review <pr-number>` on the PR just created. This posts a comment on the PR and
returns findings. Triage each finding:

- **Blocker / correctness issue** — fix it: update the code, re-run Step 5 (verification), add a commit, push.
- **Design contract mismatch** — check whether the design or the implementation is wrong:
  if the implementation is wrong, fix it; if the design is outdated, update the design doc in the same branch.
- **Non-blocking suggestion** — decide whether it is worth fixing now (quick win) or deferring. If deferring, **leave a `TODO` comment in the affected file** (see [Managing technical debt](#managing-technical-debt)) and note it in the Step 10 report.
- **Style / minor** — fix if trivial; otherwise note and move on.

After any fixes, re-run `edf:pr-review <pr-number>` to confirm no new issues were introduced.

Once review is resolved (no blockers remain), append a cost checkpoint row:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/append-checkpoint.py \
  --session-log "docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md" \
  --step "9" \
  --note "review clean$(<concise findings summary>)" \
  --issue <N>
```

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

After the report is delivered, append a cost checkpoint row:
```bash
bash ${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh ${CLAUDE_PLUGIN_ROOT}/bin/append-checkpoint.py \
  --session-log "docs/sessions/YYYY-MM/YYYY-MM-DD-session-N-<slug>-<FEATURE_ID>.md" \
  --step "10" \
  --note "report done$(<concise CI/review outcome>)" \
  --issue <N>
```

## Blocker policy

**Pause and report** (do not attempt workarounds) if:

- Design doc is missing or ambiguous for this issue
- Tests fail after 3 fix attempts on the same error
- Type errors that suggest a design contract mismatch
- External dependency is unavailable (e.g., a function from an unmerged PR)
- Issue has no acceptance criteria

**Do NOT pause for:** lint issues, minor test adjustments, missing exports, diagnostic warnings, PR slightly over 200 lines.

If you write a workaround (e.g. stub, backfill, hardcoded value) to unblock progress when a
dependency is missing or a full fix is not possible in this PR, **leave a `TODO` comment**
(see [Managing technical debt](#managing-technical-debt)) so the stub is discoverable later.
