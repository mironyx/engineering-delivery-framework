---
name: migrate
description: Guide a project through EDF plugin adoption. Detects project language and existing artefacts, backs up conflicts, populates kb/, scaffolds scripts, merges CLAUDE.md, bootstraps .env/.gitignore, and verifies the result. Use once when first integrating EDF into an existing project, or after a major plugin update that adds new required files.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, TodoWrite
---

# Migrate — EDF Plugin Adoption

Integrates the EDF plugin into an existing project. Detects what's already in place,
backs up anything that would be overwritten, scaffolds the files the plugin needs,
and verifies the result.

**Usage:** `/edf:migrate`

**Idempotent.** Safe to re-run — backups are timestamped, existing files are never
overwritten without confirmation.

A [flowchart.md](flowchart.md) companion file visualises this pipeline. Update it when changing the phase order, scaffold steps, or verification checks.

## Process

Use `TodoWrite` to track progress through the phases.

---

### Phase 1: Detect

Survey the project to understand what exists and what's missing.

Run ALL of the following in parallel:

1. Read `CLAUDE.md` (root). Note which EDF-required sections are present and which
   are missing. The required sections are: Verification Commands, Path Conventions,
   Engineering Process, Coding Principles, Knowledge Base (kb/), Key Directories.

2. Detect project language. Check for, in order:
   - `package.json` → **TypeScript/JavaScript**
   - `pyproject.toml` or `setup.py` or `requirements.txt` → **Python**
   - `Cargo.toml` → **Rust**
   - `go.mod` → **Go**
   - If none found, ask the user.

3. Resolve the scripts directory. Read `.env` if it exists and extract
   `EDF_SCRIPTS`. If absent, default to `scripts/`. This path — call it
   `$EDF_SCRIPTS_DIR` throughout — is where the 5 required scripts live.

4. List what exists and doesn't:
   - `kb/` directory and which files are present (`file-map.md`, `conventions.md`,
     `architecture.md`, `anti-patterns.md`)
   - `kernel.md` or similar architecture-doc file — if present, the project
     already has its rules documented; kb/ files should reference it, not
     duplicate it
   - `$EDF_SCRIPTS_DIR` — which of the 5 required scripts exist
   - `.env` file — does it have `EDF_SCRIPTS`, `EDF_FEATURE_PREFIX`, and
     `EDF_FEATURE_PROM_DIR`?
   - `.github/project.env` — present or not
   - `.gitignore` — does it cover `.claude/`, `.diagnostics/`?
   - `docs/adr/` directory
   - Existing skills (check `.claude/skills/` for name conflicts with EDF skills)
   - Existing agents (check `.claude/agents/` for name conflicts with EDF agents)
   - Existing hooks (check `.claude/settings.json` for `hooks` key)

4. List EDF skills and agents from the plugin. Read the skill directories under
   `${CLAUDE_PLUGIN_ROOT}/skills/` and agent files under
   `${CLAUDE_PLUGIN_ROOT}/agents/` to get the full list of names.

Present a summary table:

```
## Migration plan for <project-name>

**Language:** TypeScript | Python | Rust | Go
**Existing CLAUDE.md:** yes (sections present: X, Y; missing: Z) | no

### Conflicts to back up
| What | Details |
|------|---------|
| Scripts | `$EDF_SCRIPTS_DIR/run-tests.sh` overlaps with EDF contract |
| Skills | `pr-review`, `bug` conflict with EDF skill names |
| Hooks | PostToolUse hook already registered |

### What will be created
| Artefact | Status |
|----------|--------|
| CLAUDE.md | merge needed (3 sections to add) |
| kb/ | 4 files to populate — `kernel.md` detected, will reference instead of duplicating |
| scripts | 5 scripts to copy (TypeScript starter) to `$EDF_SCRIPTS_DIR` |
| .env | add EDF_FEATURE_PREFIX |
| .gitignore | add .diagnostics/ |
| docs/adr/ | create directory |
```

**Wait for user confirmation before proceeding.**

---

### Phase 2: Backup conflicts

For each conflict identified in Phase 1, back up before touching anything.

**Scripts.** If `$EDF_SCRIPTS_DIR` exists and any of the 5 required script names overlap:

