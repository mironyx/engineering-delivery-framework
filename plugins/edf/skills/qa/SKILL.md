---
name: qa
description: Quality assurance — executes E2E tests via Playwright, validates integration contracts, audits cross-story coverage, and produces a quality gate report. Invoked after /lld, before /feature, or post-implementation against a running app.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, Skill
---

# QA — Quality Assurance Skill

Validates the implementation surface described by the LLD against reality. Operates in two modes: pre-implementation (design-time contract validation — no app needed) and post-implementation (runtime verification against a running app via Playwright MCP).

## Arguments

`$ARGUMENTS` determines the scope:

- **Epic mode** (e.g., `epic 45`, `epic <id>`): QA a specific epic.
- **Version mode** (e.g., `v12`, `version 12`): QA all epics in a version.
- **No arguments**: Ask the user which epic or version to target.

All other parameters read from `kb/qa-config.json` by default and can be overridden on the command line:

- **`--app-url <url>`**: The base URL of the running application.
- **`--mode pre|post`**: Design-time only (`pre`) or full runtime QA (`post`, default).
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
  "roles": {
    "admin": "leonid-mironyx",
    "admin_repo": "leonid-mironyx",
    "participant": "leonid-mironyx-test"
  }
}
```

`app_url` and `default_role` are optional in the config — if absent, the skill asks when needed. `roles` is required only if you use `--auth-role`; the keys are role names meaningful to your app, and the values are GitHub usernames available in the machine's GitHub session.

**Human prerequisites** (not automated by this skill):
- The GitHub accounts must be logged in on the machine where the agent runs
- The accounts must be authorized with the app (first-time OAuth consent already completed)
- If an account is not in the picker list, the agent reports it and stops — the human adds it

## Process

### Step 0: Orient

Determine the version slug `v<N>` from `$ARGUMENTS` or by asking the user.

**Load QA config.** Read `kb/qa-config.json` (or the path from `--qa-config`). Extract `app_url`, `default_role`, and `roles`. CLI flags override these values. If the file doesn't exist and no CLI overrides are provided, ask the user for the missing values.

Read in order:
1. The requirements doc — `docs/requirements/v<N>-requirements.md`
2. The HLD — `docs/design/v{N}/v{N}-design.md` (or `docs/design/v{N}-design.md` in old flat structure)
3. `kb/architecture.md` — for helper catalogue and conventions

**Locate LLD and coverage files.** The design directory may follow the new version-foldered convention (`docs/design/v{N}/`) or the old flat convention (`docs/design/`). Use Glob to find the actual paths:

```bash
glob: docs/design/v{N}/lld-v{N}-*.md
glob: docs/design/lld-v{N}-*.md
glob: docs/design/v{N}/coverage-*.yaml
glob: docs/design/coverage-*.yaml
```

If both new and old paths exist for the same version, prefer the new structure and warn about the stale flat copies.

**Version mode vs. epic mode:** If the scope is a version (multiple epics), do NOT read all LLDs in-memory here — Step 1 will spawn sub-agents per epic to extract BDD specs and invariants, avoiding context exhaustion. For a single epic, read the LLD now:
4. The LLD file — resolved path from the Glob above

If `app_url` is set, verify the app is reachable:
```bash
curl -s -o /dev/null -w "%{http_code}" <app-url>
```
If unreachable, warn but continue in pre-mode for contract checks.

### Step 0b: Authenticate (post-implementation only)

**Skip if `--mode pre`, `--no-auth`, or no `app_url`.**

The default auth model is GitHub OAuth with an account picker. The human ensures the test GitHub accounts are logged in on the machine; the QA agent's only job is to pick the right one.

Resolve the target GitHub username: `--auth-user` > `qa-config.json roles[--auth-role]` > `qa-config.json roles[default_role]` > `$env:QA_USER`. If none of these are set, ask the user.

1. Navigate to `<app-url>`.
2. If the app loads directly (already authenticated from a prior session), skip auth.
3. If redirected to a GitHub OAuth page showing an account list:
   - Take a snapshot and find the account matching the resolved username
   - Click it
   - Wait for redirect back to the app
   - Verify the app loaded with the correct user (snapshot for the username or avatar)
4. If the GitHub page shows a "Sign in to GitHub" form (no accounts on this machine): **stop and report** — the human needs to sign into GitHub first.
5. If the app shows its own login screen (not GitHub): fall back to the `qa-config.json` file's `login` section if one exists. Otherwise **stop and ask** — the app's auth flow differs from the default GitHub OAuth assumption.

**Session persistence note:** The Playwright MCP browser instance is shared across the skill session. Once authenticated, cookies persist. Every spawned `qa-executor` agent inherits the authenticated session. If an agent reports `BLOCKED` (redirected to login), re-authenticate and re-run that scenario.

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
- If a scenario fails, take a screenshot and continue to the next scenario.
- If 3 consecutive scenarios fail, pause and ask the user whether to continue — the app may be in a broken state.

**Scenario grouping:** If multiple BDD specs cover the same screen/flow, group them into a single agent invocation to reduce navigation overhead. Pass all related scenarios in one prompt with clear boundaries.

### Step 3: Integration contract validation

Validate API contracts from Step 1E. Approach depends on mode:

**Pre-implementation (`--mode pre`):**
- Type-check: for each API function signature in the LLD, grep the codebase for the actual implementation and compare types
- Schema-check: for each DB schema reference, verify the LLD types match the canonical DB types
- Route-check: verify each declared API route exists in the routing layer (grep for path patterns)

**Post-implementation (`--mode post`):**
- For each API endpoint, send a request and validate the response shape against the LLD contract
- Check HTTP status codes for error cases declared in the LLD
- If the project has an OpenAPI spec or similar, validate it matches the LLD

Run the checks inline (no sub-agent needed — contract validation is compact).

### Step 4: Invariant verification

Run verification for each invariant classified in Step 1B:

- `grep` invariants: run the grep command directly, record pass/fail
- `type` invariants: spawn `edf:test-runner` with `${EDF_SCRIPTS}/run-typecheck.sh`
- `lint` invariants: spawn `edf:test-runner` with `${EDF_SCRIPTS}/run-lint.sh`
- `test` invariants: spawn `edf:test-runner` with `${EDF_SCRIPTS}/run-tests.sh <test-file>`

```
Agent({subagent_type: "edf:test-runner", description: "Invariant verification", prompt: "command=${EDF_SCRIPTS}/run-typecheck.sh"})
```

Batch invariant checks per type — one agent invocation per command, not per invariant.

### Step 5: Cross-story coverage audit

1. Read the coverage manifest: `docs/design/v{N}/coverage-<epic-id>.yaml`
2. For every REQ- anchor in the requirements doc, verify it has a manifest entry
3. For every manifest entry:
   - Check `lld:` is non-null (story has a design section)
   - Check `issue:` is non-null (story has an implementation issue)
   - Check `status:` is not `Draft` (story is implemented or approved)
4. Flag gaps:
   - **Uncovered REQ-** — in requirements but not in manifest
   - **No LLD** — in manifest but `lld:` is null
   - **Stale Draft** — `status: Draft` for epics approved > 2 weeks ago
   - **No issue** — `status: Approved` but `issue:` is null

### Step 6: Quality report

Produce the report at `docs/reports/qa/v{N}-qa-report-<epic-id>.md`.

Create the directory if it doesn't exist:
```bash
mkdir -p docs/reports/qa
```

**Template:**

```markdown
# QA Report — Epic <epic-id>: <epic title>

