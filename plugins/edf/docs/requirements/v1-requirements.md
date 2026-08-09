# Review-Focused LLD Diagram Improvements — V1 Requirements

## Document Control

| Field | Value |
|-------|-------|
| Version | 1.2 |
| Status | Final |
| Author | LS / Claude |
| Created | 2026-08-01 |
| Last updated | 2026-08-09 |

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-08-01 | LS / Claude | Initial draft — epics, stories, roles |
| 0.2 | 2026-08-01 | LS / Claude | Acceptance criteria for all 11 stories; closed stale open questions; added security ACs to Stories 2.1/2.2; added extension packaging deferral |
| 0.3 | 2026-08-01 | LS / Claude | Testability fixes: tightened 3 vague ACs (Story 1.3 AC5, Story 2.4 AC5, Story 4.1 AC6) |
| 0.4 | 2026-08-01 | LS / Claude | Review fixes: corrected visual reference paths; aligned #LLD- anchor format with ADR-0026; resolved AC1/AC4 contradiction in Story 1.2; removed cross-epic AC dependency on Story 4.2 |
| 1.0 | 2026-08-01 | LS / Claude | Finalised — Gate 2 approved |
| 1.1 | 2026-08-08 | LS / Claude | Aligned with verified Mermaid syntax: type-aware navigability (sequence `link`, class/flow/state `click`+tooltip, erDiagram none), removed `_self` claims, classDef-inside-diagram rule, palette hex restored to template |
| 1.2 | 2026-08-09 | LS / Claude | Dropped `edf://` scheme (Mermaid `securityLevel: strict` strips custom schemes from rendered links): navigability links use bare workspace-relative paths; interception scoped to SVG anchors; Story 2.4 degradation reworded; glossary, principles, and ACs updated across Stories 1.4/2.1/2.2/2.4/4.1/4.2 |

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

**Implementation note:** Template and skill changes are being developed alongside this
requirements process as part of the standard EDF pipeline (discovery → requirements →
kickoff → feature). The Mermaid syntax fixes to `lld/template.md` and `lld/SKILL.md`
(sequence `link` directive, `click`+tooltip for class/flow/state, erDiagram without
links, classDef-inside-diagram rule) are already committed and validated with
mermaid-cli; the `extensions/edf-review/` scaffold exists as a working base with the
`peek`/`open` message handling in place. These stories define the complete, verified
deliverable — where work already exists, the story scope is to complete, verify, and
harden that work against the acceptance criteria below.

## Glossary

| Term | Definition |
|------|-----------|
| **LLD Part A** | The first half of an LLD document — behavioural diagrams (sequence, state, ER, flowchart) and an invariants table. The primary review surface. |
| **LLD Part B** | The second half of an LLD document — internal decomposition, function signatures, data shapes, and task breakdown for each component. |
| **Navigability link** | A Mermaid syntax element that makes a diagram node clickable so it can link to a source file or Part B anchor. The syntax depends on the diagram type: sequenceDiagram uses the `link <actor>: <label> @ <url>` directive; flowchart / classDiagram / stateDiagram use `click <node> href "<url>" "<tooltip>"`; erDiagram supports no interaction and participants are linked via prose. |
| **Workspace-relative navigability path** | A source-file link target written as a bare repo-relative path (e.g. `src/lib/auth/middleware.ts`) — no URL scheme. Mermaid's strict security mode strips custom schemes (like the abandoned `edf://`) from rendered links but preserves relative paths; the EDF Review VSCode extension resolves them against the workspace root. |
| **`classDef` palette** | A set of Mermaid `classDef` declarations defining colour-coded styles for diagram participants. The canonical palette is defined in `lld/template.md`: error (`#f7d6d6`), auth (`#f7eed6`), external (`#d6e8f7`), new (`#d4f0d4`). |
| **Enforcement point** | A location in a sequence diagram where a cross-cutting concern (authZ, validation, SSRF boundary, error propagation) is enforced. Marked with a `Note` annotation. |
| **`[Review]` marker** | A blockquote convention (`> **[Review]:** <feedback>`) used to collect inline review feedback in EDF documents. Already established in `/requirements` and `/discovery`. |
| **Markdown preview** | VSCode's built-in rendered-markdown view (Ctrl+Shift+V). The extension augments this with navigability-link handling. |
| **Graceful degradation** | The principle that navigability links must render as inert, harmless links in renderers that lack the extension (GitHub, other editors). No errors, no broken UX. |

