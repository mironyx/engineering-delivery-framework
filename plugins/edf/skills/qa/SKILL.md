---
name: qa
description: Quality assurance — executes E2E tests via Playwright, validates integration contracts, audits cross-story coverage, and produces a quality gate report. Invoked after edf:lld, before edf:feature, or post-implementation against a running app.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, Skill
---

# QA — Quality Assurance Skill

Validates the implementation surface described by the LLD against reality. Operates in three modes:

- **`pre`** — design-time only: contract validation, invariant checks, coverage audit. No app needed.
- **`post`** — runtime verification: BDD-based E2E tests + all pre-mode checks against a running app.
- **`exploratory`** — everything in `post` plus creative edge-case hunting. BDD specs are a starting point, not the script. The QA explorer tries to break the system.

## Arguments

`$ARGUMENTS` determines the scope:

- **Epic mode** (e.g., `epic 45`, `epic <id>`): QA a specific epic.
- **Version mode** (e.g., `v12`, `version 12`): QA all epics in a version.
- **No arguments**: Ask the user which epic or version to target.

All other parameters read from `kb/qa-config.json` by default and can be overridden on the command line:

- **`--app-url <url>`**: The base URL of the running application.
- **`--mode pre|post|exploratory`**: Design-time only (`pre`), BDD-based runtime QA (`post`, default), or full exploratory edge-case hunting (`exploratory`).
- **`--no-auth`**: Skip authentication entirely.
- **`--auth-role <role>`**: Which role to sign in as. Resolves to a GitHub username via the config file's `roles` map. Default: the config file's `default_role`, or `admin`.
- **`--auth-user <github-username>`**: GitHub username directly — bypasses the role map. Default: `$env:QA_USER`.
- **`--qa-config <path>`**: Override the default config file path. Default: `kb/qa-config.json`.

**Resolution order** (first wins): CLI flag > `kb/qa-config.json` > `$env:QA_USER`.

## QA config file

The file at `kb/qa-config.json` (or `--qa-config <path>`) supplies defaults so you can run `/qa epic 45` without repeating arguments:

```json
{
  "app_url": "http://localhost:3000",
  "default_role": "admin",
  "exploratory_budget_minutes": 5,
  "roles": {
    "admin": "leonid-mironyx",
    "admin_repo": "leonid-mironyx",
    "participant": "leonid-mironyx-test"
  }
}
```

`app_url` and `default_role` are optional in the config — if absent, the skill asks when needed. `exploratory_budget_minutes` controls the self-managed time budget per epic in exploratory mode (default 5). `roles` is required only if you use `--auth-role`; the keys are role names meaningful to your app, and the values are GitHub usernames available in the machine's GitHub session.

**Human prerequisites** (not automated by this skill):
- The GitHub accounts must be logged in on the machine where the agent runs
- The accounts must be authorized with the app (first-time OAuth consent already completed)
- If an account is not in the picker list, the agent reports it and stops — the human adds it

## Critical rules

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing mode routing, agent spawns, or the quality report structure.

These override any conflicting instinct. Violations are the top cost drivers.

1. **Pass fully-resolved `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-*.sh` commands to sub-agents.** `${CLAUDE_PLUGIN_ROOT}` is resolved by Claude Code in skill markdown. No `EDF_SCRIPTS` variable, no `.env` reading — the `bash` prefix avoids execute-bit issues. Infer `<ts|p>` from file extensions: `.ts/.tsx` → `ts`, `.py` → `p`. Use `all` if the QA scope spans both languages.
2. **Use agents for all verification, never inline.** E2E scenarios run in `edf:qa-executor`, invariants run in `edf:test`, integration contracts run in `edf:qa-contracts`, coverage audit runs in `edf:qa-coverage`. Zero verification output reaches the main context.
3. **Pass pointers to sub-agents, not content.** File paths, epic IDs, LLD paths, version slugs. Never paste diffs, file contents, or BDD spec text into agent prompts — let agents read the files they need.

