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

- **23 skills** — `/edf:feature`, `/edf:feature-core`, `/edf:diag`, `/edf:architect`, `/edf:kickoff`, `/edf:create-adr`, `/edf:create-plan`, `/edf:lld`, `/edf:pr-review-v2`, `/edf:retro`, `/edf:baseline`, `/edf:drift-scan`, `/edf:backlog`, `/edf:discovery`, `/edf:requirements`, `/edf:feature-end`, `/edf:feature-team`, `/edf:lld-sync`, `/edf:bug`, `/edf:create-mermaid-diagram`, `/edf:frontend-architect`, `/edf:feature-cont`
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

Projects should provide `kb/architecture.md`, `kb/file-map.md`, and `kb/conventions.md` so EDF agents understand project-specific paths and boundaries. Templates in `starters/kb/`.

## Update

```
/plugin marketplace update mironyx
/plugin install edf@mironyx
/reload-plugins
```

## License

MIT
