# Review-Focused LLD Diagram Improvements — V1 Requirements

## Document Control

| Field | Value |
|-------|-------|
| Version | 0.1 |
| Status | Draft — Structure |
| Author | LS / Claude |
| Created | 2026-08-01 |
| Last updated | 2026-08-01 |

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-08-01 | LS / Claude | Initial draft — epics, stories, roles |

---

## Context / Background

The EDF LLD (Low-Level Design) document is the primary artefact reviewers use to build
theory about a feature before inspecting its implementation. Today, Part A diagrams render
with flat, unresolvable participant names — a reviewer seeing `AuthHelper` in a sequence
diagram must manually grep the codebase to find the corresponding source file, losing their
place in the design document. Enforcement points (authZ, validation, error handling) are
buried in Part B prose and invisible in the diagram surface where reviewers spend most of
their time. Feedback requires tool-switching between the markdown preview, source editor,
and GitHub.

This version enriches the LLD diagram surface into a navigable review cockpit. Template
changes add diagram types (state, ER, flowchart), a standard colour palette, enforcement
annotations, and `click` directives on every participant. A thin VSCode extension
intercepts those clicks in the markdown preview: hover to peek at ~40 lines of source,
click to open the file in an adjacent column, and insert `[Review]` comments without
leaving the review flow. The conventions degrade gracefully in GitHub and other renderers
that lack the extension.

The discovery doc ([v1-discovery.md](../discovery/v1-discovery.md)) defines 14 features
across three waves. V1 delivers the 11 Wave 1 features — the complete review-enabling
surface. Wave 2 (review convention documentation, upstream/downstream impact assessment)
and Wave 3+ (contextual test execution, bidirectional navigation) are deferred.

## Glossary

| Term | Definition |
|------|-----------|
| **LLD Part A** | The first half of an LLD document — behavioural diagrams (sequence, state, ER, flowchart) and an invariants table. The primary review surface. |
| **LLD Part B** | The second half of an LLD document — internal decomposition, function signatures, data shapes, and task breakdown for each component. |
| **`click` directive** | A Mermaid syntax element (`click ParticipantId "url"`) that makes a diagram node clickable. Used to link participants to source files or Part B anchors. |
| **`edf://` protocol** | A custom URL scheme (`edf://path/to/file.ts`) recognised by the EDF Review VSCode extension. Resolves to a workspace-relative file path. |
| **`classDef` palette** | A set of Mermaid `classDef` declarations defining colour-coded styles for diagram participants: error paths, auth boundaries, external services, and new components. |
| **Enforcement point** | A location in a sequence diagram where a cross-cutting concern (authZ, validation, SSRF boundary, error propagation) is enforced. Marked with a `Note` annotation. |
| **`[Review]` marker** | A blockquote convention (`> **[Review]:** <feedback>`) used to collect inline review feedback in EDF documents. Already established in `/requirements` and `/discovery`. |
| **Markdown preview** | VSCode's built-in rendered-markdown view (Ctrl+Shift+V). The extension augments this with `edf://` link handling. |
| **Graceful degradation** | The principle that `edf://` links must render as inert, harmless links in renderers that lack the extension (GitHub, other editors). No errors, no broken UX. |

## Design Principles / Constraints

1. **Diagram-first review surface** — Diagrams are the primary navigation surface for
   reviewers. Every diagram participant must resolve to something actionable (source file
   or Part B spec). No dead labels.
2. **Preview-sticky navigation** — Opening a source file from a diagram must not close or
   obscure the markdown preview. The preview stays visible so the reviewer remains oriented
   in the design document.
3. **Graceful degradation by default** — Every `edf://` link must be harmless when the
   extension is absent. GitHub PR reviews, external contributors, and non-VSCode users must
   never encounter broken links or error states.
4. **Convention over configuration** — The `classDef` palette, diagram type selection rules,
   and annotation placement are defined once in the template and skill instructions. No
   per-project or per-team customisation in V1.
5. **Thin extension surface** — The VSCode extension does three things: hover preview, click
   navigation, and quick-pick comment insertion. No code analysis, no diagram generation, no
   bidirectional sync. Complexity lives in the LLD generation, not the extension.
6. **Template and skill co-versioned** — Template changes (`lld/template.md`) and skill
   instruction changes (`lld/SKILL.md`) must stay in lockstep. Every template feature must
   have a corresponding generation rule in the skill.

## Roles

