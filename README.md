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

## Quick start

After installing the plugin, run `/edf:setup` in your project to configure
project-level conventions:

- **CLAUDE.md** — engineering process, verification commands, coding principles
- **kb/** — file map, conventions, architecture rules, anti-patterns
- **.env** — script paths, feature prefix, Prometheus monitoring directory
- **.gitignore**, **.mcp.json**, **docs/adr/** directory

For cost tracking (session logs show cumulative usage per feature), set up
a [Prometheus](https://prometheus.io/) instance with the
[textfile collector](https://github.com/prometheus/node_exporter?tab=readme-ov-file#textfile-collector)
pointing at the directory configured in `EDF_FEATURE_PROM_DIR`.

## What's included

- **25 skills** — `/edf:feature`, `/edf:feature-core`, `/edf:feature-end`, `/edf:feature-team`, `/edf:test`, `/edf:diag`, `/edf:qa`, `/edf:pr-review`, `/edf:architect`, `/edf:refactor-architect`, `/edf:frontend-architect`, `/edf:kickoff`, `/edf:discovery`, `/edf:requirements`, `/edf:create-plan`, `/edf:lld`, `/edf:lld-sync`, `/edf:create-adr`, `/edf:create-mermaid-diagram`, `/edf:bug`, `/edf:backlog`, `/edf:baseline`, `/edf:drift-scan`, `/edf:retro`, `/edf:setup`
- **14 agents** — ci-probe, diagnostics-checker, feature-evaluator, gh-issue-manager, hld-review, lld-review, qa-contracts, qa-coverage, qa-executor, qa-explorer, requirements-design-drift, requirements-review, test-author, test-runner
- **3 hooks** — PostToolUse diagnostics + editor open, PreCompact session log
- **13 utility scripts** — GitHub project management, session tagging, cost tracking, PR creation, coverage manifest, test output summarizers (vitest, pytest)

## Project configuration

### `.env` (repo root)

Project-specific settings shared by the team. Commit this file.

| Variable | Script(s) | Purpose |
|---|---|---|
| `EDF_FEATURE_PREFIX` | `tag-session.py`, `query-feature-cost.py` | Override the auto-derived feature-id prefix (default: initials from repo name — `engineering-delivery-framework` → `EDF`). Set when the team uses a different prefix in their tracker. |
| `EDF_FEATURE_PROM_DIR` | `tag-session.py`, `query-feature-cost.py`, `extract-session-id.py` | Override the Prometheus textfile collector directory (default: `<repo-root>/monitoring/textfile_collector`). Set when node_exporter reads from a non-standard location, or point at a gitignored path (e.g. `.claude/textfile_collector`) to keep the working tree clean. |

Overrides are read in this order: OS environment → `.env` → derivation.

### `.github/project.env`

GitHub project board configuration. Used by `gh-project-status.sh` and any skill that queries the board (`/feature-team`, `/backlog`, `/retro`). Create this file with:

```
REPO=owner/name
PROJECT_NUMBER=N
PROJECT_ID=PVT_...
FIELD_ID=PVTSSF_...
STATUS_TODO=...
STATUS_BLOCKED=...
STATUS_IN_PROGRESS=...
STATUS_DONE=...
```

To set up a new repo:
1. Create the project board in GitHub
2. Run `gh project field-list <number> --owner <owner>`
3. Copy the field ID and option IDs into `.github/project.env`

Without this file, board-aware skills will fail with a configuration error.

### Model configuration

Several EDF agents pin `model: haiku` in their frontmatter (`ci-probe`, `diagnostics-checker`, `gh-issue-manager`, `test-runner`) to keep cost low on mechanical work. This relies on the calling environment having a `haiku` model available — either:

- **Anthropic API directly** — `claude-haiku-4-5` is selected automatically.
- **External routing** — set `ANTHROPIC_DEFAULT_HAIKU_MODEL` (or your routing tool's equivalent) so the `haiku` selector resolves to your chosen backend (e.g. DeepSeek, a local model).
- **No haiku available** — Claude Code falls back to the default model. EDF still works; you just pay the default-model rate on mechanical agents.

The `haiku` label is a model *name*, not an agent type. EDF's agent types are namespaced (`edf:test-runner`, `edf:ci-probe`, etc.) and do not require a "haiku" agent type to be registered.

## Project documentation conventions

EDF skills assume certain docs live in standard locations. Configure these in your project's `kb/file-map.md`:

- **Vision / north-star doc** — where the project's "why this exists" is captured (used by `/backlog`). Point `vision-doc` to a marketing article, pitch deck, product brief, or similar.
- **Anti-patterns** — `kb/anti-patterns.md` (starter in `starters/kb/`). Populate with patterns your team has learned to flag in review.
- **Architecture rules** — `kb/architecture.md` (starter in `starters/kb/`). Boundary rules, API composition, DB contract used by `/pr-review`.

## Script contract

EDF skills invoke project-specific scripts instead of hardcoded commands. Each project using EDF must provide these 5 scripts in `scripts/`:

| Script | Purpose | Exit |
|---|---|---|
| `run-tests.sh` | Unit tests; optional file path arg | 0 = pass |
| `run-typecheck.sh` | Type check | 0 = pass |
| `run-lint.sh` | Lint | 0 = pass |
| `run-build.sh` | Build (`exec true` if N/A) | 0 = pass |
| `run-e2e.sh` | E2E (optional) | 0 = pass |

Optional CI-only scripts (`run-markdown-lint.sh`, `run-format-check.sh`) are included in CI workflow starters — no skill invokes them.

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
