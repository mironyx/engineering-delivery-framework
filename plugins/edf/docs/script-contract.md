# Script Contract

This plugin ships two kinds of scripts:

| Kind | Location | Runtime | Examples |
|---|---|---|---|
| **Plugin scripts** | `${CLAUDE_PLUGIN_ROOT}/bin/` | Claude Code | `gh-create-issue.sh`, `tag-session.py`, `query-feature-cost.py`, `create-feature-pr.sh` |
| **Project scripts** | `${CLAUDE_PLUGIN_ROOT}/starters/scripts/` | Claude Code, CI | `run-tests.sh`, `run-lint.sh` |

Plugin scripts are invoked via `${CLAUDE_PLUGIN_ROOT}/bin/<name>` — prefix `.sh` scripts with `bash` (e.g., `bash ${CLAUDE_PLUGIN_ROOT}/bin/gh-create-issue.sh`) to avoid execute-bit issues in plugin caches. Python scripts are invoked through `run-python.sh`. Project scripts follow the same convention: prefix with `bash` and use `${CLAUDE_PLUGIN_ROOT}` (e.g., `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh ts ...`). `${CLAUDE_PLUGIN_ROOT}` is resolved by Claude Code in skill markdown — it is never expected to be available as a shell variable.

## Project scripts

Each consuming project references the universal wrapper scripts via `${CLAUDE_PLUGIN_ROOT}/starters/scripts/` — skills resolve this at invocation time. No `.env` variable is needed; the skills construct the path directly:

```bash
# Skills invoke scripts with bash prefix + CLAUDE_PLUGIN_ROOT:
bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh ts tests/foo.test.ts
```

### Language parameter

All project scripts accept a language code as the first argument:

- `ts` — TypeScript/JavaScript
- `p` — Python
- `all` — run both languages sequentially (summed exit codes)

```bash
# Examples
bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh ts tests/foo.test.ts
bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-typecheck.sh p
bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-lint.sh all
```

Skills infer `<ts|p>` from the file extensions they're working with: `.ts/.tsx` → `ts`, `.py` → `p`.

### Required scripts

| Script | Purpose | Args | Exit codes |
|---|---|---|---|
| `run-tests.sh` | Run unit tests with compact output | `<ts\|p\|all>` [test-file] | 0 = pass |
| `run-typecheck.sh` | Type check | `<ts\|p\|all>` | 0 = pass |
| `run-lint.sh` | Lint | `<ts\|p\|all>` | 0 = pass |
| `run-build.sh` | Build (exec `true` if N/A) | `<ts\|p\|all>` | 0 = pass |
| `run-e2e.sh` | E2E (optional, skill skips if absent) | `<ts\|p\|all>` | 0 = pass |

`run-markdown-lint.sh` and `run-format-check.sh` are optional CI-only scripts — not invoked by any skill. Starters include them in CI workflow templates (`starters/.github/workflows/`); projects that want them in CI can keep them.

Convention: stdout/stderr captured by the skill; non-zero exit always means fail.

## Test output summarization

`run-tests.sh` must produce **compact output** — one line on pass, the failures on fail. EDF ships summarizers in `bin/` that filter raw test runner output:

- `parse-vitest-output.py` — parses vitest output from stdin
- `parse-pytest-output.py` — parses pytest output from stdin

The universal wrappers dispatch to language-specific scripts in `starters/scripts/typescript/` and `starters/scripts/python/`. Those leaf scripts derive the plugin root from their own location. `CLAUDE_PLUGIN_ROOT` is only resolved by Claude Code in hooks.json and skill markdown — it is not exported into the Bash environment, so scripts must resolve it themselves:

```bash
#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

<test-runner> "$@" > "$tmpfile" 2>&1
test_exit=$?

"${PLUGIN_ROOT}/hooks/run-python.sh" "${PLUGIN_ROOT}/bin/<summarizer>.py" < "$tmpfile"
exit $test_exit
```

## Path conventions (stay in CLAUDE.md)

These are inputs the skill constructs, not commands it runs:

- Test file convention (e.g. `tests/<area>/<unit>.test.ts` vs `tests/<area>/test_<unit>.py`)
- Source directory (`src/` vs `src/recall/`)
- Eval test path convention
