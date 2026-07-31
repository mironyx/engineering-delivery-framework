# LLD Template

The LLD is structured in two parts. **Part A** is for human review — a reviewer can read
Part A alone and build sufficient theory about the feature. **Part B** is for the implementing
agent — detailed enough for `/feature` to produce correct code autonomously.

One file per phase (phase mode) or one file per task (epic mode). Each implementation plan
section becomes a top-level heading.

```markdown
# Low-Level Design: Phase N — [Phase Name]

## Document Control

| Field | Value |
|-------|-------|
| Version | 0.1 |
| Status | Draft |
| Author | LS / Claude |
| Created | [today's date] |
| Parent | [v<N>-design.md](v<N>-design.md) |
| Implementation plan | [Phase N](../plans/<resolved-plan-filename>.md) |

---

**Layout rule — two contiguous passes, never interleaved.** Every section number N.k in
this document appears exactly twice: a Part A block (`## N.k [Section Name]`, under the
`# Part A` heading) and a Part B block (`## N.k [Section Name] — Implementation`, under the
`# Part B` heading). Emit **all** Part A blocks for every section first, then **all** Part B
blocks. Do not emit a section's Part A + Part B content in one place, and do not move a
Part B block above the `# Part B` heading.

# Part A — Human-Reviewable Design

> Both the human reviewer and the implementing agent read this part.
> For the reviewer, it builds theory about the feature. For the agent, it provides
> the conceptual foundation that Part B's details depend on.
> It answers: what does the feature do, how do the parts interact,
> what must always be true, and how do we know it works.

## N.1 [Section Name]

**Stories:** [story numbers]
**Layers:** DB | BE | FE

### Purpose
[1-3 sentences: what this section delivers and why]

### Behavioural Flows

Sequence diagrams for every non-trivial interaction (>2 components communicating).
Use mermaid `sequenceDiagram` syntax. One diagram per key flow (happy path, error path,
async/webhook flows as needed).

` ` `mermaid
sequenceDiagram
    participant Client
    participant API as API Route
    participant Service
    participant DB as Database

    Client->>API: POST /api/example
    API->>Service: processRequest(ctx, params)
    Service->>DB: query(...)
    DB-->>Service: rows
    Service-->>API: Result
    API-->>Client: 200 OK
` ` `

**When required:** Any flow involving >2 components or services. API routes with
auth + service + DB. Webhook handling chains. Multi-step UI interactions with server calls.

**When optional:** Single-component CRUD. Pure utility functions. Schema-only changes.

### Structural Overview

Module/class dependency diagram showing how the pieces fit together. Use mermaid
`classDiagram` syntax. Works for both class-based and module-based codebases:

- **Classes** — show with methods and relationships (inheritance, composition)
- **Modules** — use `<<module>>` stereotype, show exported functions
- **Interfaces/Ports** — use `<<interface>>`, show who implements them
- **Direction** — arrows show dependency direction (who depends on whom)

` ` `mermaid
classDiagram
    class engine/scoring {
        <<module>>
        +calculateScore(responses) Score
        +buildDimensions(config) Dimension[]
    }
    class ports/github {
        <<interface>>
        +fetchPRs(org, repo) PR[]
    }
    class adapters/github {
        <<module>>
        +createGitHubClient(token) GitHubPort
    }
    engine/scoring --> ports/github : depends on
    adapters/github ..|> ports/github : implements
` ` `

**When required:** Any task that introduces new modules/classes, modifies module boundaries,
or adds new dependencies between existing modules. Changes touching the ports/adapters layer.

**When optional:** Changes within a single existing module that do not alter its public
surface or dependencies.

### Visual Specifications

> **When required:** Any section that includes a Frontend layer. The visual spec
> shows what the user sees — layout, spatial hierarchy, and all relevant UI states.
> It is the third view alongside behavioural flows (how it works) and structural
> overview (how pieces connect).

Screenshots of the wireframes/mockups for each screen this section touches.
Generated during `/requirements` via `frontend-design` and propagated here.
If the LLD refines visual details, the HTML wireframe is updated and new
screenshots are taken.