| Role | Type | Description |
|------|------|-----------|
| **LLD Reviewer** | Contextual | A developer reviewing an LLD before or alongside a PR. Reads Part A diagrams to build theory, cross-references implementation against design, and provides feedback via `[Review]` markers and PR comments. Reviews 2–5 LLDs per week. |
| **Plugin Maintainer** | Persistent | A developer working on the EDF plugin itself. Generates test LLDs to verify conventions, tests the VSCode extension, and ensures template/skill consistency. |

**Role relationships:** The LLD Reviewer is the primary beneficiary — every story delivers
value to this role. The Plugin Maintainer is the secondary beneficiary who ensures the
conventions remain self-documenting and verifiable. There are no permission boundaries
between these roles; the Maintainer is effectively a Reviewer who also modifies the
framework.

---

## Epic 1: LLD Template & Diagram Vocabulary [Priority: High]

The foundation. Enriches the LLD Part A template with conditional diagram types, a
standard colour palette, enforcement-point annotations, and `click` directives on every
diagram participant. Every downstream story (navigation, commenting, quality gates)
depends on diagrams having the right structure, palette, and link surface.

<a id="REQ-lld-template-diagram-vocabulary-conditional-diagram-types"></a>

### Story 1.1: Conditional diagram types (state, ER, flowchart)

**As a** Plugin Maintainer,
**I want to** extend the LLD template with conditional support for `stateDiagram-v2`,
`erDiagram`, and `flowchart TD` diagram types, gated by "When required" conditions,
**so that** LLD authors can express state machines, data models, and branching logic
directly in Part A instead of resorting to prose workarounds.

*(Acceptance criteria in next pass)*

---

<a id="REQ-lld-template-diagram-vocabulary-standard-classdef-palette"></a>

### Story 1.2: Standard `classDef` palette across all diagrams

**As an** LLD Reviewer,
**I want to** see consistent colour-coding applied to diagram participants — error paths
in red, auth boundaries in amber, external services in grey, and new components in teal,
**so that** I can identify enforcement boundaries and external dependencies at a glance
without reading prose.

*(Acceptance criteria in next pass)*

---

<a id="REQ-lld-template-diagram-vocabulary-note-annotations-enforcement-points"></a>

### Story 1.3: `Note` annotations on sequence diagrams for enforcement points

**As an** LLD Reviewer,
**I want to** see enforcement points (authZ, validation, SSRF boundaries, error
propagation) annotated directly on sequence diagrams as `Note` blocks,
**so that** I can verify that security and correctness boundaries are explicitly designed
into the interaction flow, not buried in Part B prose.

*(Acceptance criteria in next pass)*

---

<a id="REQ-lld-template-diagram-vocabulary-click-directives-diagram-participants"></a>

### Story 1.4: `click` directives on every diagram participant

**As an** LLD Reviewer,
**I want to** click on any diagram participant and navigate to its source file (for
existing code via `edf://`) or its Part B spec (for new components via `#LLD-` anchors),
**so that** I can verify implementation against design without leaving the markdown
preview or manually grepping the codebase.

*(Acceptance criteria in next pass)*

---

## Epic 2: VSCode Extension — Diagram Navigation [Priority: High]

The extension that makes `edf://` links functional in VSCode's markdown preview. Hover
to peek at source, click to open in an adjacent column, and navigate to Part B specs via
`#LLD-` anchors. Depends on Epic 1 for diagrams to carry `click` directives. Includes
graceful degradation so links are harmless when the extension is absent.

<a id="REQ-vscode-extension-diagram-navigation-hover-tooltip-source-preview"></a>

### Story 2.1: Hover tooltip showing source file preview

**As an** LLD Reviewer,
**I want to** hover over an `edf://` link in the markdown preview and see the first ~40
lines of the referenced source file in a tooltip,
**so that** I can verify the real function signature matches the design's assumptions
without opening the file or losing my place in the diagram.

*(Acceptance criteria in next pass)*

---

<a id="REQ-vscode-extension-diagram-navigation-click-opens-source-adjacent-column"></a>

### Story 2.2: Click opens source file in adjacent column

**As an** LLD Reviewer,
**I want to** click an `edf://` link and have the source file open in the adjacent VSCode
column while the markdown preview stays visible,
**so that** I can inspect the full implementation without tab-switching or losing
orientation in the design document.

*(Acceptance criteria in next pass)*

---

<a id="REQ-vscode-extension-diagram-navigation-lld-anchor-navigation-part-b"></a>

### Story 2.3: `#LLD-` anchor navigation to Part B specs

**As an** LLD Reviewer,
**I want to** click on a diagram participant marked as a new component (teal outline) and
have the preview scroll to its Part B internal decomposition section,
**so that** I can read the component's spec — function signatures, data shapes, and task
breakdown — in a single click instead of scroll-hunting through the document.

*(Acceptance criteria in next pass)*

