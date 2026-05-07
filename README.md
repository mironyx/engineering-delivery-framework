# Engineering Delivery Framework (EDF)

A Claude Code plugin that provides a structured software delivery harness — skills, agents, hooks, and scripts — for TDD-driven development, architecture design, and process automation.

## Install

### From marketplace

```
/plugin marketplace add mironyx/engineering-delivery-framework
/plugin install edf@mironyx
```

### Local development

```bash
git clone git@github.com:mironyx/engineering-delivery-framework.git
claude --plugin-dir ./engineering-delivery-framework
```

## What's included

- **23 skills** — `/edf:feature`, `/edf:feature-core`, `/edf:diag`, `/edf:architect`, `/edf:kickoff`, `/edf:create-adr`, `/edf:create-plan`, `/edf:lld`, `/edf:pr-review`, `/edf:retro`, `/edf:baseline`, `/edf:drift-scan`, `/edf:backlog`, `/edf:discovery`, `/edf:requirements`, `/edf:feature-end`, `/edf:feature-team`, `/edf:lld-sync`, `/edf:bug`, `/edf:create-mermaid-diagram`, `/edf:frontend-architect`, `/edf:feature-cont`
- **4 agents** — ci-probe, diagnostics-checker, feature-evaluator, requirements-design-drift
- **3 hooks** — PostToolUse diagnostics + editor open, PreCompact session log
- **6 utility scripts** — GitHub project management, session tagging, cost tracking

## Script contract

EDF skills invoke project-specific scripts instead of hardcoded commands. Each project using EDF must provide these 7 scripts in `scripts/`:

| Script | Purpose | Exit |
|---|---|---|
| `run-tests.sh` | Unit tests; optional file path arg | 0 = pass |
| `run-typecheck.sh` | Type check | 0 = pass |
| `run-lint.sh` | Lint | 0 = pass |
| `run-build.sh` | Build (`exec true` if N/A) | 0 = pass |
| `run-markdown-lint.sh` | Markdown lint | 0 = pass |
| `run-format-check.sh` | Format check (optional) | 0 = pass |
| `run-e2e.sh` | E2E (optional) | 0 = pass |

Starter scripts for TypeScript and Python projects are in `starters/scripts/`.

## Knowledge base (kb/)

EDF skills are project-agnostic — they reference project-specific paths and conventions through named concepts, not literal paths. Each project using EDF provides four kb files that fill in those concepts:

- `kb/file-map.md` — concept name → path (e.g. `engine-dir`, `api-dir`, `schema-dir`).
- `kb/conventions.md` — concept name → pattern (e.g. `test-path`, `migration-generate-cmd`).
- `kb/architecture.md` — short paragraphs of project-specific architecture rules (boundary rules, API composition, DB contract). Read by `/pr-review` as `{{ARCHITECTURE_RULES}}`.
- `kb/anti-patterns.md` — the project's anti-pattern checklist (framework-specific patterns, language conventions, kernel-reuse rules). Read by `/pr-review` as `{{ANTI_PATTERNS}}`.

Templates with the full concept list are in `starters/kb/`. Copy them to your project's `kb/` and replace each `<!-- e.g. ... -->` placeholder with your project's actual path or pattern.

### Concept-driven references

Skill text uses `<concept-name>` placeholders. At runtime the agent resolves each concept from your project's kb. For example:

> If `git diff --name-only HEAD -- "<schema-dir>/"` is non-empty …

The skill stays project-agnostic; the agent looks up `schema-dir` in your `kb/file-map.md` to know whether it means `supabase/schemas/`, `db/schema.rb`, etc.

### Optional concepts

Some concepts only apply to specific workflows:

- `schema-is-declarative` — set to `true` for projects with a declarative schema source (`schema-dir`) and generated migrations (e.g. Supabase). Leave blank if you write migrations directly.
- `migration-generate-cmd` / `db-reset-cmd` / `migration-verify-cmd` — required when `schema-is-declarative=true`; ignored otherwise.
- `migration-dir` — set if the project uses migrations at all (declarative or hand-authored). Some skills (e.g. the architect schema-foundations rule) gate on this.

Skills that reference an optional concept skip their behaviour cleanly when the concept is blank — no errors, no false guards.

## Update

```
/plugin marketplace update mironyx
/plugin install edf@mironyx
/reload-plugins
```

## License

MIT