| Screen | Visual reference | States shown | REQ anchors | HLD component |
|--------|-----------------|--------------|-------------|---------------|
| [Page/Screen name] | [docs/design/v{N}/vis-name.html](vis-name.html) | Loading, Error, Empty, Success | [REQ-xxx-xxx](#req-xxx-xxx) | [Component name](v<N>-design.md#anchor) |

[Screenshot embedded — one per screen, showing the primary state. Additional
screenshots for error, empty, and edge-case states as needed.]

![Screen name — Success state](vis-name-success.png)

![Screen name — Error state](vis-name-error.png)

> **Constraint:** Every state declared in the UI states table (Part B) must have a
> corresponding visual representation shown here. A state declared in text but not
> shown visually is a review blocker — the implementing agent has no reference for
> what to build.

**When optional:** Pure backend sections, CLI-only changes, API-only changes,
schema migrations — anything with no UI surface.

### Invariants

Hard constraints that the implementation must satisfy. Collected in one place so the
reviewer can sign off on them and automated tools (`/pr-review`, `/feature-evaluator`)
can verify them.

Each invariant should be testable — either by a unit test, a type check, or a lint rule.

| # | Invariant | Verification |
|---|-----------|-------------|
| 1 | [e.g. Service never calls createClient() directly] | [e.g. grep for import; unit test with mock ApiContext] |
| 2 | [e.g. Webhook replay is idempotent — no duplicate rows] | [e.g. test calls handler twice, asserts row count unchanged] |
| 3 | [e.g. Engine module has zero framework imports] | [e.g. grep engine-dir for framework imports] |

### Acceptance Criteria

- [ ] [Concrete, testable criterion]
- [ ] [Another criterion]

### BDD Specs

` ` `ts
describe('[context]', () => {
  it('[behaviour — given/when/then]');
  it('[another behaviour]');
});
` ` `

### HLD coverage assessment
- [Section X.Y] — sufficient, referenced only
- [Section X.Z] — needs extension, detailed below

## N.2 [Next Section Name]

[Repeat the Part A subsections from N.1: Purpose, Behavioural Flows, Structural Overview,
Visual Specifications, Invariants, Acceptance Criteria, BDD Specs, HLD coverage assessment.
Emit a `## N.k` block for every remaining section here — these all belong under the
`# Part A` heading. Do NOT include any Part B content (file paths, function signatures,
internal decomposition) in this part.]

---

# Part B — Agent Implementation Detail

> The implementing agent (`/feature`) reads both parts — Part A for the conceptual
> model, Part B for precise file paths, types, function signatures, and decomposition
> rules. A human reviewer may scan Part B for completeness but does not need to
> review it line-by-line.

## N.1 [Section Name] — Implementation

### [Layer: Database] (if applicable)

See [v<N>-design.md §N.N](v<N>-design.md#section-anchor) for [schema/functions].

[Only what the HLD doesn't cover: migration file strategy, seed data, test isolation, etc.]

### [Layer: Backend] (if applicable)

See [v<N>-design.md §N.N](v<N>-design.md#section-anchor) for [contracts].

#### File structure
` ` `
src/lib/module/
  file.ts          — [purpose]
  file.test.ts     — [what it tests]
` ` `

#### Internal types
[Types not in the public L4 contract but needed for implementation]

> **Constraint:** For any type referencing a DB column, grep the project's canonical DB-types file (generated or hand-authored) to confirm the type matches the actual column/enum definition. Mismatches cause casts and workarounds at the call site — fix the type here in the LLD, not downstream in the implementation.

> **Constraint:** For any third-party surface used here that was not read from this repo — SDK/library config shape, function or hook signature, cloud-provider argument, query-language or IaC semantic — verify it against the official docs with `WebFetch`/`WebSearch` and cite the doc URL + library version. If it cannot be verified, mark the claim `> **Unverified — recall-based:**` so the risk is explicit. Recall of an exact API surface can be wrong while reading internally consistent, so neither authoring nor review catches it without a doc check.
>
> **Pin the version in the LLD.** Every third-party tool, SDK, cloud provider, Terraform provider, or external API used in this design must state its exact version or version constraint (e.g. `hashicorp/azurerm ~> 3.108`, `@azure/storage-blob@12.18.0`, `OpenAI API 2024-11`). This makes drift trackable: when a version changes, the LLD's pinned version is the anchor for impact analysis. If the design is version-agnostic (e.g. a generic HTTP client), state that explicitly rather than omitting the version.

#### Function signatures
[Key internal functions with their signatures and behaviour]

#### Internal decomposition — [route or component]

For every non-trivial API route or component, add an explicit internal decomposition section
**before implementation begins**. Name every function, class, or interface that will exist
internally and state what is forbidden.

```
Controller (stays in route.ts, ≤ 5 lines):
- const ctx = await createApiContext(request)   // per-request composition root: assembles all clients
- return json(await service.fn(ctx, params))    // injects context into service

Service ([endpoint]/service.ts):
- Exported: `serviceFn(ctx: ApiContext, params: ParamType): Promise<ResponseType>` — [one-line purpose]
- Receives ApiContext (DI) — never calls createClient() or any infrastructure factory

  Private helpers (≤ 20 lines each):
  - `helperName(params): ReturnType` — [purpose and error behaviour]

Extracted to helpers.ts (if applicable):
- `pureFunction(...)` — [why extracted: testability, reuse]
```

Use `> **Constraint:**` for notes written **before** implementation (hard limits for the implementing
agent). Use `> **Implementation note (issue #N):**` only to document decisions made **after**
implementation — these are historical records, not pre-implementation guidance.

#### Error handling
[Error cases, codes, and recovery strategies]

### [Layer: Frontend] (if applicable)

See [v<N>-design.md §N.N](v<N>-design.md#section-anchor) for [contracts].

#### Component tree
` ` `
PageComponent
  ├── SubComponent
  │   └── ChildComponent
  └── AnotherComponent
` ` `

> **Constraint (server components):** Use module-level render helper functions rather than JSX sub-components inside server component files. Sub-components defined in the same file are opaque to test traversal — `render()` returns a serialised tree, so `screen.getByRole` cannot cross a sub-component boundary. Module-level helpers keep assertions traversable without extra wrapper renders.

#### Page routes
| Route | Component | Data fetching | Auth |
|-------|-----------|--------------|------|

#### UI states
| State | Trigger | Display |
|-------|---------|---------|
| Loading | Initial fetch | Skeleton |
| Error | API failure | Error message + retry |
| Empty | No data | Empty state message |
| Success | Data loaded | Content |

#### Client state
[What state lives on the client, how it's managed]

## N.2 [Next Section Name] — Implementation

[Repeat the Part B subsections from N.1: Database, Backend, and Frontend layers with their
File structure / Internal types / Function signatures / Internal decomposition / Error
handling subsections. Emit a `## N.k — Implementation` block for every remaining section
here — these all belong under the `# Part B` heading. Do NOT include Part A content here.]

---

## Cross-References

### Internal (within this phase)
- §N.1 depends on: —
- §N.2 depends on: [§N.1](#n1-section-name)
- ...

### External
- Depends on: [lld-artefact-pipeline.md](lld-artefact-pipeline.md) (if applicable)
- Depended on by: Phase M LLD (if applicable)

### Shared types
[Types used across multiple sections in this phase]

---

## Tasks

[Task entries per the format in SKILL.md Step 3, covering ALL sections in the phase]

---

## Execution Order

### Dependency DAG

` ` `mermaid
graph LR
  T1[Task 1: ...] --> T3[Task 3: ...]
  T2[Task 2: ...] --> T3
` ` `

### Execution Waves

| Wave | Tasks | Blocked by | Notes |
|------|-------|------------|-------|
| 1 | Task 1, Task 2 | — | Parallelisable |
| 2 | Task 3 | Wave 1 | |
```