---

<a id="REQ-vscode-extension-diagram-navigation-graceful-degradation-edf-links"></a>

### Story 2.4: Graceful degradation of `edf://` links in external renderers

**As a** Plugin Maintainer,
**I want to** ensure that `edf://` links render as inert, harmless links when the
markdown is viewed in GitHub, GitLab, or other non-VSCode renderers,
**so that** external reviewers and contributors never encounter broken links, error
states, or confusing UI when reading LLDs outside VSCode.

*(Acceptance criteria in next pass)*

---

## Epic 3: VSCode Extension — Review Feedback [Priority: Medium]

Closes the preview→source round-trip for adding review comments. When a reviewer
identifies an issue in the diagram preview, they can insert a `[Review]` marker under
the relevant LLD section heading without hunting through the source editor. Depends on
Epic 2 for the extension infrastructure (commands, activation, markdown preview
integration).

<a id="REQ-vscode-extension-review-feedback-quick-pick-insert-review-comment"></a>

### Story 3.1: Quick-pick section → insert `[Review]` comment

**As an** LLD Reviewer,
**I want to** invoke a command from the markdown preview that shows a quick-pick list of
LLD Part A section headings, and on selection inserts a `> **[Review]:** ` template under
that heading in the source editor with focus switched for typing,
**so that** I can add review feedback without manually finding the corresponding line in
the source markdown or breaking my review flow.

*(Acceptance criteria in next pass)*

---

## Epic 4: Skill Instructions & Quality Gates [Priority: Medium]

Updates to `/lld` skill instructions so the template conventions are self-documenting
and mechanically verifiable. Diagram type selection rules, `click` generation logic,
annotation placement guidelines, and a self-critique checklist item for navigability.
Ensures the Plugin Maintainer can verify that generated LLDs follow conventions.

<a id="REQ-skill-instructions-quality-gates-diagram-generation-rules-lld-skill"></a>

### Story 4.1: Diagram generation rules in `/lld` SKILL.md

**As a** Plugin Maintainer,
**I want to** update the `/lld` SKILL.md Step 2 with concrete generation rules for
diagram type selection, `click` directive generation, `classDef` application, and
`Note` annotation placement,
**so that** every `/lld` invocation produces diagrams that follow the new conventions
without the author needing to remember them.

*(Acceptance criteria in next pass)*

---

<a id="REQ-skill-instructions-quality-gates-self-critique-checklist-diagram-navigability"></a>

### Story 4.2: Self-critique checklist item for diagram navigability

**As a** Plugin Maintainer,
**I want to** add a diagram navigability check to the `/lld` Step 2.5 self-critique
checklist (every participant has a `click`, enforcement points are annotated, palette
is applied, `edf://` links use valid paths),
**so that** every LLD author catches navigability gaps during self-review, before the
document reaches a human reviewer.

*(Acceptance criteria in next pass)*

---

## Cross-Cutting Concerns

### Security

- **Path traversal prevention:** The `edf://` protocol handler must validate that resolved
  file paths are within the workspace root. An `edf://../../../etc/passwd` link must not
  resolve to a file outside the workspace.
- **No arbitrary code execution:** Hover tooltip content is extracted from source files
  via workspace APIs, not by executing the file. The extension must not evaluate or
  interpret file contents beyond reading text.
- **Extension permissions:** The extension requests only the `workspace.fs` read and
  `window.showTextDocument` capabilities. No network access, no filesystem write, no
  process execution.

### Performance

- **Hover tooltip latency:** The first ~40 lines of a source file must appear in the
  hover tooltip within 200ms of hover. File reading is synchronous and local — this is
  a workspace FS read, not a network call.
- **File open latency:** Click-to-open must issue `showTextDocument` within 100ms of
  the click event. The editor's own file-open animation is outside the extension's
  control.
- **Preview load overhead:** The extension's markdown preview scripts must not
  measurably increase preview render time. Script injection is < 5 KB of JavaScript.

### Observability

- **Extension errors** are logged to the VSCode output channel `EDF Review`. Every
  failed `edf://` resolution (file not found, path outside workspace, malformed URI)
  produces a log entry with the raw URI and the failure reason.
- **Preview script errors** are logged to the same output channel via
  `postMessage`-to-extension relay.

---

## What We Are NOT Building

- **Additional diagram types (C4Context, gantt, pie, etc.)** — V1 is scoped to
  `stateDiagram-v2`, `erDiagram`, and `flowchart TD` as conditional additions to the
  existing sequence diagram foundation. Other diagram types may be considered in
  future versions.
