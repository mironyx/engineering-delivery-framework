# Script Contract

Skills never invoke language-specific commands directly. Instead they call a fixed set of shell scripts the project provides. The project substitutes the real command inside the script.

## Required scripts

Each consuming project must provide these scripts at `scripts/`:

| Script | Purpose | Args | Exit codes |
|---|---|---|---|
| `run-tests.sh` | Run unit tests | optional file path | 0 = pass |
| `run-typecheck.sh` | Type check | none | 0 = pass |
| `run-lint.sh` | Lint | none | 0 = pass |
| `run-build.sh` | Build (exec `true` if N/A) | none | 0 = pass |
| `run-markdown-lint.sh` | Markdown lint | none | 0 = pass |
| `run-format-check.sh` | Format check (optional) | none | 0 = pass |
| `run-e2e.sh` | E2E (optional, skill skips if absent) | none | 0 = pass |

Convention: stdout/stderr captured by the skill; non-zero exit always means fail.

## Path conventions (stay in CLAUDE.md)

These are inputs the skill constructs, not commands it runs:

- Test file convention (e.g. `tests/<area>/<unit>.test.ts` vs `tests/<area>/test_<unit>.py`)
- Source directory (`src/` vs `src/recall/`)
- Eval test path convention

## Example

FCS `scripts/run-tests.sh`:
```bash
#!/usr/bin/env bash
exec npx vitest run "$@"
```

Recall `scripts/run-tests.sh`:
```bash
#!/usr/bin/env bash
exec uv run pytest "$@"
```
