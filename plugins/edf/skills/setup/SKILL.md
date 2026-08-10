---
name: setup
description: Bootstrap an existing project with EDF conventions. Detects project language and existing artefacts, scaffolds kb/ and CLAUDE.md, configures .env/.gitignore, and verifies the result. Run after installing the EDF plugin to configure project-level files.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, TodoWrite
---

# Setup — Bootstrap EDF into a Project

Configures a project to work with the EDF plugin. Detects what's already in
place, scaffolds project-level files (CLAUDE.md, kb/, .env, .gitignore,
.mcp.json, docs/adr/), and verifies the result. Run after installing the
plugin to set up project conventions.

**Usage:** `/edf:setup`

**Idempotent.** Safe to re-run — existing files are never overwritten without
confirmation.

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update
it when changing the phase order, scaffold steps, or verification checks.

## Process

Use `TodoWrite` to track progress through the phases.

---

### Phase 1: Detect

Survey the project to understand what exists and what's missing.

Run ALL of the following in parallel:

1. Read `CLAUDE.md` (root). Note which EDF-required sections are present and
   which are missing. The required sections are: Verification Commands, Path
   Conventions, Engineering Process, Coding Principles, Knowledge Base (kb/),
   Key Directories.

2. Detect project language. Check for, in order:
   - `package.json` → **TypeScript/JavaScript**
   - `pyproject.toml` or `setup.py` or `requirements.txt` → **Python**
   - If neither found, ask the user.

3. List what exists and doesn't:
   - `kb/` directory and which files are present (`file-map.md`, `conventions.md`,
     `architecture.md`, `anti-patterns.md`)
   - `kernel.md` or similar architecture-doc file
   - `.env` file — does it have `EDF_SCRIPTS`, `EDF_FEATURE_PREFIX`, and
     `EDF_FEATURE_PROM_DIR`?
   - `.github/project.env` — present or not
   - `.mcp.json` — present or not
   - `.gitignore` — does it cover `.claude/`, `.diagnostics/`?
   - `docs/adr/` directory

Present a summary table:

```
## Setup plan for <project-name>

**Language:** TypeScript/JavaScript | Python
**Existing CLAUDE.md:** yes (sections present: X, Y; missing: Z) | no

### What will be created
| Artefact | Status |
|----------|--------|
| CLAUDE.md | merge needed (3 sections to add) |
| kb/ | 4 files to populate |
| .env | add EDF_SCRIPTS, EDF_FEATURE_PREFIX, EDF_FEATURE_PROM_DIR |
| .gitignore | add .diagnostics/ |
| docs/adr/ | create directory |
| .mcp.json | add Playwright server config |
```

**Wait for user confirmation before proceeding.**

---

### Phase 2: Scaffold

Scaffold every artefact EDF needs — create new files where absent, merge into
existing ones where already present. Each sub-step is independent and proceeds
regardless of earlier sub-step outcomes.

#### 2a. CLAUDE.md

**If no CLAUDE.md exists:**

Copy the template from `${CLAUDE_PLUGIN_ROOT}/starters/CLAUDE.md.template` to
`CLAUDE.md`. Then customise:

1. **Tech stack** — fill in from Phase 1 detection.
2. **Verification Commands** — if a `package.json` exists, read its `scripts`
   and map `test`, `typecheck`/`type-check`, `lint`, `build` to the table.
   If `pyproject.toml`, read `[tool.pytest]` and similar.
3. **Path Conventions** — set the test file convention based on language:
   - TypeScript: `tests/<area>/<unit>.test.ts`
   - Python: `tests/<area>/test_<unit>.py`
   Set source directory and eval test path.
4. **Key Directories** — fill in from the project's actual structure.

**If CLAUDE.md already exists:**

Do NOT overwrite. Instead, read it and check for each required section:

| Section | Check |
|---------|-------|
| Verification Commands | Table with 5 run script references |
| Path Conventions | Test file convention, source directory, eval test path |
| Engineering Process | Pipeline reference |
| Coding Principles | HTTP mocking convention, test runner, typechecker |
| Knowledge Base (kb/) | Table with 4 kb/ file references |
| Key Directories | Project-specific directory layout |

For each missing section, append it to the end of CLAUDE.md with a comment
noting it was added by `/edf:setup`. Do not modify existing sections.

Present the proposed additions and **wait for user confirmation** before writing.

#### 2b. Knowledge base (kb/)

The `kb/` directory contains 4 files that map project-specific concepts to
paths and patterns. Copy starter templates and help the user fill them in.

```bash
mkdir -p kb
```

For each file, if it does not already exist, copy from the starter:

```bash
cp ${CLAUDE_PLUGIN_ROOT}/starters/kb/file-map.md kb/file-map.md
cp ${CLAUDE_PLUGIN_ROOT}/starters/kb/conventions.md kb/conventions.md
cp ${CLAUDE_PLUGIN_ROOT}/starters/kb/architecture.md kb/architecture.md
cp ${CLAUDE_PLUGIN_ROOT}/starters/kb/anti-patterns.md kb/anti-patterns.md
```

If a file already exists, skip it — do not overwrite.

Then, for each file that was freshly copied, analyse the project and propose
values for the placeholders:

**`kb/file-map.md`** — fill concept → path mappings:
- `engine-dir` — look for `src/lib/engine/`, `src/engine/`, `src/core/`,
  `lib/engine/`, or equivalent
- `api-dir` — look for `src/app/api/`, `src/routes/`, `src/api/`, or equivalent
- `types-dir` — look for `src/types/`, `src/@types/`, `types/`, or equivalent
- `test-dir` — `tests/` or `src/__tests__/`
- `composition-root` — look for `src/lib/api/context.ts`, `src/app/context.ts`,
  `src/db.ts`, `src/database.ts`, or equivalent
- `db-types` — look for `src/types/database.types.ts`, `src/types/db.ts`, or
  equivalent
- `schema-dir` — `supabase/schemas/`, `db/schema/`, or leave blank
- `migration-dir` — `supabase/migrations/`, `db/migrate/`, `db/migrations/`,
  or leave blank

Propose values for each. **Wait for user confirmation** before writing.

**`kb/conventions.md`** — fill concept → pattern:
- `test-suffix` — derived from language: `.test.ts`, `_test.py`, etc.
- `test-path` — derived from project structure
- `eval-test-path` — `tests/eval/` or `tests/evaluation/`
- `e2e-dir` — `tests/e2e/` or blank
- `fixture-dir` — `tests/fixtures/` or blank
- `helper-dir` — `tests/helpers/` or blank
- Schema section — leave as-is unless the project uses declarative schemas

Propose values. **Wait for user confirmation** before writing.

**`kb/architecture.md` and `kb/anti-patterns.md`:**

If the project has a `kernel.md` (or `ARCHITECTURE.md`, `CONVENTIONS.md`, or
similar file detected in Phase 1), do NOT copy blank templates. Instead, create
thin pointer files:

`kb/architecture.md`:
```markdown
# Architecture

This project's architecture rules are documented in [`kernel.md`](../kernel.md).
See that file for boundary rules, API composition patterns, and DB contract.
```

`kb/anti-patterns.md`:
```markdown
# Anti-Patterns

This project's anti-pattern checklist is documented in [`kernel.md`](../kernel.md).
See that file for framework-specific patterns, language conventions, and
helper-reuse rules.
```

Then in the CLAUDE.md Knowledge Base table, note that `kernel.md` is the
authoritative source.

If no `kernel.md` or equivalent exists, these files are project-specific and
cannot be auto-populated. Leave the template placeholders in place and tell
the user:

> `kb/architecture.md` and `kb/anti-patterns.md` contain project-specific rules.
> Start with the boundary rule (which directories must not import from which
> frameworks) and the API composition pattern. Fill in anti-patterns as the
> team discovers them in code review.

#### 2c. Environment configuration

**`.env` file:**

Read `.env` if it exists. Check for `EDF_SCRIPTS`, `EDF_FEATURE_PREFIX`,
and `EDF_FEATURE_PROM_DIR`.

If `EDF_SCRIPTS` is missing, append with the default:

```
EDF_SCRIPTS=${CLAUDE_PLUGIN_ROOT}/starters/scripts
```

If `EDF_FEATURE_PREFIX` is missing, derive a default from the repo name
(uppercase initials: `engineering-delivery-framework` → `EDF`). Append:

```
EDF_FEATURE_PREFIX=<derived-prefix>
```

If `EDF_FEATURE_PROM_DIR` is missing, ask the user where node_exporter reads
its textfile collector directory from. Do **not** assume it is local to this
repo — node_exporter typically reads its textfiles from a different repo or a
host path.

> Where does node_exporter read its textfile collector directory from?
> `EDF_FEATURE_PROM_DIR` must match the directory your node_exporter runs with
> `--collector.textfile.directory` pointing at — usually configured in a separate
> monitoring/infra repo, not here. Paste the path, or accept the repo-local
> default (`monitoring/textfile_collector`) if node_exporter isn't set up yet.

If the user provides a path, write it verbatim (use an absolute path when the
directory is outside this repo):

```
EDF_FEATURE_PROM_DIR=<user-provided-path>
```

