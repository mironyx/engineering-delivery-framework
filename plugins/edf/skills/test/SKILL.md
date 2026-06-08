---
name: test
description: Run tests, typecheck, lint, build, and E2E checks via wrapper scripts. Delegates to the edf:test-runner agent for token-efficient output. Use for any verification run — single file, full suite, or specific check.
allowed-tools: Bash, Agent
---

# Test — Verification Runner

Runs verification commands through the project's wrapper scripts, delegating execution
to `edf:test-runner` for token-efficient output. Owns the resolution logic (language
inference, script selection, file paths) so callers don't duplicate it.

## Arguments

`$ARGUMENTS` determines the mode:

- **File path** (e.g., `tests/foo.test.ts`) — run tests on that file only. Language auto-inferred from extension.
- **`all [ts|p|all]`** — run full test suite. Language defaults to `all`.
- **`full [ts|p|all]`** — tests + typecheck + lint. Used by `feature-core` Step 5.
- **`typecheck [ts|p|all]`** — typecheck only.
- **`lint [ts|p|all]`** — lint only.
- **`build [ts|p|all]`** — build only.
- **`e2e [ts|p|all]`** — build + E2E tests.

## Instructions

### 1. Parse input

Split `$ARGUMENTS` on whitespace. The first token is the mode or file path.

**File path** — if the first token ends with `.ts`, `.tsx`, or `.py`, or contains `/` or `\`:
- Mode: `file`
- Target: the file path
- Language: infer from extension — `.ts` / `.tsx` → `ts`, `.py` → `p`

**Keyword** — if the first token is `all`, `full`, `typecheck`, `lint`, `build`, or `e2e`:
- Mode: the keyword
- Language: second token if present, otherwise `all`

### 2. Resolve command

Construct the fully-resolved command using `${CLAUDE_PLUGIN_ROOT}`:

| Mode | Command |
|------|---------|
| `file` | `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh <ts\|p> <file>` |
| `all` | `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh <ts\|p>` |
| `full` | `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh <ts\|p> && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-typecheck.sh <ts\|p> && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-lint.sh <ts\|p>` |
| `typecheck` | `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-typecheck.sh <ts\|p>` |
| `lint` | `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-lint.sh <ts\|p>` |
| `build` | `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-build.sh <ts\|p>` |
| `e2e` | `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-build.sh <ts\|p> && bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-e2e.sh <ts\|p>` |

`${CLAUDE_PLUGIN_ROOT}` is resolved by Claude Code in skill markdown — do not read it from `.env`.

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
