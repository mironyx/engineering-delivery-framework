# Framework ADRs

Architecture Decision Records for the EDF framework itself. Every project that
adopts the EDF plugin inherits these decisions unchanged.

## What lives here

ADRs whose subject is **how the EDF process works** — the design-down pipeline,
the epic/task model, traceability anchors, the feature evaluator step, the
tiered process model. These shape the skills and agents in this plugin.

## What does NOT live here

ADRs that are project decisions — the project's datastore, auth model, runtime,
framework choices, API conventions, RLS strategy, etc. Those live in the
consuming project's `docs/adr/` and are numbered by the project.

## Test for "framework ADR"

> Would every project that adopts EDF inherit this decision unchanged?
>
> If yes, plugin. If a sane project might decide otherwise, project-local.

## Numbering

Framework ADRs use the same `NNNN-title.md` numbering as project ADRs. The
plugin currently claims numbers 0018, 0019, 0021, 0022, 0026, 0030, 0033 — pulled from the
seed project (`feature-comprehension-score`) where they originated. Consuming
projects should treat those numbers as reserved by the framework and pick
unused numbers for their own ADRs.

If/when the framework ships to a third-party consumer, this numbering may
migrate to a separate prefix (e.g. `EDF-NNNN`) to avoid the awkward gaps. Not
done yet — current practice is "keep the existing numbers, fill gaps from
project side".

## Current contents

| ADR | Subject |
|---|---|
| [0018](0018-epic-task-organisation.md) | Epic/task work organisation — the unit of work |
| [0019](0019-feature-evaluator-agent.md) | Feature evaluator agent in `/feature` |
| [0021](0021-project-bootstrap-pipeline.md) | Project bootstrap pipeline (`/discovery → /requirements → /kickoff → /architect → /feature`) |
| [0022](0022-tiered-feature-process.md) | Tiered feature process (bug / feature / epic / phase tiers) |
| [0026](0026-stable-ids-requirements-lld.md) | Stable IDs for requirements stories and LLD sections |
| [0030](0030-feature-team-agent.md) | Feature team agent in `/feature-team` |
| [0033](0033-feature-team-agent-implementation.md) | Feature team agent implementation details |

## How references resolve

Skills in `plugins/edf/skills/<skill>/SKILL.md` reference these ADRs via
`../../docs/adr/NNNN-*.md` (two levels up from the skill, then into the plugin
docs). Agents in `plugins/edf/agents/<agent>.md` reference them via
`../docs/adr/NNNN-*.md` (one level up).

When a skill cites a project-level ADR (e.g. one made by the consuming project),
the path resolves into the consuming project's `docs/adr/` — those references
stay project-relative.
