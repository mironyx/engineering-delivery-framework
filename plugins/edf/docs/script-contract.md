# Script Contract

This plugin ships two kinds of scripts:

| Kind | Location | Runtime | Examples |
|---|---|---|---|
| **Plugin scripts** | `${CLAUDE_PLUGIN_ROOT}/bin/` | Claude Code | `gh-create-issue.sh`, `tag-session.py`, `query-feature-cost.py` |
| **Project scripts** | `${EDF_SCRIPTS}/` | Claude Code, CI | `run-tests.sh`, `run-lint.sh`, `create-feature-pr.sh` |

Plugin scripts are invoked directly via `${CLAUDE_PLUGIN_ROOT}/bin/<name>` (or through `run-python.sh` for Python scripts). Project scripts are invoked via `${EDF_SCRIPTS}/<name>`.

## Project scripts

Each consuming project sets `EDF_SCRIPTS` in its `.env` to point at the project's scripts directory. Starters for TypeScript and Python are provided at `starters/scripts/{typescript,python}/`; point `EDF_SCRIPTS` to the appropriate one:

```bash
# .env (TypeScript project)
EDF_SCRIPTS=${CLAUDE_PLUGIN_ROOT}/starters/scripts/typescript
```

```bash
# .env (Python project)
EDF_SCRIPTS=${CLAUDE_PLUGIN_ROOT}/starters/scripts/python
```

### Required scripts

| Script | Purpose | Args | Exit codes |
|---|---|---|---|
| `run-tests.sh` | Run unit tests with compact output | optional file path | 0 = pass |
| `run-typecheck.sh` | Type check | none | 0 = pass |
| `run-lint.sh` | Lint | none | 0 = pass |
| `run-build.sh` | Build (exec `true` if N/A) | none | 0 = pass |
| `run-markdown-lint.sh` | Markdown lint | none | 0 = pass |
| `run-format-check.sh` | Format check (optional) | none | 0 = pass |
| `run-e2e.sh` | E2E (optional, skill skips if absent) | none | 0 = pass |

Convention: stdout/stderr captured by the skill; non-zero exit always means fail.

## Test output summarization

`run-tests.sh` must produce **compact output** — one line on pass, the failures on fail. EDF ships summarizers in `bin/` that filter raw test runner output:

- `parse-vitest-output.py` — parses vitest output from stdin
- `parse-pytest-output.py` — parses pytest output from stdin

Call them from the project's `run-tests.sh` via `${CLAUDE_PLUGIN_ROOT}`:

```bash
#!/usr/bin/env bash
set -uo pipefail
tmpfile=$(mktemp)
trap 'rm -f "$tmpfile"' EXIT

<test-runner> "$@" > "$tmpfile" 2>&1
test_exit=$?

"${CLAUDE_PLUGIN_ROOT}/hooks/run-python.sh" "${CLAUDE_PLUGIN_ROOT}/bin/<summarizer>.py" < "$tmpfile"
exit $test_exit
```

## Path conventions (stay in CLAUDE.md)

These are inputs the skill constructs, not commands it runs:

- Test file convention (e.g. `tests/<area>/<unit>.test.ts` vs `tests/<area>/test_<unit>.py`)
- Source directory (`src/` vs `src/recall/`)
- Eval test path convention