```bash
mkdir -p scripts.backup.$(date +%Y%m%d-%H%M%S)
cp $EDF_SCRIPTS_DIR/<conflicting-script>.sh scripts.backup.<timestamp>/
```

Add `scripts.backup.*/` to `.gitignore`:

```
# EDF migration backups
scripts.backup.*/
```

If the backup directory already exists from a previous run, append a counter
(`scripts.backup.20260514-2153.1/`).

**Skills.** If any skill in `.claude/skills/<name>/` shares a name with an EDF
skill:

```bash
mkdir -p skills.backup.$(date +%Y%m%d-%H%M%S)
cp -r .claude/skills/<name>/ skills.backup.<timestamp>/
```

Add `skills.backup.*/` to `.gitignore`.

**Agents.** Same pattern as skills — back up to `agents.backup.<timestamp>/`.

**Hooks.** Read `.claude/settings.json` (or `.claude/settings.local.json`).
If hooks exist on `PostToolUse` or `PreCompact`, copy the entire settings file
to `settings.json.backup.<timestamp>`. Do not merge hooks automatically — the
user must decide. Explain:

> Your project has hooks on `<event>`. EDF also registers hooks on this event.
> Both can coexist — EDF hooks do not replace yours. Your settings file has
> been backed up to `settings.json.backup.<timestamp>`.

If backup directories or files are empty after copying (no actual conflicts),
remove them and note "No conflicts to back up."

---

### Phase 3: Scaffold

Scaffold every artefact the plugin needs — new files where absent, merged into
existing ones where already present. Each sub-step is independent and proceeds
regardless of earlier sub-step outcomes.

#### 3a. CLAUDE.md

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
   - Rust: `tests/<area>/<unit>.rs` or `src/<module>/tests.rs`
   - Go: `<package>/<file>_test.go`
   Set source directory and eval test path.
4. **Key Directories** — fill in from the project's actual structure.

Commit:
```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md — project-specific configuration for EDF"
```

**If CLAUDE.md already exists:**

Do NOT overwrite. Instead, read it and check for each required section:

| Section | Check |
|---------|-------|
| Verification Commands | Table with `run-tests.sh`, `run-typecheck.sh`, `run-lint.sh`, `run-build.sh`, `run-e2e.sh` |
| Path Conventions | Test file convention, source directory, eval test path |
| Engineering Process | Pipeline reference: `idea → /discovery → ... → /retro` |
| Coding Principles | HTTP mocking convention, test runner, typechecker |
| Knowledge Base (kb/) | Table with `kb/architecture.md`, `kb/anti-patterns.md`, `kb/conventions.md`, `kb/file-map.md` |
| Key Directories | Project-specific directory layout |

For each missing section, append it to the end of CLAUDE.md with a comment
noting it was added by `/edf:migrate`. Do not modify existing sections.

Present the proposed additions and **wait for user confirmation** before writing.

Commit after:
```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md — add EDF-required sections"
```

#### 3b. Knowledge base (kb/)

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

Then in the CLAUDE.md Knowledge Base table (Phase 3a), note that `kernel.md`
is the authoritative source for architecture rules and anti-patterns.

If no `kernel.md` or equivalent exists, these files are project-specific and
cannot be auto-populated. Leave the template placeholders in place and tell
the user:

> `kb/architecture.md` and `kb/anti-patterns.md` contain project-specific rules.
> Start with the boundary rule (which directories must not import from which
> frameworks) and the API composition pattern. Fill in anti-patterns as the
> team discovers them in code review — each `/pr-review` finding that becomes
> a recurring issue should become an entry in `kb/anti-patterns.md`.

Commit:
```bash
git add kb/
git commit -m "docs: kb/ — project knowledge base for EDF skills"
```

Skip committing if no kb files changed.

#### 3c. Scripts

The plugin requires 5 scripts at the path resolved in Phase 1 (`$EDF_SCRIPTS_DIR`,
referenced as `${EDF_SCRIPTS}/` in CLAUDE.md):