**Date:** <today>
**Version:** v<N>
**Mode:** pre | post
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
- Contract mismatches → flag for `/lld-sync` reconciliation

### Step 8: Session log

Follow `.claude/skills/shared/session-log.md`. Use `<skill>=qa` and `<slug>=<epic-id>` (e.g. `qa-e11`).

In addition to the standard sections, the QA session log must include:

**QA execution summary** — a compact table of what ran:

```markdown
## QA execution summary

| Dimension | Total | Passed | Failed | Blocked | Skipped |
|-----------|-------|--------|--------|---------|---------|
| E2E scenarios | N | N | N | N | N |
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

- **LLD is the source of truth.** Do not invent test scenarios not traceable to an LLD section. If the LLD is missing a scenario, flag it as a coverage gap — don't fill it in.
- **Pre-mode is always available.** Even without a running app, contract validation, invariant checks, and coverage audit provide value. Don't skip QA just because the app isn't running.
- **Failures are findings, not errors in the QA process.** A failed E2E test means the app has a bug — report it, don't fix it  (unless the user asks).
- **Keep the report actionable.** Each gap or failure must have a clear next step: fix the app, update the LLD, create an issue, or accept the risk.
- **Coverage manifest is authoritative for cross-story audit.** If it's missing, flag it — the `/lld` skill should have created it.
