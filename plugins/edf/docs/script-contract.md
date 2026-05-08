# Script Contract

Skills never invoke language-specific commands directly. Instead they call a fixed set of shell scripts the project provides. The project substitutes the real command inside the script.

## Required scripts

Each consuming project must provide these scripts at `scripts/`:

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

Starters for TypeScript and Python are in `starters/scripts/`.

## Path conventions (stay in CLAUDE.md)

These are inputs the skill constructs, not commands it runs:

- Test file convention (e.g. `tests/<area>/<unit>.test.ts` vs `tests/<area>/test_<unit>.py`)
- Source directory (`src/` vs `src/recall/`)
- Eval test path convention
