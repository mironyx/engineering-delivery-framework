---
name: test
description: Run tests, typecheck, lint, build, and E2E checks via wrapper scripts. Delegates to the edf:test-runner agent for token-efficient output. Use for any verification run — single file, full suite, or specific check.
allowed-tools: Bash, Agent
---

# Test — Verification Runner

Runs verification commands through the project's wrapper scripts, delegating execution
to `edf:test-runner` for token-efficient output. Owns the resolution logic (language
inference, script selection, file paths) so callers don't duplicate it.

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when
changing mode parsing, command resolution, or agent delegation.

## Arguments

`$ARGUMENTS` determines the mode:

- **File path** (e.g., `tests/foo.test.ts`) — run tests on that file only. Language auto-inferred from extension.
- **`all [ts|p|all]`** — run full test suite. Language defaults to `all`.
- **`full [ts|p|all]`** — tests + typecheck + lint. Used by `feature-core` Step 5.
- **`typecheck [ts|p|all]`** — typecheck only.
- **`lint [ts|p|all]`** — lint only.
- **`build [ts|p|all]`** — build only.
- **`e2e [ts|p|all]`** — build + E2E tests.
- **`audit [ts|p|all]`** — dependency security scan (npm/pnpm/yarn audit; uv audit/pip-audit). Used by `feature-core` Step 5.

## Instructions

### 1. Parse input

Split `$ARGUMENTS` on whitespace. The first token is the mode or file path.

**File path** — if the first token ends with `.ts`, `.tsx`, or `.py`, or contains `/` or `\`:
- Mode: `file`
- Target: the file path
- Language: infer from extension — `.ts` / `.tsx` → `ts`, `.py` → `p`

**Keyword** — if the first token is `all`, `full`, `typecheck`, `lint`, `build`, `e2e`, or `audit`:
- Mode: the keyword
- Language: second token if present, otherwise `all`

### 2. Resolve command

**Capture your own CWD first, and prefix it onto the command.** `edf:test-runner` never
changes directory itself (see its anti-patterns) — it runs wherever it inherits, and
sub-agent spawns do not reliably inherit the calling session's CWD. This is what caused
verification to silently run against the wrong checkout (main repo instead of a
`/feature-team` worktree). Run this before building the command:

```bash
CWD=$(pwd)
```

Construct the fully-resolved command using `${CLAUDE_PLUGIN_ROOT}`, with `cd "$CWD" &&`
prefixed onto every variant below:

| Mode | Command |
|------|---------|
| `file` | `cd "$CWD" && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh <ts\|p> <file>` |
| `all` | `cd "$CWD" && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh <ts\|p>` |
| `full` | `cd "$CWD" && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh <ts\|p> && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-typecheck.sh <ts\|p> && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-lint.sh <ts\|p>` |
| `typecheck` | `cd "$CWD" && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-typecheck.sh <ts\|p>` |
| `lint` | `cd "$CWD" && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-lint.sh <ts\|p>` |
| `build` | `cd "$CWD" && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-build.sh <ts\|p>` |
| `e2e` | `cd "$CWD" && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-build.sh <ts\|p> && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-e2e.sh <ts\|p>` |
| `audit` | `cd "$CWD" && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-audit.sh <ts\|p>` |

`${CLAUDE_PLUGIN_ROOT}` is resolved by Claude Code in skill markdown — do not read it from `.env`.
`$CWD` is the literal path captured above — substitute it in, don't pass the variable name.

### 3. Execute

Launch the `edf:test-runner` agent with the resolved command:

```
Launch Agent: edf:test-runner
Input: command="<resolved command>"
```

### 4. Report

- **PASS** — report pass and continue.
- **FAIL** — report the failure (test-runner surfaces the first 10 lines). Do not retry — the caller decides whether to fix and re-run.

## Guidelines

- **One command per invocation.** Do not chain multiple modes.
- **Language inference is for convenience.** Callers that know the project language should pass `<ts|p>` explicitly.
- **Never modify the resolved command.** Pass it verbatim to `edf:test-runner`.