- **Per-project or per-team palette customisation** — The `classDef` palette is a
  single convention applied uniformly. Customisation adds configuration surface that
  V1 does not need.
- **Automated annotation generation from code analysis** — Enforcement point
  annotations are authored by the LLD writer (guided by skill instructions), not
  inferred from static analysis of the codebase.
- **Bidirectional navigation (code → diagram)** — Clicking a function in source code
  does not highlight the corresponding diagram participant. This requires Tree-sitter
  or equivalent code parsing and is deferred to Wave 3+.
- **Full code-to-diagram synchronisation engine** — Diagrams are not auto-updated
  when code changes. The `lld-sync` skill handles drift at the document level;
  real-time diagram sync is out of scope.
- **Real-time collaborative editing** — `[Review]` markers are an async convention,
  not a CRDT-backed live commenting system.
- **Contextual test execution from the LLD preview (F14)** — "Run tests for this
  section" requires test file path extraction and project command discovery. Deferred
  to Wave 3+.
- **CodeBoarding-style auto-generated diagrams** — Post-implementation diagram
  generation from code depends on external APIs (Gemini) and is deferred to Wave 3+.
- **Live drift detection between code and LLD diagrams** — Requires a diffing engine
  and is deferred to Wave 3+.
- **Inline code snippet rendering below diagrams in the preview** — Full code
  rendering in the preview is deferred to Wave 3+.

---

## V2 / Future

These Wave 2 and Wave 3+ features are out of scope for V1 but captured here as input
for future discovery and requirements cycles.

### Wave 2 — Review Workflow

| Feature | Description |
|---------|-------------|
| F10 — `[Review]` convention documented for LLDs | Extend the existing `[Review]` marker convention documentation to cover LLDs. No code changes — documentation and template mention only. |
| F12 — Upstream/downstream skill impact assessment | Check `lld-sync`, `pr-review`, `architect`, `feature-core` for compatibility with the new diagram conventions. May produce additional work items. |

### Wave 3+ — Future Enhancements

| Feature | Description |
|---------|-------------|
| F14 — Contextual "Run tests for this section" | Extract test file paths from the LLD Tasks section, discover project test commands, and offer a run command from the preview. |
| Bidirectional navigation | Click a function in source code → highlight the corresponding diagram participant. Requires Tree-sitter or equivalent parsing. |
| Auto-generated diagrams post-implementation | Use Gemini API to generate diagrams from completed code. External cost, unproven value. |
| Live drift detection | Detect when code has diverged from the LLD diagram and flag in the preview. Requires a diffing engine. |

---

## Open Questions

| # | Question | Context | Options | Impact |
|---|----------|---------|---------|--------|
| 1 | Should F11 (graceful degradation) be verified against specific GitHub markdown renderer versions, or is "harmless dead link" behaviour sufficient as a general requirement? | The discovery doc states `_self` target + unrecognised URL scheme → cursor changes, no navigation, no error. GitHub's Mermaid renderer may evolve independently. | (a) General requirement: link must not cause errors or navigation in any renderer; (b) Specific: test against GitHub, GitLab, and Bitbucket renderers | If GitHub changes its Mermaid link handling, F11's ACs may need updating. Currently, all major renderers treat unknown URL schemes as inert in `<a>` tags. |
| 2 | What is the exact mechanism for the preview→extension communication channel for hover tooltips? | Discovery references `markdown.previewScripts` + `onDidReceivePreviewMessage` with "panel reference for reply." The exact API surface should be validated during implementation. | (a) Use `postMessage` from preview script → extension `onDidReceivePreviewMessage`; (b) Use a custom `vscode-resource` URI scheme | The `postMessage` approach is the standard VSCode extension pattern. The implementation story should include a spike to confirm the API works for hover events specifically. |
| 3 | Should the `classDef` palette colours be chosen now or deferred to implementation? | The discovery says "Colours match EDF pipeline flowcharts." If EDF pipeline flowcharts already use specific hex values, these should be referenced. Otherwise the palette is an implementation detail. | (a) Specify exact hex values in requirements; (b) Defer to implementation, constrained by "match EDF pipeline flowcharts" | Low impact on scope. Deferring avoids bikeshedding in the requirements phase. |
| 4 | Does F13 (quick-pick → insert `[Review]`) need the section headings parsed from the markdown AST, or is a regex-based extraction of `##`/`###` headings sufficient? | The discovery says "using the LLD's own section structure as the navigation anchor." Parsing accuracy affects robustness. | (a) Use a simple regex for `##`/`###` headings; (b) Parse the markdown AST with a library | Regex is simpler and sufficient for the LLD's predictable heading structure. An AST parser adds dependency weight for marginal gain. |
