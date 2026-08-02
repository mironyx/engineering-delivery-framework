# Conventions

File naming and path conventions. Referenced by EDF skills.

| Concept | Pattern |
|---|---|
| test-suffix | `test_<unit>.py` (pytest prefix convention) |
| test-path | `tests/test_<unit>.py` |
| eval-test-path | n/a |
| e2e-dir | n/a (Playwright MCP-based QA) |
| fixture-dir | n/a |
| helper-dir | n/a |

## Schema & migrations

n/a — this is a plugin monorepo, not a database-backed application.

`schema-is-declarative` is unset (no database).

| Concept | Pattern |
|---|---|
| schema-is-declarative | |
| migration-generate-cmd | n/a |
| db-reset-cmd | n/a |
| migration-verify-cmd | n/a |
