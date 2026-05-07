# Conventions

File naming and path conventions. Referenced by EDF skills.

| Concept | Pattern |
|---|---|
| test-suffix | <!-- e.g. `.test.ts` --> |
| test-path | <!-- e.g. `tests/<area>/<unit>.test.ts` --> |
| eval-test-path | <!-- e.g. `tests/evaluation/<slug>.eval.test.ts` --> |
| e2e-dir | <!-- e.g. `tests/e2e/` --> |
| fixture-dir | <!-- e.g. `tests/fixtures/` --> |
| helper-dir | <!-- e.g. `tests/helpers/` --> |

## Schema & migrations

`schema-is-declarative` distinguishes two workflows:

- `true` — `schema-dir` is the source of truth and migrations are generated from it. All four concepts below are required.
- blank/false — migrations are hand-authored directly in `migration-dir`. Only `migration-dir` (in file-map) is required; the commands below are not used.

| Concept | Pattern |
|---|---|
| schema-is-declarative | <!-- e.g. `true` --> |
| migration-generate-cmd | <!-- e.g. `npx supabase db diff -f <name>` (declarative only) --> |
| db-reset-cmd | <!-- e.g. `npx supabase db reset` --> |
| migration-verify-cmd | <!-- e.g. `npx supabase db reset && npx supabase db diff` — must produce empty output (declarative only) --> |