| Script | Purpose |
|--------|---------|
| `run-tests.sh` | Unit tests |
| `run-typecheck.sh` | Type check |
| `run-lint.sh` | Lint |
| `run-build.sh` | Build (can be `exit 0` if N/A) |
| `run-e2e.sh` | E2E tests (can be `exit 0` if not yet) |

Copy the appropriate starter scripts based on detected language:

```bash
mkdir -p $EDF_SCRIPTS_DIR
```

**TypeScript:**
```bash
cp ${CLAUDE_PLUGIN_ROOT}/starters/scripts/typescript/run-tests.sh $EDF_SCRIPTS_DIR/
cp ${CLAUDE_PLUGIN_ROOT}/starters/scripts/typescript/run-typecheck.sh $EDF_SCRIPTS_DIR/
cp ${CLAUDE_PLUGIN_ROOT}/starters/scripts/typescript/run-lint.sh $EDF_SCRIPTS_DIR/
cp ${CLAUDE_PLUGIN_ROOT}/starters/scripts/typescript/run-build.sh $EDF_SCRIPTS_DIR/
cp ${CLAUDE_PLUGIN_ROOT}/starters/scripts/typescript/run-e2e.sh $EDF_SCRIPTS_DIR/
```

**Python:**
```bash
cp ${CLAUDE_PLUGIN_ROOT}/starters/scripts/python/run-tests.sh $EDF_SCRIPTS_DIR/
cp ${CLAUDE_PLUGIN_ROOT}/starters/scripts/python/run-typecheck.sh $EDF_SCRIPTS_DIR/
cp ${CLAUDE_PLUGIN_ROOT}/starters/scripts/python/run-lint.sh $EDF_SCRIPTS_DIR/
cp ${CLAUDE_PLUGIN_ROOT}/starters/scripts/python/run-build.sh $EDF_SCRIPTS_DIR/
cp ${CLAUDE_PLUGIN_ROOT}/starters/scripts/python/run-e2e.sh $EDF_SCRIPTS_DIR/
```

**Other languages (Rust, Go):** use the closest starter and tell the user to
adjust the commands inside.

If a script already exists from a previous run, skip it. If a script exists
that the user wrote (not from a starter), it should have been backed up in
Phase 2 — confirm before overwriting.

Make scripts executable:
```bash
chmod +x $EDF_SCRIPTS_DIR/*.sh
```

Commit:
```bash
git add $EDF_SCRIPTS_DIR/
git commit -m "chore: add EDF verification scripts"
```

#### 3d. Environment configuration

**`.env` file:**

Read `.env` if it exists. Check for `EDF_SCRIPTS`, `EDF_FEATURE_PREFIX`,
and `EDF_FEATURE_PROM_DIR`.

If `EDF_SCRIPTS` is missing, append with the default resolved in Phase 1:

```
EDF_SCRIPTS=scripts
```

If `EDF_FEATURE_PREFIX` is missing, derive a default from the repo name
(uppercase initials: `engineering-delivery-framework` → `EDF`). Append:

```
EDF_FEATURE_PREFIX=<derived-prefix>
```

If `EDF_FEATURE_PROM_DIR` is missing, append with the default path:

```
EDF_FEATURE_PROM_DIR=monitoring/textfile_collector
```

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

If `.gitignore` does not exist and the project doesn't use an alternative
(`.dockerignore`-only, etc.), create a minimal one.

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

Do not create an empty `.github/project.env` — let the user set it up.

Commit:
```bash
git add .env .gitignore
git commit -m "chore: EDF environment configuration"
```

Skip the commit if no changes.

#### 3e. docs/adr/ directory

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

Commit:
```bash
git add docs/adr/README.md
git commit -m "docs: initialise ADR directory"
```

Skip if the directory and README already exist.

#### 3f. CI workflows (optional)

Ask the user:

> EDF provides CI workflow starters for TypeScript and Python. Copy one to
> `.github/workflows/`?

If the user says yes and the language is TypeScript or Python:

```bash
mkdir -p .github/workflows
cp ${CLAUDE_PLUGIN_ROOT}/starters/.github/workflows/ci-<typescript|python>.yml .github/workflows/
```

Commit:
```bash
git add .github/workflows/
git commit -m "ci: add EDF CI workflow"
```

---