## Design Principles / Constraints

1. **Diagram-first review surface** — Diagrams are the primary navigation surface for
   reviewers. Every diagram participant must resolve to something actionable (source file
   or Part B spec). No dead labels.
2. **Preview-sticky navigation** — Opening a source file from a diagram must not close or
   obscure the markdown preview. The preview stays visible so the reviewer remains oriented
   in the design document.
3. **Graceful degradation by default** — Every navigability link must be harmless when the
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
7. **Extension distribution (V1)** — The extension is loaded via VSCode's Extension
   Development Host for development and testing. Marketplace publishing, `.vsix` packaging,
   and consumer-facing installation instructions are deferred to a future version.

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

**Acceptance Criteria:**

- Given an LLD for a feature with UI state management (FE components with multiple
  visual states), when `/lld` Step 2 evaluates the feature's characteristics, then a
  `stateDiagram-v2` is included in Part A showing states and transitions.
- Given an LLD for a feature introducing new data entities or modifying entity
  relationships, when `/lld` Step 2 evaluates the feature's characteristics, then an
  `erDiagram` is included showing the relevant entities and their relationships.
- Given an LLD for a feature with branching business logic or decision flows, when
  `/lld` Step 2 evaluates the feature's characteristics, then a `flowchart TD` is
  included showing decision nodes and paths.
- Given an LLD for a feature with none of the above characteristics, when `/lld`
  Step 2 evaluates, then no conditional diagram types are added — the document
  contains only the standard sequence diagram.
- Given any conditional diagram type is included, when the resulting markdown is
  rendered in GitHub's Mermaid renderer, then the diagram renders without syntax
  errors.
- Given a conditional diagram type is included, when the template's "When required"
  gate is evaluated, then the gate condition is stated as a concrete, checkable rule
  (not a vague "if it seems useful").

**Notes:** The "When required" gates must be deterministic — the same feature
characteristics must always produce the same diagram types. The template defines
these gates; `/lld` SKILL.md Step 2 applies them.

---

<a id="REQ-lld-template-diagram-vocabulary-standard-classdef-palette"></a>

### Story 1.2: Standard `classDef` palette across all diagrams

**As an** LLD Reviewer,
**I want to** see consistent colour-coding applied to diagram participants — error paths
in red, auth boundaries in amber, external services in grey, and new components in teal,
**so that** I can identify enforcement boundaries and external dependencies at a glance
without reading prose.

**Acceptance Criteria:**

- Given any LLD Part A diagram, when rendered, then every participant matching one of
  the four defined roles is assigned its colour class: error (`#f7d6d6`), auth
  (`#f7eed6`), external (`#d6e8f7`), new (`#d4f0d4`). Participants not matching any
  role use Mermaid default styling.
- Given `classDef` blocks are defined inside the first diagram of each type that uses
  them (a standalone `classDef` block with no diagram-type keyword is invalid Mermaid),
  when a new diagram type is added to the document, then the existing palette classes
  are applied to participants matching those roles — no duplicate or divergent colour
  definitions.
- Given the palette is applied, when the document is viewed in GitHub's Mermaid
  renderer, then all four colours render distinctly and are distinguishable from each
  other.
- Given a diagram participant does not match any of the four defined roles, when
  rendered, then it uses the Mermaid default styling (no palette class applied).
