# CLAUDE.md

This is the Engineering Delivery Framework (EDF) — a Claude Code plugin that provides a
structured software delivery harness. The repo is the plugin source itself, not a project
that uses EDF.

## Plugin structure

```
plugins/edf/
  skills/       — 22 skill .md files (feature-core, diag, lld, pr-review, etc.)
  agents/       — agent .md files (test-author, feature-evaluator, ci-probe, etc.)
  hooks/        — hook scripts (PostToolUse, PreCompact)
  bin/          — utility scripts (tag-session, query-feature-cost, create-feature-pr, etc.)
  starters/     — starter templates for projects adopting EDF (scripts/, kb/)
  .claude-plugin/plugin.json  — plugin manifest (name, version, author)
.claude-plugin/marketplace.json — marketplace entry (must stay in sync with plugin.json)
```

## Version bump convention

**Every change to skills, agents, or hooks must bump the version** in two files:

1. `plugins/edf/.claude-plugin/plugin.json` — `"version"` field
2. `.claude-plugin/marketplace.json` — `"version"` field in the `plugins` array entry

These two versions must stay in sync. Bump the patch version (0.10.N) for fixes and
behavioural changes to skills/agents/hooks. The README's skill/agent counts may need
updating when adding or removing them.

## Skill files

Skill files under `plugins/edf/skills/` are markdown with YAML frontmatter. Key conventions:

- Skills reference project-specific paths through **concepts** (e.g. `<schema-dir>`,
  `<engine-dir>`) that resolve from the host project's `kb/file-map.md` and
  `kb/conventions.md`. Never hardcode paths.
- Skills invoke scripts with fully-resolved `${CLAUDE_PLUGIN_ROOT}` paths — the `bash`
  prefix avoids execute-bit issues.
- Skill steps are sequential and numbered. When changing step order or branching logic,
  update the companion `flowchart.md` file in the same directory.
- `/feature-core` is the central implementation pipeline. Its Step 3c classification
  (Light/Standard/Heavy) gates cost tracking — misclassifying as Light permanently
  loses cost checkpoint data (it cannot be backfilled).

## Agent files

Agent .md files under `plugins/edf/agents/` use frontmatter with `model` pins:

- Mechanical agents (`ci-probe`, `diagnostics-checker`, `gh-issue-manager`, `test-runner`)
  pin `model: haiku` to keep cost low.
- The `haiku` label resolves via the calling environment — it is a model name, not an
  agent type. No `haiku` agent type needs to be registered.

## Tests

Tests for the plugin itself live under `tests/`. These are integration tests for the
scripts and hooks.
