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

Agent .md files under `plugins/edf/agents/` use frontmatter with a `model` field. There are
exactly two valid values, and `tests/test_agent_schema.py` enforces the split:

- **Mechanical agents** (`ci-probe`, `diagnostics-checker`, `gh-issue-manager`,
  `qa-contracts`, `qa-coverage`, `test-runner`) pin `model: haiku` to keep cost low. They
  execute pre-assembled commands and string substitution — no judgement to preserve.
- **Every other agent** uses `model: inherit`, so its depth tracks whatever model the
  operator is running. Never pin a judgement agent to a specific alias: a hard `sonnet`
  pin caps a reviewer at Sonnet even in an Opus session, and a hard `opus` pin bills Opus
  even in a cheap one.
- The `haiku` label resolves via the calling environment — it is a model name, not an
  agent type. No `haiku` agent type needs to be registered.

**Model resolution order** (highest wins), per the Claude Code subagent docs:
`CLAUDE_CODE_SUBAGENT_MODEL` env var → the per-invocation `model` parameter on the `Agent`
call → the agent definition's frontmatter → the main conversation's model. A skill that
passes `model:` at the spawn site therefore overrides `inherit` — see the `**Model:**`
directives in `architect`, `kickoff`, `requirements`, `discovery`, `bug`,
`refactor-architect`, and `frontend-architect`, which deliberately force Opus for design
work.

## Tests

Tests for the plugin itself live under `tests/`. These are integration tests for the
scripts and hooks.

<!-- The following sections were added by /edf:setup -->

## Engineering Process

Pipeline: `idea → /discovery → /requirements → /kickoff → /architect → /feature → /feature-end → /retro`.

This repo is a plugin monorepo — the same process applies to plugin features and the VS Code extension.

## Coding Principles

- HTTP mocking: respx (HTTPX) for any HTTP interactions. Do not use manual stubs or monkey-patching.
- Test runner: pytest. Typecheck: pyright (via VS Code).

## Verification Commands

| Command | Purpose |
| --- | --- |
| `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh p tests/test_<name>.py` | Unit tests |
| `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-lint.sh p` | Lint (shellcheck + Python) |
| `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-markdown-lint.sh p` | Markdown lint |

E2E tests run via Playwright MCP in `/qa`. Typecheck is handled by pyright in the IDE.

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `plugins/edf/` | EDF plugin — skills, agents, hooks, bin, starters |
| `extensions/` | VS Code extension sources |
| `tests/` | Plugin integration tests (pytest) |
| `plugins/edf/docs/adr/` | Architecture Decision Records |
| `kb/` | Project conventions for EDF skills |

## Knowledge Base (kb/)

| File | Purpose | Read by |
|------|---------|---------|
| `kb/architecture.md` | Architecture rules, API composition patterns | `/lld`, `/pr-review`, `/lld-sync` |
| `kb/anti-patterns.md` | Plugin-specific anti-patterns | `/pr-review`, `/lld-sync` |
| `kb/conventions.md` | Test naming, path conventions | `/pr-review` |
| `kb/file-map.md` | Logical concept → path mappings | `/pr-review`, `/lld-sync` |