- Given the palette table exists, when a maintainer updates a colour value, then
  the change is made in exactly one place (the template's palette table) and
  propagates to all diagrams.

**Notes:** The canonical hex values are defined in `lld/template.md` and are the
single source of truth. Story 4.1 ensures the skill instructions reference the
template's palette. The palette matches EDF pipeline flowchart conventions.

---

<a id="REQ-lld-template-diagram-vocabulary-note-annotations-enforcement-points"></a>

### Story 1.3: `Note` annotations on sequence diagrams for enforcement points

**As an** LLD Reviewer,
**I want to** see enforcement points (authZ, validation, SSRF boundaries, error
propagation) annotated directly on sequence diagrams as `Note` blocks,
**so that** I can verify that security and correctness boundaries are explicitly designed
into the interaction flow, not buried in Part B prose.

**Acceptance Criteria:**

- Given a sequence diagram where an interaction crosses an authZ boundary, when the
  diagram is generated, then a `Note over` or `Note right of` annotation marks the
  enforcement point with the authZ mechanism (e.g., "AuthZ: token validated —
  401 on invalid token").
- Given a sequence diagram where an interaction crosses a validation boundary, when
  the diagram is generated, then a `Note` annotation marks the validation enforcement
  point with the validation rule and rejection behaviour.
- Given a sequence diagram where a participant calls an external service, when the
  diagram is generated, then a `Note` annotation marks the SSRF boundary with the
  safeguard (e.g., "SSRF: URL validated against allowlist before fetch").
- Given a sequence diagram with an error propagation path, when the diagram is
  generated, then a `Note` annotation marks the error boundary with the error
  response code and recovery behaviour.
- Given a `Note` annotation exists, when the diagram is rendered in any
  Mermaid-compatible renderer (VSCode, GitHub, GitLab), then the note renders
  without Mermaid syntax errors and the note text is visible (not truncated,
  not hidden by `display: none`, not positioned outside the diagram bounds).
- Given a flow crosses a trust boundary without a stated enforcement point, when the
  diagram is reviewed against the template's enforcement annotation rules, then the
  omission is detectable by inspection (every trust-boundary-crossing interaction
  must have a visible `Note` annotation).

**Notes:** Enforcement annotations must be placed adjacent to the interaction they
describe, not in a legend block. An interaction that crosses multiple enforcement
boundaries (e.g., external service call that also requires authZ) must carry
multiple annotations — one per concern.

---

<a id="REQ-lld-template-diagram-vocabulary-click-directives-diagram-participants"></a>

### Story 1.4: Navigability links on every diagram participant

**As an** LLD Reviewer,
**I want to** click on any diagram participant and navigate to its source file (for
existing code via a workspace-relative path) or its Part B spec (for new components via
`#LLD-` anchors),
**so that** I can verify implementation against design without leaving the markdown
preview or manually grepping the codebase.

**Acceptance Criteria:**

- Given a sequence diagram participant representing existing code, when the diagram
  is generated, then it carries a `link` directive with the workspace-relative source
  file path (e.g., `link AuthMiddleware: source @ src/lib/auth/middleware.ts`).
- Given a flowchart, classDiagram, or stateDiagram participant representing existing
  code, when the diagram is generated, then it carries a `click` directive with the
  workspace-relative path and tooltip (e.g.,
  `click AuthMiddleware href "src/lib/auth/middleware.ts" "source"`).
- Given a sequence diagram participant representing a new component, when the diagram
  is generated, then it carries a `link` directive with a `#LLD-` anchor referencing
  the Part B section's stable anchor ID as defined by ADR-0026 (e.g.,
  `link DeliveryService: spec @ #LLD-v11-e11-1-delivery-service`).
- Given a flowchart, classDiagram, or stateDiagram participant representing a new
  component, when the diagram is generated, then it carries a `click` directive with
  a `#LLD-` anchor and tooltip (e.g.,
  `click DeliveryService href "#LLD-v11-e11-1-delivery-service" "spec"`).
- Given a diagram is fully generated, when the diagram source is inspected, then no
  participant is a "dead label" — every participant carries a navigability link
  appropriate to its diagram type (`link` on sequence diagrams, `click` on flowchart /
  classDiagram / stateDiagram) resolving to either a workspace-relative path or a
  `#LLD-` anchor. erDiagram participants are exempt (the type supports no interaction;
  refer to them in prose instead).
- Given a workspace-relative navigability link is rendered in a Mermaid diagram, when
  viewed in a renderer without the EDF extension (GitHub, GitLab), then the relative
  href is preserved and resolves against the page URL to a non-existent repo path (a
  404 page) — or the renderer strips diagram links entirely; either way no navigation
  to real content occurs and no error is raised on click.
- Given a navigability path references a file, when the path is constructed, then it
  is workspace-relative (no leading slash, no `..` segments) suitable for resolution
  by `vscode.Uri.joinPath`.
- Given a Part B section exists with a stable anchor ID, when a `#LLD-` link targets
  it, then the anchor ID follows the ADR-0026 format (`LLD-<epic-id>-<section-slug>`)
  and the link uses the full anchor ID as its fragment target.

**Notes:** The navigability link is the bridge between Epic 1 (template) and Epic 2
(extension). The extension intercepts navigability links in the preview; `#LLD-` anchors
work via native browser scrolling. The template must document the per-type mechanism
(`link` vs `click`) and both link types with examples.

---

## Epic 2: VSCode Extension — Diagram Navigation [Priority: High]

The extension that makes diagram navigability links functional in VSCode's markdown
preview. Hover to peek at source, click to open in an adjacent column, and navigate to
Part B specs via `#LLD-` anchors. Depends on Epic 1 for diagrams to carry navigability
links (`link` on
sequence diagrams, `click` on flowchart / classDiagram / stateDiagram). The extension
intercepts the `<a>` elements Mermaid renders for those directives — no DOM-injection
onto SVG nodes is required. Includes graceful degradation so links are harmless when the
extension is absent.

<a id="REQ-vscode-extension-diagram-navigation-hover-tooltip-source-preview"></a>

### Story 2.1: Hover tooltip showing source file preview

**As an** LLD Reviewer,
**I want to** hover over a navigability link in the markdown preview and see the first ~40
lines of the referenced source file in a tooltip,
**so that** I can verify the real function signature matches the design's assumptions
without opening the file or losing my place in the diagram.

**Acceptance Criteria:**

- Given an LLD markdown preview is open with rendered Mermaid diagrams containing
  navigability links, when the reviewer hovers over a navigability link for 150ms,
  then a tooltip appears showing the first 40 lines of the referenced source file.
- Given a tooltip is displayed, when the reviewer moves the mouse away from the link,
  then the tooltip dismisses within 200ms.
- Given a navigability link points to a file that does not exist in the workspace, when
  the reviewer hovers, then the tooltip shows "File not found: <path>" and no file
  read is attempted.
- Given a navigability link contains a path with `..` segments that would resolve
  outside the workspace root, when the extension resolves the path, then the tooltip
  shows "Path outside workspace: <path>" and no file content is read.
- Given a navigability link contains a malformed or empty path, when the reviewer
  hovers, then the tooltip shows "Invalid path: <raw-value>" and no file read is
  attempted.
- Given the tooltip content is displayed, when measured from the hover event to the
  tooltip appearing, then the latency is under 200ms (excluding the 150ms debounce).
- Given the extension reads a source file for the tooltip, when the file is read,
  then the read uses `vscode.workspace.fs.readFile` with a `vscode.Uri` validated to
  be within the workspace root — no arbitrary filesystem access.
- Given the tooltip is rendered, when styled, then it uses VSCode theme variables
  (`--vscode-editor-background`, `--vscode-editor-foreground`,
  `--vscode-editor-font-family`) so it matches the user's colour theme.

### Visual Reference

- [Markdown Preview Navigation wireframe](../design/v1/vis-markdown-preview-navigation.html) — hover state (tooltip over WebhookController)

---

<a id="REQ-vscode-extension-diagram-navigation-click-opens-source-adjacent-column"></a>

### Story 2.2: Click opens source file in adjacent column

**As an** LLD Reviewer,
**I want to** click a navigability link and have the source file open in the adjacent VSCode
column while the markdown preview stays visible,
**so that** I can inspect the full implementation without tab-switching or losing
orientation in the design document.

**Acceptance Criteria:**

- Given a reviewer hovers over a navigability link in the markdown preview, when they
  click the link, then the referenced source file opens in the adjacent VSCode column
  using `vscode.window.showTextDocument(uri, { viewColumn: ViewColumn.Beside })`.
- Given a source file opens in the adjacent column, when the operation completes,
  then the markdown preview remains visible in its original column — it is not closed
  or replaced.
- Given a navigability link points to a file that does not exist, when clicked, then a
  VSCode error message "File not found: <path>" is shown and no editor tab is opened.
- Given a navigability link path resolves outside the workspace root (contains `..`
  segments escaping the root), when clicked, then the file is not opened, an error is
  logged to the "EDF Review" output channel with the raw URI and failure reason, and
  a VSCode information message "Cannot open file outside workspace" is shown.
- Given a click event occurs on a navigability link, when measured, then
  `showTextDocument` is issued within 100ms of the click event.
- Given the extension opens a file, when the file is already open in another tab,
  then the existing tab is focused (the same file is not opened twice).

### Visual Reference

- [Markdown Preview Navigation wireframe](../design/v1/vis-markdown-preview-navigation.html) — click state (source file in adjacent column, preview stays)

---

<a id="REQ-vscode-extension-diagram-navigation-lld-anchor-navigation-part-b"></a>

### Story 2.3: `#LLD-` anchor navigation to Part B specs

**As an** LLD Reviewer,
**I want to** click on a diagram participant marked as a new component (teal outline) and
have the preview scroll to its Part B internal decomposition section,
**so that** I can read the component's spec — function signatures, data shapes, and task
breakdown — in a single click instead of scroll-hunting through the document.

**Acceptance Criteria:**

- Given a diagram participant has a navigability link with a `#LLD-` anchor (e.g.,
  `#LLD-delivery-service`), when the reviewer clicks it in the markdown preview, then
  the preview scrolls to the corresponding Part B `<a id="LLD-delivery-service">`
  element.
- Given a `#LLD-` anchor link is clicked in GitHub's markdown renderer, when the
  browser processes the click, then the browser navigates to the anchor using
  standard page-internal linking — no extension required.
- Given a `#LLD-` anchor target does not exist in the document (broken anchor), when
  clicked, then the preview does not scroll and no error is displayed (silent no-op
  in the preview).
- Given a Part B section has a stable anchor ID, when the LLD is generated, then the
  anchor ID follows the ADR-0026 format (`LLD-<epic-id>-<section-slug>`) and the
  `click` directive's `#LLD-` fragment target matches that anchor ID exactly.

### Visual Reference

- [Markdown Preview Navigation wireframe](../design/v1/vis-markdown-preview-navigation.html) — anchor state (Part B section scrolled into view)

---

<a id="REQ-vscode-extension-diagram-navigation-graceful-degradation-navigability-links"></a>

### Story 2.4: Graceful degradation of navigability links in external renderers

**As a** Plugin Maintainer,
**I want to** ensure that navigability links render as inert, harmless links when the
markdown is viewed in GitHub, GitLab, or other non-VSCode renderers,
**so that** external reviewers and contributors never encounter broken links, error
states, or confusing UI when reading LLDs outside VSCode.

**Acceptance Criteria:**

- Given an LLD is viewed in GitHub's markdown renderer, when navigability links appear
  in Mermaid diagrams, then they render as standard `<a>` elements carrying a relative
  href — clicking produces no navigation to real content (a 404 page at worst, or no
  navigation if the renderer strips diagram links), never an error or console warning.
- Given an LLD is viewed in GitLab's markdown renderer, when navigability links are
  rendered, then the links are inert — no broken-link styling, no error page on
  click, no JavaScript exceptions in the browser console.
- Given an LLD is viewed as raw markdown in a text editor without preview, when the
  markdown source is read, then navigability paths are clearly identifiable as
  workspace-relative file references (human-readable paths like
  `src/lib/auth/middleware.ts`).
- Given Mermaid renders a workspace-relative href as a standard `<a>` element, when
  the `<a>` element is generated, then clicking the link in any browser produces no
  error and no console warning — the relative href either navigates to a 404 page or
  is stripped by the renderer, both harmless.
- Given the extension is not installed, when navigability links are tested in a
  fresh browser profile against the current versions of GitHub and GitLab, then
  no error or console warning occurs on click — the link is inert (404 at worst).

**Notes:** This is primarily a verification and documentation story. The template
specifies workspace-relative path links; the "harmless dead link" behaviour is inherent
to a relative href resolving against the page URL (or being stripped by the renderer) —
it does not depend on `_self` targets. The extension does not need to handle the
degradation case — it is only active in VSCode. The story deliverable is a verification
report confirming degradation across GitHub, GitLab, and at least one other renderer,
plus any template adjustments needed.

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

**Acceptance Criteria:**

- Given the markdown preview is open for an LLD document, when the reviewer invokes
  "EDF: Insert Review Comment" from the command palette (Ctrl+Shift+P), then a
  quick-pick list appears showing all `##` and `###` headings extracted from the
  document, each annotated with its line number.
- Given the quick-pick list is open, when the reviewer types in the filter input,
  then the heading list filters in real-time to matching entries (case-insensitive
  substring match).
- Given the reviewer selects a heading from the quick-pick and presses Enter, then a
  `> **[Review]:** ` template followed by a space is inserted on a new line
  immediately after the selected heading's line in the source editor.
- Given the template is inserted, when the operation completes, then the source
  editor gains focus with the cursor positioned at the character immediately after
  the inserted `> **[Review]:** ` text, ready for typing.
- Given the quick-pick is open, when the reviewer presses Escape, then the
  quick-pick dismisses and no changes are made to the document.
- Given the document has no `##` or `###` headings, when the command is invoked,
  then a VSCode information message "No section headings found in this document" is
  shown.
- Given the document being previewed is not an LLD (no Part A / Part B structure),
  when the command is invoked, then the quick-pick still shows all `##`/`###`
  headings — the command works for any markdown document with headings.
- Given a heading already has one or more `[Review]` markers directly beneath it,
  when a new review comment is inserted, then the new template is inserted after the
  existing markers, preserving their order.

### Visual Reference

- [Review Comment Insertion wireframe](../design/v1/vis-review-comment-insertion.html) — quick-pick open and inserted states

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

**Acceptance Criteria:**

- Given a developer runs `/lld`, when Step 2 executes, then the skill follows
  documented rules for diagram type selection: state diagrams for FE state management
  features, ER diagrams for new/changed data entities, flowcharts for branching
  business logic — each gated by a concrete "When required" condition.
- Given a diagram type is selected, when Step 2 executes, then the skill applies the
  `classDef` palette (error, auth, external, new) from `lld/template.md` to all
  participants matching those roles.
- Given a diagram participant is identified as existing code, when Step 2 executes,
  then the skill generates a navigability link appropriate to the diagram type — a
  `link` directive on sequence diagrams, a `click` directive on flowchart /
  classDiagram / stateDiagram — with the workspace-relative source path.
- Given a diagram participant is identified as a new component, when Step 2 executes,
  then the skill generates a navigability link appropriate to the diagram type — a
  `link` directive on sequence diagrams, a `click` directive on flowchart /
  classDiagram / stateDiagram — with a `#LLD-` anchor matching the Part B anchor ID
  (derived from the component name, lower-kebab-case).
- Given enforcement boundaries are identified (authZ, validation, external calls,
  error propagation), when Step 2 executes, then the skill places `Note` annotations
  at the corresponding interaction points with the enforcement mechanism stated.
- Given the generation rules exist in SKILL.md, when the rules are reviewed against
  the template (`lld/template.md`), then every concern has at least one worked example
  in the skill: diagram type selection (example with gate condition), `classDef`
  application (example with colour assignment), navigability-link generation (example
  with a workspace-relative path and a `#LLD-` path, using `link` on sequence diagrams
  and `click` on flowchart / classDiagram / stateDiagram), and `Note` annotation
  placement (example with enforcement mechanism text).
- Given the template (`lld/template.md`) is updated, when the SKILL.md generation
  rules are reviewed, then every template feature has a corresponding generation rule
  in the skill (co-versioning per Design Principle 6).

**Notes:** The SKILL.md rules must reference the template as the single source of
truth for the palette hex values, diagram syntax, and annotation format. The skill
must not duplicate template content — it references it.

---

<a id="REQ-skill-instructions-quality-gates-self-critique-checklist-diagram-navigability"></a>

### Story 4.2: Self-critique checklist item for diagram navigability

**As a** Plugin Maintainer,
**I want to** add a diagram navigability check to the `/lld` Step 2.5 self-critique
checklist (every participant has a navigability link — `link` on sequence diagrams,
`click` on flowchart / classDiagram / stateDiagram, none on erDiagram; enforcement
points are annotated; the palette is applied; workspace-relative paths use valid paths),
**so that** every LLD author catches navigability gaps during self-review, before the
document reaches a human reviewer.

**Acceptance Criteria:**

- Given an LLD is generated by `/lld`, when Step 2.5 (self-critique) executes, then
  a "Diagram navigability" check verifies: every diagram participant has a
  navigability link appropriate to its diagram type (`link` on sequence diagrams,
  `click` on flowchart / classDiagram / stateDiagram; erDiagram participants are
  exempt) — no dead labels.
- Given the self-critique runs, when enforcement points are evaluated, then the check
  verifies: every interaction crossing a trust boundary (authZ, validation, external
  service, error propagation) has a `Note` annotation stating the enforcement
  mechanism.
- Given the self-critique runs, when the `classDef` palette is evaluated, then the
  check verifies: `classDef` blocks are defined inside the first diagram of each type
  that uses them (never as a standalone block, which is invalid Mermaid) and are
  applied consistently — no participant that matches a defined role uses default
  styling.
- Given the self-critique runs, when navigability paths are evaluated, then the check
  verifies: each workspace-relative path references a file that exists in the workspace
  (resolvable relative to the workspace root).
- Given a navigability check fails, when reported to the author, then the failure
  message identifies the specific participant, interaction, or path that needs
  fixing — not a generic "diagram could be improved."
- Given the checklist item exists, when an LLD author runs `/lld` and receives the
  self-critique output, then navigability issues are surfaced at the same prominence
  level as other checklist items (security, error paths, reused helpers).

**Notes:** The checklist item must be written so that an automated agent (the `/lld`
skill itself) can execute the checks. Prefer mechanical checks (grep for `click`,
verify path existence) over judgment calls. The checklist item in SKILL.md must
match the template conventions defined in Epic 1.

---

## Cross-Cutting Concerns

### Security

- **Path traversal prevention (owned by Stories 2.1, 2.2):** The navigability-path
  handler must validate that resolved file paths are within the workspace root. A
  `../../../etc/passwd` navigability link must not resolve to a file outside the
  workspace. Implemented by resolving the path against
  `vscode.workspace.workspaceFolders[0].uri` and verifying the resulting URI's `fsPath`
  starts with the workspace root `fsPath`.
- **No arbitrary code execution (owned by Stories 2.1, 2.2):** Hover tooltip content
  is extracted from source files via `vscode.workspace.fs.readFile`, not by executing
  the file. The extension must not evaluate, `import()`, or otherwise interpret file
  contents beyond reading them as UTF-8 text.
- **Extension permissions (owned by Stories 2.1, 2.2, 3.1):** The extension's
  `package.json` declares only the minimum capabilities: `workspace.fs` read and
  `window.showTextDocument`. No `activationEvents` that grant unnecessary access. No
  network access (`"extensionKind": "workspace"`), no filesystem write, no process
  execution (`"scripts"` in package.json must be empty aside from build).

### Performance

- **Hover tooltip latency (owned by Story 2.1):** The first 40 lines of a source
  file must appear in the hover tooltip within 200ms of the hover event (excluding
  the 150ms debounce). File reading is via `vscode.workspace.fs.readFile` — a local
  workspace FS read, not a network call.
- **File open latency (owned by Story 2.2):** Click-to-open must issue
  `showTextDocument` within 100ms of the click event. The editor's own file-open
  animation is outside the extension's control and not measured.
- **Preview load overhead (owned by Stories 2.1, 2.2, 2.3, 3.1):** The extension's
  markdown preview scripts (`media/preview.js`) must not measurably increase preview
  render time. Script injection is under 5 KB of JavaScript (minified). The script
  uses a `MutationObserver` for late-rendered SVGs; the observer callback must
  complete in under 1ms per invocation.

### Observability

- **Extension errors (owned by Stories 2.1, 2.2, 3.1):** Every failed navigability-path
  resolution (file not found, path outside workspace, malformed URI) produces a log
  entry in the VSCode output channel `EDF Review` with the raw URI and the failure
  reason.
- **Preview script errors (owned by Stories 2.1, 2.2):** JavaScript errors in
  `media/preview.js` are caught and relayed to the extension host via
  `postMessage({ command: 'logError', ... })` for logging to the `EDF Review` output
  channel. Unhandled errors must not crash the preview webview.

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
- **Extension marketplace publishing** — V1 loads the extension via VSCode's
  Extension Development Host for development and testing. `.vsix` packaging,
  marketplace publishing, and consumer-facing installation instructions are deferred
  to a future version.
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

## Next steps

1. Run `edf:kickoff docs/requirements/v1-requirements.md` to produce HLD, ADRs,
   and implementation plan.
2. The V2 / Future section above is input for the next discovery cycle — Wave 2
   features (F10, F12) and Wave 3+ enhancements should be reconsidered after V1
   ships.

---

## Open Questions

| # | Question | Context | Options | Impact |
|---|----------|---------|---------|--------|
| 1 | Should F11 (graceful degradation) be verified against specific GitHub markdown renderer versions, or is "harmless dead link" behaviour sufficient as a general requirement? | The discovery doc states unrecognised URL scheme → cursor changes, no navigation, no error. GitHub's Mermaid renderer may evolve independently. | (a) General requirement: link must not cause errors or navigation in any renderer; (b) Specific: test against GitHub, GitLab, and Bitbucket renderers | If GitHub changes its Mermaid link handling, Story 2.4's ACs may need updating. Currently, all major renderers treat unknown URL schemes as inert in `<a>` tags. Story 2.4 ACs default to option (a) with verification against GitHub and GitLab. |
| 2 | What is the exact mechanism for the preview→extension communication channel for hover tooltips? | Discovery references `markdown.previewScripts` + `onDidReceivePreviewMessage` with "panel reference for reply." The exact API surface should be validated during implementation. | (a) Use `postMessage` from preview script → extension `onDidReceivePreviewMessage`; (b) Use a custom `vscode-resource` URI scheme | The `postMessage` approach is the standard VSCode extension pattern and is the assumed mechanism in Stories 2.1/2.2. An implementation spike should confirm the API works for hover events specifically. |
| 3 | ~~Should the `classDef` palette colours be chosen now or deferred to implementation?~~ **Resolved.** The palette hex values are already defined in `lld/template.md`: error `#f7d6d6`, auth `#f7eed6`, external `#d6e8f7`, new `#d4f0d4`. The glossary and Story 1.2 reference these as the canonical source of truth. |
| 4 | Does F13 (quick-pick → insert `[Review]`) need the section headings parsed from the markdown AST, or is a regex-based extraction of `##`/`###` headings sufficient? | The discovery says "using the LLD's own section structure as the navigation anchor." Parsing accuracy affects robustness. | (a) Use a simple regex for `##`/`###` headings; (b) Parse the markdown AST with a library | Regex is simpler and sufficient for the LLD's predictable heading structure. Story 3.1 defaults to regex extraction. An AST parser adds dependency weight for marginal gain given the LLD's constrained heading format. |