## Playwright MCP setup

The `edf:qa-executor` and `edf:qa-explorer` agents require Playwright MCP for browser automation. EDF scaffolds a `.mcp.json` at the project root (via `edf:migrate`, or copy `starters/.mcp.json` manually). You do **not** need the separate `playwright@claude-plugins-official` plugin — uninstall it if present to avoid duplicate server registration.

The default config (`npx @playwright/mcp@latest`) uses the `chrome` channel. This works out of the box on macOS and Windows where Chrome is installed. On Linux and WSL, `/opt/google/chrome/chrome` is typically absent — add `--executable-path` to the **project's** `.mcp.json` to point at the Playwright-bundled Chromium:

```json
{
  "playwright": {
    "command": "npx",
    "args": ["@playwright/mcp@latest", "--executable-path", "<path from table below>"]
  }
}
```

| Platform | Chromium path | How to find it |
|---|---|---|
| **Linux / WSL** | `~/.cache/ms-playwright/chromium-<version>/chrome-linux64/chrome` | `find ~/.cache/ms-playwright -maxdepth 2 -iname chrome` |
| **macOS** | `~/Library/Caches/ms-playwright/chromium-<version>/chrome-mac/Chromium.app/Contents/MacOS/Chromium` | `find ~/Library/Caches/ms-playwright -maxdepth 3 -iname Chromium` |
| **Windows** | `%USERPROFILE%\.cache\ms-playwright\chromium-<version>\chrome-win64\chrome.exe` | `dir /s /b %USERPROFILE%\.cache\ms-playwright\chrome.exe` |

If the Playwright Chromium is not cached, install it once: `npx playwright install chromium`.

**This fix lives in the project repo — it survives EDF updates, Playwright plugin updates, and reinstalls.** Restart Claude Code after editing `.mcp.json` (MCP servers pick up config changes on session start).

## Process

### Step 0: Orient

Determine the version slug `v<N>` from `$ARGUMENTS` or by asking the user.

**Load QA config.** Read `kb/qa-config.json` (or the path from `--qa-config`). Extract `app_url`, `default_role`, `exploratory_budget_minutes`, and `roles`. CLI flags override these values. If the file doesn't exist and no CLI overrides are provided, ask the user for the missing values.

Read in order:
1. The requirements doc — `docs/requirements/v<N>-requirements.md`
2. The HLD — `docs/design/v{N}/v{N}-design.md` (or `docs/design/v{N}-design.md` in old flat structure)
3. `kb/architecture.md` — for helper catalogue and conventions

**Locate LLD and coverage files.** The design directory may follow the new version-foldered convention (`docs/design/v{N}/`) or the old flat convention (`docs/design/`). Use Glob to find the actual paths:

```bash
glob: docs/design/v{N}/lld-*.md
glob: docs/design/lld-v{N}-*.md
glob: docs/design/v{N}/coverage-*.yaml
glob: docs/design/coverage-*.yaml
```

If both new and old paths exist for the same version, prefer the new structure and warn about the stale flat copies.

**Version mode vs. epic mode:** If the scope is a version (multiple epics), do NOT read all LLDs in-memory here — Step 1 will spawn sub-agents per epic to extract BDD specs and invariants, avoiding context exhaustion. For a single epic, read the LLD now:
4. The LLD file — resolved path from the Glob above. **Resolve to absolute** (`REPO_ROOT=$(git rev-parse --show-toplevel)`) before passing to sub-agents — sub-agent CWD may differ from yours.

If `app_url` is set, verify the app is reachable:
```bash
curl -s -o /dev/null -w "%{http_code}" <app-url>
```
If unreachable, warn but continue in pre-mode for contract checks.

### Step 0b: Authenticate (post-implementation only)

**Skip if `--mode pre`, `--no-auth`, or no `app_url`.**