### Phase 4: Verify

Run verification checks. Each check passes or fails — report all results.

1. **Scripts exist and are executable:**
   ```bash
   for script in run-tests.sh run-typecheck.sh run-lint.sh run-build.sh run-e2e.sh; do
     if [ -x "$EDF_SCRIPTS_DIR/$script" ]; then
       echo "  OK $EDF_SCRIPTS_DIR/$script"
     else
       echo "  MISSING $EDF_SCRIPTS_DIR/$script"
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

Report as a checklist. If any checks fail, tell the user what to fix.

---

### Phase 5: Report

Summarise everything that was done:

```
## EDF migration complete

### Backed up
- scripts.backup.20260514-2153/ — 2 conflicting scripts
- skills.backup.20260514-2153/ — 2 conflicting skills

### Created / modified
- CLAUDE.md — added 4 sections
- kb/file-map.md — populated 6 concepts
- kb/conventions.md — populated 5 concepts
- kb/architecture.md — template (needs project-specific rules)
- kb/anti-patterns.md — template (needs project-specific patterns)
- $EDF_SCRIPTS_DIR/ — 5 verification scripts (TypeScript)
- .env — added EDF_SCRIPTS, EDF_FEATURE_PREFIX, EDF_FEATURE_PROM_DIR
- .gitignore — added .diagnostics/, .claude/
- docs/adr/ — created directory

### Verification
- 5/5 scripts executable
- 4/4 kb files present
- 6/6 CLAUDE.md sections present
- 3/3 .env variables set
- 2/2 .gitignore patterns present

### What the team should know
1. **New workflow:** EDF skills are available as `/edf:<name>`. The core
   pipeline is `/discovery → /requirements → /kickoff → /architect → /feature`.
2. **kb files are living documents.** Update `kb/architecture.md` with
   architecture rules as soon as possible — `/pr-review` reads them on every
   review. Add entries to `kb/anti-patterns.md` as the team discovers
   recurring issues.
3. **Scripts at `$EDF_SCRIPTS_DIR/`.** These wrap your project's test/lint/build
   commands. Edit them if your commands differ from the starter defaults. The
   path is configured via `EDF_SCRIPTS` in `.env` — change it there if needed.
4. **Skills that were backed up** are in `skills.backup.<timestamp>/`.
   Reconcile any that your team still needs.
5. **`.github/project.env` is not yet configured.** Board-aware skills will
   fail until it's set up.

### Suggested next steps
1. Push this branch and create a PR for the team to review the migration changes.
2. Once merged, fill in `kb/architecture.md` — start with the boundary rule.
3. Fill in `kb/anti-patterns.md` — start with framework anti-patterns.
4. Verify the scripts work: `$EDF_SCRIPTS_DIR/run-tests.sh`.
5. Set up `.github/project.env` if using GitHub Projects.
```

---

## Guidelines

- **Never overwrite without backup.** Every destructive action is preceded by
  a timestamped backup. This skill should be safe to run on any project at
  any time.
- **Idempotent.** Files that already exist are skipped. Backups are
  timestamped so multiple runs don't collide.
- **Detect, don't assume.** Read the actual project state. Don't guess the
  language, don't assume directories exist.
- **User gates at key decisions.** Stop and confirm before: (a) the migration
  plan, (b) CLAUDE.md merges, (c) kb value proposals.
- **No data loss.** Skills, scripts, and hooks that conflict are backed up,
  not deleted. The user reconciles them later.
- **British English** in all output.
- **No Co-Authored-By trailers** in commit messages.
- **Commit after each logical change.** Separate commits for CLAUDE.md, kb/,
  scripts, .env, adr/ — not one giant commit.
- **The project is not broken if something fails.** Each phase is independent.
  If kb population fails, the scripts are still copied. If .env setup fails,
  CLAUDE.md is still merged. Report failures clearly and let the user fix
  them.
- **Don't invent project details.** When proposing kb values, base them on
  what you actually find in the project. If you can't find a concept
  (e.g. no `engine-dir` exists), leave the placeholder and tell the user.
- **Respect existing content.** When merging CLAUDE.md, preserve every
  existing section. Only append missing sections at the end.