Otherwise append the default:

```
EDF_FEATURE_PROM_DIR=monitoring/textfile_collector
```

Explain what this is after setting it (or if it's already set, still mention it):

> **What this is for:** EDF tags each session with a feature ID and records
> session↔feature mappings in a Prometheus textfile in `EDF_FEATURE_PROM_DIR/`.
> The cost tracking scripts (`query-feature-cost.py`) then read cumulative cost
> and token usage per feature from Prometheus. The session log's cost checkpoint
> table depends on this — without it, every row shows "unavailable".
>
> To enable cost tracking, you need:
> 1. node_exporter running with `--collector.textfile.directory` pointing at
>    `EDF_FEATURE_PROM_DIR` (usually configured in a separate monitoring/infra
>    repo or on the host that runs node_exporter — not in this repo).
> 2. A Prometheus instance scraping node_exporter.
> 3. If the directory is inside this repo, keep it out of version control via
>    `.gitignore` (handled below).
>
> Cost is **not required** for EDF to function — all rows gracefully degrade to
> "unavailable" when Prometheus is unreachable. But without it, you lose per-feature
> cost observability.

If `.env` does not exist, create it with all three variables. If all three
are already present, skip.

**`.gitignore`:**

Read `.gitignore` if it exists. Check for these patterns:

```
.claude/
.claude-plugin/cache/
.diagnostics/
```

Add any that are missing. Append a comment block:

```
# EDF plugin
.claude/
.claude-plugin/cache/
.diagnostics/
```

If `.gitignore` does not exist, create a minimal one.

**`.github/project.env`:**

Check if `.github/project.env` exists. If not, tell the user:

> EDF board-aware skills (`/feature-team`, `/backlog`, `/retro`) need a
> GitHub project board configured in `.github/project.env`. To set this up:
> 1. Create the project board in GitHub
> 2. Run `gh project field-list <number> --owner <owner>`
> 3. Fill in `.github/project.env` with the field and option IDs
>
> Skipping for now — board skills will report a configuration error until
> this is set up.

Do not create an empty `.github/project.env`.

#### 2d. docs/adr/ directory

Create if missing:

```bash
mkdir -p docs/adr
```

If `docs/adr/README.md` does not exist, create one:

```markdown
# Architecture Decision Records

This directory contains architecture decisions for this project.
Numbering is sequential (0001, 0002, …). Create new ADRs with `/create-adr`.

Framework ADRs (process decisions inherited from EDF) live in the plugin
itself and are not copied here.
```

#### 2e. MCP Configuration (`.mcp.json`)

EDF's QA skill requires Playwright MCP for browser automation. The plugin
ships a starter `.mcp.json` that configures the Playwright MCP server.

Check whether `.mcp.json` exists:

**If it does not exist**, copy from starters:

```bash
cp ${CLAUDE_PLUGIN_ROOT}/starters/.mcp.json .mcp.json
```

**If it already exists**, read it and check for a `playwright` key. If the
file has no `playwright` entry, merge one in — add the `playwright` key
alongside any existing server entries. If a `playwright` key already exists,
leave the file untouched.

After scaffolding, tell the user:

> `.mcp.json` configures the Playwright MCP server used by the QA skill and
> agents. On macOS and Windows this works out of the box (Chrome is already
> installed). On Linux/WSL you may need to add `--executable-path` to point
> at the Playwright-bundled Chromium.

#### 2f. CI workflows (optional)

Ask the user:

> EDF provides CI workflow starters for TypeScript and Python. Copy one to
> `.github/workflows/`?

If the user says yes and the language is TypeScript or Python:

```bash
mkdir -p .github/workflows
cp ${CLAUDE_PLUGIN_ROOT}/starters/.github/workflows/ci-<typescript|python>.yml .github/workflows/
```

---

### Phase 3: Verify

Run verification checks. Each check passes or fails — report all results.

1. **Scripts reachable:**
   ```bash
   for script in run-tests.sh run-typecheck.sh run-lint.sh run-build.sh run-e2e.sh run-audit.sh run-format-check.sh run-markdown-lint.sh; do
     if [ -f "${CLAUDE_PLUGIN_ROOT}/starters/scripts/$script" ]; then
       echo "  OK ${CLAUDE_PLUGIN_ROOT}/starters/scripts/$script"
     else
       echo "  MISSING ${CLAUDE_PLUGIN_ROOT}/starters/scripts/$script"
     fi
   done
   ```

2. **kb files present:**
   ```bash
   for file in file-map.md conventions.md architecture.md anti-patterns.md; do
     if [ -f "kb/$file" ]; then
       echo "  OK kb/$file"
     else
       echo "  MISSING kb/$file"
     fi
   done
   ```

3. **CLAUDE.md sections present.** Read CLAUDE.md and verify each required
   section exists. Report which are present and which are missing.

4. **.env has required variables:**
   ```bash
   grep -q "EDF_SCRIPTS" .env && echo "  OK EDF_SCRIPTS" || echo "  MISSING EDF_SCRIPTS"
   grep -q "EDF_FEATURE_PREFIX" .env && echo "  OK EDF_FEATURE_PREFIX" || echo "  MISSING EDF_FEATURE_PREFIX"
   grep -q "EDF_FEATURE_PROM_DIR" .env && echo "  OK EDF_FEATURE_PROM_DIR" || echo "  MISSING EDF_FEATURE_PROM_DIR"
   ```

5. **.gitignore covers EDF patterns:**
   ```bash
   grep -q ".claude" .gitignore && echo "  OK .claude/" || echo "  MISSING .claude/"
   grep -q ".diagnostics" .gitignore && echo "  OK .diagnostics/" || echo "  MISSING .diagnostics/"
   ```

6. **`.mcp.json` present with Playwright server:**
   ```bash
   if [ -f ".mcp.json" ]; then
     grep -q '"playwright"' .mcp.json && echo "  OK .mcp.json (playwright server configured)" || echo "  MISSING playwright server in .mcp.json"
   else
     echo "  MISSING .mcp.json"
   fi
   ```

Report as a checklist. If any checks fail, tell the user what to fix.

---

### Phase 4: Report

Summarise everything that was done:

```
## EDF setup complete

### Created / modified
- CLAUDE.md — added 4 sections
- kb/file-map.md — populated 6 concepts
- kb/conventions.md — populated 5 concepts
- kb/architecture.md — template (needs project-specific rules)
- kb/anti-patterns.md — template (needs project-specific patterns)
- .env — added EDF_SCRIPTS, EDF_FEATURE_PREFIX, EDF_FEATURE_PROM_DIR
- .mcp.json — Playwright MCP server config for QA
- .gitignore — added .diagnostics/, .claude/
- docs/adr/ — created directory

### Verification
- 7/7 EDF scripts reachable
- 4/4 kb files present
- 6/6 CLAUDE.md sections present
- 3/3 .env variables set
- 2/2 .gitignore patterns present
- .mcp.json present with playwright server

### What to know
1. **kb files are living documents.** Update `kb/architecture.md` with
   architecture rules as soon as possible — `/pr-review` reads them on every
   review. Add entries to `kb/anti-patterns.md` as the team discovers
   recurring issues.
2. **Scripts referenced via `${CLAUDE_PLUGIN_ROOT}`.** The CLAUDE.md
   template uses `${CLAUDE_PLUGIN_ROOT}/starters/scripts/` directly
   (Claude Code resolves this in markdown). The `.env` also sets
   `EDF_SCRIPTS` for scripts that prefer the shorter alias.
   Example: `bash ${CLAUDE_PLUGIN_ROOT}/starters/scripts/run-tests.sh ts tests/foo.test.ts`.
3. **`.github/project.env` is not yet configured.** Board-aware skills will
   fail until it's set up.

### Suggested next steps
1. Add and commit the new files to version control.
2. Fill in `kb/architecture.md` — start with the boundary rule.
3. Fill in `kb/anti-patterns.md` — start with framework anti-patterns.
4. Verify the scripts work: `${EDF_SCRIPTS}/run-tests.sh <ts|p> <test-file>`.
5. Set up `.github/project.env` if using GitHub Projects.
```

---

## Guidelines

- **Idempotent.** Existing files are skipped. Backups are never needed — the
  plugin's files are authoritative and this skill only creates what's missing.
- **Detect, don't assume.** Read the actual project state. Don't guess the
  language, don't assume directories exist.
- **User gates at key decisions.** Stop and confirm before: (a) the setup plan,
  (b) CLAUDE.md merges, (c) kb value proposals.
- **British English** in all output.
- **No Co-Authored-By trailers** in commit messages.
- **No commits during setup.** The user commits as part of their normal
  workflow.
- **The project is not broken if something fails.** Each phase is independent.
  If kb population fails, .env is still configured. If .env setup
  fails, CLAUDE.md is still merged. Report failures clearly and let the user
  fix them.
- **Don't invent project details.** When proposing kb values, base them on
  what you actually find in the project. If you can't find a concept, leave
  the placeholder and tell the user.
- **Respect existing content.** When merging CLAUDE.md, preserve every
  existing section. Only append missing sections at the end.