The default auth model is GitHub OAuth with an account picker. The human ensures the test GitHub accounts are logged in on the machine; the QA agent's only job is to pick the right one.

Resolve the target GitHub username: `--auth-user` > `qa-config.json roles[--auth-role]` > `qa-config.json roles[default_role]` > `$env:QA_USER`. If none of these are set, ask the user.

#### 0b-1: Restore saved auth state (cross-session persistence)

The Playwright MCP starts a fresh browser per Claude session. To avoid re-authenticating every session, save and restore cookies via `browser_run_code_unsafe`.

Check whether `kb/qa-auth-state.json` exists (use Bash `test -f`). If it does:

```
browser_run_code_unsafe(code: "async (page) => {
  const fs = require('fs');
  const state = JSON.parse(fs.readFileSync('kb/qa-auth-state.json', 'utf-8'));
  await page.context().addCookies(state.cookies);
  return 'cookies restored';
}")
```

Then navigate to `<app-url>`. If the restored GitHub OAuth session cookie is still valid, the app loads directly — skip the rest of Step 0b.

If the file doesn't exist or the app still redirects to GitHub OAuth after restore, proceed through the normal auth flow below.

#### 0b-2: Authenticate

1. Navigate to `<app-url>` (if not already there from 0b-1).
2. If the app loads directly (already authenticated via restored cookies), skip auth.
3. If redirected to a GitHub OAuth page showing an account list:
   - Take a snapshot and find the account matching the resolved username
   - Click it
   - Wait for redirect back to the app
   - Verify the app loaded with the correct user (snapshot for the username or avatar)
4. If the GitHub page shows a "Sign in to GitHub" form (no accounts on this machine): **stop and report** — the human needs to sign into GitHub first.
5. If the app shows its own login screen (not GitHub): fall back to the `qa-config.json` file's `login` section if one exists. Otherwise **stop and ask** — the app's auth flow differs from the default GitHub OAuth assumption.

#### 0b-3: Save auth state

After successful authentication (app loaded with correct user), persist cookies for the next session:

```
browser_run_code_unsafe(code: "async (page) => {
  const fs = require('fs');
  const state = await page.context().storageState();
  fs.writeFileSync('kb/qa-auth-state.json', JSON.stringify(state, null, 2));
  return 'auth state saved';
}")
```

Then ensure the file is gitignored (one-time setup — only if not already covered):

```bash
grep -q 'qa-auth-state' .gitignore 2>/dev/null || echo 'kb/qa-auth-state.json' >> .gitignore
```

**Session persistence note:** The Playwright MCP browser instance is shared across the skill session. Once authenticated, cookies persist. Every spawned `qa-executor` or `qa-explorer` agent inherits the authenticated session. If an agent reports `BLOCKED` (redirected to login), re-authenticate and re-run that scenario. The `kb/qa-auth-state.json` file bridges auth across Claude Code sessions — it's gitignored automatically on first save.

### Step 1: Extract testable scenarios from the LLD

The LLD is the sole source of truth for what to test. Extraction approach depends on scope:

**Version mode (multiple epics):** Spawn one `Explore` agent per epic LLD to extract BDD specs and invariant tables. Each agent returns a compact summary — the main agent never loads full LLD text, keeping context free for E2E execution.

For each epic in the version:
```
Agent({subagent_type: "Explore", description: "Extract BDD specs from epic <id> LLD", prompt: "Read the LLD file at <resolved-path> (found via Glob in Step 0) and extract ONLY:

1. BDD Specs — full text of every describe/it block (include the it() descriptions verbatim)
2. Invariants table — each row: invariant text + Verification method

Return just these two sections. Do NOT return the full LLD content. Be thorough: every BDD spec, every invariant."})
```

Run all epic agents in parallel (they're read-only). Aggregate their results into the in-memory scenario list, then print the summary:

```
## QA Scenario Summary — Version v<N> (M epics)

E2E scenarios (from BDD specs):   N
Invariant checks:                  N
Acceptance criteria assertions:    N
Visual state checks:               N
API contract checks:               N
---
Total:                             N
```

If any single epic has >80 scenarios, warn the user and suggest narrowing scope to that epic first.

**Epic mode (single epic):** The LLD was already read in Step 0. Extract scenarios in-memory from these LLD sections:

**A. BDD Specs → E2E scenarios**
Every BDD spec in the LLD (`describe`/`it` blocks) maps to a browser-based test scenario. The `it()` descriptions become the test steps. Track the mapping:
```
LLD source → scenario id → description
```

**B. Invariants → verification checks**
Every invariant in the LLD's Invariants table with a `Verification` method becomes a check. Classify by type:
- `test` → can be verified by running existing unit tests
- `type` → can be verified by type-checking
- `grep` → can be verified by grepping the codebase
- `lint` → can be verified by running the linter

**C. Acceptance Criteria → pass/fail assertions**
Each AC in the LLD becomes a binary assertion. For post-implementation mode, each AC is tested against the running app.

**D. Visual Specifications → visual checks**
Every screen in the LLD's Visual Specifications table with states (Loading, Error, Empty, Success, etc.) becomes a visual check. For post-implementation, the QA executor navigates to each screen and verifies each state is reachable and renders correctly.

**E. API contracts → integration checks**
Every API route declared in Part B (Backend layer) becomes an integration check:
- Endpoint path and method
- Expected request shape (from function signatures)
- Expected response shape (from return types)
- Error cases (from error handling section)

Build an **in-memory scenario list** — do NOT write a test plan file. Print a summary:

```
## QA Scenario Summary — Epic <id>

E2E scenarios (from BDD specs):   N
Invariant checks:                  N
Acceptance criteria assertions:    N
Visual state checks:               N
API contract checks:               N
---
Total:                             N
```

### Step 2: Execute E2E tests (post-implementation only)

**Skip if `--mode pre` or no `--app-url`.**

For each E2E scenario identified in Step 1A, spawn the `edf:qa-executor` agent:

```
Agent({subagent_type: "edf:qa-executor", description: "QA scenario <id>", prompt: "app_url: <app-url>
scenario_id: QA-<epic-id>-<N>
description: <from BDD spec>
expected_behavior: |
  - <step 1 from BDD>
  - <step 2 from BDD>
  ...
visual_reference: <path to vis screenshot in LLD, or 'none'>
lld_section: <LLD anchor or section reference>
auth_established: true
assertions:
  - <assertion 1 — what must be true>
  - <assertion 2>
starting_url: <optional — specific page to start from>"})
```

**Execution strategy:**
- Run scenarios sequentially (browser state is shared). Do not parallelise.
- If a scenario fails, the qa-executor agent captures a screenshot and reports failure. Continue to the next scenario.
- If 3 consecutive scenarios fail, pause and ask the user whether to continue — the app may be in a broken state.
- Each agent invocation covers one scenario. The scenario prompt is compact — scenario ID, description, steps, assertions — not file contents.

### Step 2b: Exploratory testing (exploratory mode only)

**Skip if not `--mode exploratory`.**

After BDD verification establishes a baseline, spawn the `edf:qa-explorer` agent to hunt for breakage. The explorer reads the LLD for context (screens, flows, API contracts) but is not constrained by it — it actively looks for what the spec didn't anticipate.

For each epic:
```
Agent({subagent_type: "edf:qa-explorer", description: "Exploratory QA for epic <id>", prompt: "app_url: <app-url>
epic_id: <epic-id>
lld_path: <resolved LLD path from Step 0>
auth_established: true
budget_minutes: <exploratory_budget_minutes from config>"})
```

Run one explorer per epic. If version mode has multiple epics, run explorers sequentially (shared browser state). The explorer walks the happy path once for orientation, then attacks edges: input boundaries, interaction abuse (double-submit, back button, refresh mid-flow), state manipulation (URL hacking, stale state), error handling, and visual stress (viewport resize, long text overflow).

The explorer returns a severity-ranked finding list — it does not list what works, only what's broken. Findings are self-contained: the main agent never sees the full exploration trace, only the verdict table and evidence for High+ findings.

### Step 3: Integration contract validation

Delegate to the `edf:qa-contracts` agent. This keeps all grep output, HTTP responses,
and schema comparisons out of the main context.

```
Agent({subagent_type: "edf:qa-contracts", description: "Contract validation for epic <id>", prompt: "mode: <pre|post>
lld_path: <resolved LLD path from Step 0>
app_url: <app-url or empty for pre-mode>
epic_id: <epic-id>
version: <v{N}>"})
```

The agent reads the LLD directly, extracts API contracts from Part B, and returns
a compact pass/fail table. No contract content reaches the main context.

### Step 4: Invariant verification

Run verification for each invariant classified in Step 1B:

- `grep` invariants: run the grep command directly, record pass/fail
- `type` invariants: invoke `edf:test typecheck <ts|p>`
- `lint` invariants: invoke `edf:test lint <ts|p>`
- `test` invariants: invoke `edf:test <test-file>`

```
Skill: edf:test typecheck <ts|p>
```

Batch invariant checks per type — one invocation per check type, not per invariant.

### Step 5: Cross-story coverage audit

Delegate to the `edf:qa-coverage` agent. This keeps all manifest parsing and
REQ- cross-referencing out of the main context.

```
Agent({subagent_type: "edf:qa-coverage", description: "Coverage audit for epic <id>", prompt: "version: <v{N}>
epic_id: <epic-id>
requirements_path: docs/requirements/v<N>-requirements.md
coverage_glob: docs/design/v{N}/coverage-*.yaml"})
```

The agent reads the manifest and requirements doc directly, cross-references every
REQ- anchor, and returns a compact gap table. No manifest content reaches the main context.

### Step 6: Quality report

Produce the report at `docs/reports/qa/<YYYY-MM-DD>-v{N}-qa-report-<epic-id>.md`.

Create the directory if it doesn't exist:
```bash
mkdir -p docs/reports/qa
```

**Template:**

```markdown
# QA Report — Epic <epic-id>: <epic title>

**Date:** <today>
**Version:** v<N>
**Mode:** pre | post | exploratory
**App URL:** <url or "N/A">

## 1. Summary

| Dimension | Total | Passed | Failed | Skipped |
|-----------|-------|--------|--------|---------|
| E2E scenarios | N | N | N | N |
| Integration contracts | N | N | N | N |
| Invariants | N | N | N | N |
| Acceptance criteria | N | N | N | N |
| Visual states | N | N | N | N |
| Coverage audit | N entries | N covered | N gaps | — |

**Overall verdict:** PASS | PASS WITH GAPS | FAIL

## 2. E2E Results

| ID | Scenario | Result | Evidence |
|----|----------|--------|----------|
| QA-<epic>-1 | <description> | PASS | — |
| QA-<epic>-2 | <description> | FAIL | [Screenshot](qa-v<N>-<epic>-2-fail.png), console errors: ... |

## 2b. Exploratory Findings (exploratory mode only)

| # | Severity | Screen | What happened | Expected |
|---|----------|--------|---------------|----------|
| 1 | High | /checkout | Double-submit created duplicate order | Should idempotent-guard |

**Edge coverage:**

| Category | Tested | Notes |
|----------|--------|-------|
| Input edges | Yes | — |
| Interaction edges | Yes | Double-submit, back button |
| State edges | Yes | URL hacking |
| Error handling | Partial | 500 path not reachable |
| Visual edges | Yes | 320px layout broken on /settings |

## 3. Integration Contract Results

| Endpoint | Method | Expected | Actual | Result |
|----------|--------|----------|--------|--------|
| /api/... | POST | 201 + `{id, name}` | 201 + `{id, name}` | PASS |

## 4. Invariant Verification

| # | Invariant | Method | Result |
|---|-----------|--------|--------|
| 1 | <invariant text> | grep / type / test | PASS |

## 5. Acceptance Criteria

| AC | Source | Result | Notes |
|----|--------|--------|-------|
| AC-1 | [lld §N.N](#) | PASS | — |

## 6. Visual State Coverage

| Screen | State | Result | Evidence |
|--------|-------|--------|----------|
| Login | Loading | PASS | — |
| Login | Error | FAIL | State not reachable — form validation prevents error submission |

## 7. Coverage Audit

| REQ- anchor | LLD | Issue | Status | Gap? |
|-------------|-----|-------|--------|------|
| REQ-xxx-yyy | lld-...md#LLD-... | #42 | Implemented | — |
| REQ-xxx-zzz | null | null | Draft | **Uncovered** — no LLD section |

## 8. Gaps and recommendations

- <gap 1>: <recommendation>
- <gap 2>: <recommendation>
```

### Step 7: Human gate

Present the report path and summary verdict. Wait for user confirmation.

If the user identifies issues:
- E2E failures → the user may re-run specific scenarios or fix the app
- Coverage gaps → the user may decide to defer, create issues, or update the manifest
- Contract mismatches → flag for `edf:lld-sync` reconciliation

### Step 8: Session log

Follow `.claude/skills/shared/session-log.md`. Use `<skill>=qa` and `<slug>=<epic-id>` (e.g. `qa-e11`).

In addition to the standard sections, the QA session log must include:

**QA execution summary** — a compact table of what ran:

```markdown
## QA execution summary

| Dimension | Total | Passed | Failed | Blocked | Skipped |
|-----------|-------|--------|--------|---------|---------|
| E2E scenarios | N | N | N | N | N |
| Exploratory (epics) | N | N findings | — | — | — |
| Integration contracts | N | N | N | — | N |
| Invariants | N | N | N | — | N |
| Visual states | N | N | N | N | N |
| Coverage entries | N | N | N gaps | — | — |

**Auth:** <method> — <note: picker worked, session expired, etc.>
**Playwright issues:** <or "none">
```

**LLD testability feedback** — which BDD specs or ACs in the LLD were ambiguous when translated to executable tests. This feeds back into LLD quality:

```markdown
## LLD testability feedback

- **Clear:** <N> scenarios — BDD specs translated directly to executable steps
- **Ambiguous:** <N> scenarios — <example: "BDD said 'user can manage items' but didn't specify CRUD operations">
- **Missing:** <N> gaps — <example: "no error-path BDD spec for payment decline">
```

**Skill self-reflection** — what the QA skill got right and what it struggled with. Be specific and concrete:

```markdown
## Skill self-reflection

### What worked
- <one thing the skill did well this session>

### What didn't work
- <specific friction: unclear step, missing guardrail, agent instruction gap>

### Improvement suggestion
- <one concrete change to SKILL.md or qa-executor.md>
```

Commit the session log separately from the QA report:

```bash
git add docs/sessions/YYYY-MM/<filename>
git commit -m "docs(sessions): qa session for <epic-id>"
```

## Guidelines

- **LLD is the starting point, not the boundary.** BDD specs guide verification, but the explorer hunts beyond them. Spec gaps found during exploratory testing are findings, not out-of-scope. In `post` mode, stick to BDD-traceable scenarios.
- **Pre-mode is always available.** Even without a running app, contract validation, invariant checks, and coverage audit provide value. Don't skip QA just because the app isn't running.
- **Failures are findings, not errors in the QA process.** A failed E2E test means the app has a bug — report it, don't fix it  (unless the user asks).
- **Keep the report actionable.** Each gap or failure must have a clear next step: fix the app, update the LLD, create an issue, or accept the risk.
- **Coverage manifest is authoritative for cross-story audit.** If it's missing, flag it — the `edf:lld` skill should have created it.
