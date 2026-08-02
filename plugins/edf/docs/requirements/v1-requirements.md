# Review-Focused LLD Diagram Improvements — V1 Requirements

## Document Control

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Status | Final |
| Author | LS / Claude |
| Created | 2026-08-01 |
| Last updated | 2026-08-01 |

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-08-01 | LS / Claude | Initial draft — epics, stories, roles |
| 0.2 | 2026-08-01 | LS / Claude | Acceptance criteria for all 11 stories; closed stale open questions; added security ACs to Stories 2.1/2.2; added extension packaging deferral |
| 0.3 | 2026-08-01 | LS / Claude | Testability fixes: tightened 3 vague ACs (Story 1.3 AC5, Story 2.4 AC5, Story 4.1 AC6) |
| 0.4 | 2026-08-01 | LS / Claude | Review fixes: corrected visual reference paths; aligned #LLD- anchor format with ADR-0026; resolved AC1/AC4 contradiction in Story 1.2; removed cross-epic AC dependency on Story 4.2 |
| 1.0 | 2026-08-01 | LS / Claude | Finalised — Gate 2 approved |

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
kickoff → feature). Uncommitted changes to `lld/template.md`, `lld/SKILL.md`, and the
`extensions/edf-review/` scaffold exist as work-in-progress artefacts. These stories
define the complete, verified deliverable — where work already exists, the story scope
is to complete, verify, and harden that work against the acceptance criteria below.

## Glossary

> **[Review]:** The `edf://` protocol entry must be removed. Verified against Mermaid
> 11.12.2 (the version VS Code 1.121 bundles): the built-in renderer never sets
> `securityLevel`, so Mermaid defaults to `strict`, whose sanitizer strips the `href`
> for any unrecognised scheme — `edf://` included, in every diagram type. Workspace-relative
> paths, `#fragment`, and `https:` survive. Replace the entry with a **workspace-relative
> path** convention (`click AuthHelper href "src/lib/auth/helper.ts" _self`). See the
> rejection note on ADR-0038 for the full evidence.

> **[Review]:** The `click` directive entry needs a caveat: Mermaid supports `click`
> only in `flowchart` and `classDiagram`. In `sequenceDiagram` it is a **fatal parse
> error** (the diagram does not render at all); `erDiagram` ignores it silently; and
> `stateDiagram-v2` parse-errors when a `_self` target is supplied.

| Term | Definition |
|------|-----------|
| **LLD Part A** | The first half of an LLD document — behavioural diagrams (sequence, state, ER, flowchart) and an invariants table. The primary review surface. |
| **LLD Part B** | The second half of an LLD document — internal decomposition, function signatures, data shapes, and task breakdown for each component. |
| **`click` directive** | A Mermaid syntax element (`click ParticipantId "url"`) that makes a diagram node clickable. Used to link participants to source files or Part B anchors. |
| **`edf://` protocol** | A custom URL scheme (`edf://path/to/file.ts`) recognised by the EDF Review VSCode extension. Resolves to a workspace-relative file path. |
| **`classDef` palette** | A set of Mermaid `classDef` declarations defining colour-coded styles for diagram participants. The canonical palette is defined in `lld/template.md`: error (`#f7d6d6`), auth (`#f7eed6`), external (`#d6e8f7`), new (`#d4f0d4`). |
| **Enforcement point** | A location in a sequence diagram where a cross-cutting concern (authZ, validation, SSRF boundary, error propagation) is enforced. Marked with a `Note` annotation. |
| **`[Review]` marker** | A blockquote convention (`> **[Review]:** <feedback>`) used to collect inline review feedback in EDF documents. Already established in `/requirements` and `/discovery`. |
| **Markdown preview** | VSCode's built-in rendered-markdown view (Ctrl+Shift+V). The extension augments this with `edf://` link handling. |
| **Graceful degradation** | The principle that `edf://` links must render as inert, harmless links in renderers that lack the extension (GitHub, other editors). No errors, no broken UX. |

## Design Principles / Constraints

> **[Review]:** Principle 3 ("Graceful degradation by default") needs reframing. With
> workspace-relative paths instead of `edf://`, links are no longer inert in GitHub —
> they resolve to the actual file in the repository. The principle should be restated as
> *renderer-native navigation*: links must work without any extension, and work better
> where one exists. This is a stronger outcome than the original principle asked for.

> **[Review]:** Principle 7 ("Extension distribution — Dev Host only") is in tension with
> the value proposition: a tool whose premise is "don't break your review flow" would
> require launching a second VS Code in debug mode to use. With Stories 2.1/2.2 moving to
> V2, this principle now applies only to Story 3.1. Either commit to `.vsix` packaging or
> reconsider whether the story ships in V1.

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

> **[Review]:** `classDiagram` is already present in the working-tree template and the
> HLD (C1) treats it as in-scope, but this story names only three types and the
> "What We Are NOT Building" section explicitly excludes other types. Resolve the
> contradiction — either add `classDiagram` as a fourth type here (with a "When required"
> gate and an AC) and amend the exclusion, or remove it from the template.

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
- Given a `classDef` block is present at the top of Part A, when a new diagram type
  is added to the document, then the existing palette classes are applied to
  participants matching those roles — no duplicate or divergent colour definitions.
- Given the palette is applied, when the document is viewed in GitHub's Mermaid
  renderer, then all four colours render distinctly and are distinguishable from each
  other.
- Given a diagram participant does not match any of the four defined roles, when
  rendered, then it uses the Mermaid default styling (no palette class applied).
- Given the `classDef` block exists, when a maintainer updates a colour value, then
  the change is made in exactly one place (the template's palette block) and
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

### Story 1.4: `click` directives on every diagram participant

> **[Review]:** This story needs the largest rework. (a) Replace `edf://` with
> workspace-relative paths throughout — the custom scheme is stripped by Mermaid's strict
> sanitizer. (b) AC4's premise is false: no `<a>` element is generated for sequence-diagram
> participants, so it cannot render "as an inert `<a>` with `target=_self`". (c) `click`
> cannot be applied to sequence diagrams at all — it is a fatal parse error — so this
> story must specify a different mechanism for the primary diagram type (e.g. a
> participant→path mapping block the preview can read), or explicitly scope sequence-diagram
> participants out of the navigability requirement. (d) AC2's example uses a `v11` epic id
> borrowed from another project.

**As an** LLD Reviewer,
**I want to** click on any diagram participant and navigate to its source file (for
existing code via `edf://`) or its Part B spec (for new components via `#LLD-` anchors),
**so that** I can verify implementation against design without leaving the markdown
preview or manually grepping the codebase.

**Acceptance Criteria:**

- Given a diagram participant representing existing code, when the diagram is
  generated, then it carries a `click` directive with an `edf://` URL resolving to
  the workspace-relative source file path (e.g., `click AuthMiddleware "edf://src/lib/auth/middleware.ts"`).
- Given a diagram participant representing a new component, when the diagram is
  generated, then it carries a `click` directive with a `#LLD-` anchor referencing the
  Part B section's stable anchor ID as defined by ADR-0026 (e.g.,
  `click DeliveryService "#LLD-v11-e11-1-delivery-service"`).
- Given a diagram is fully generated, when the diagram source is inspected, then no
  participant is a "dead label" — every participant has a `click` directive resolving
  to either an `edf://` path or a `#LLD-` anchor.
- Given an `edf://` link is rendered in a Mermaid diagram, when viewed in a renderer
  without the EDF extension (GitHub, GitLab), then the link renders as an inert `<a>`
  element with `target="_self"` — cursor changes on hover but no navigation or error
  occurs on click.
- Given an `edf://` path references a file, when the path is constructed, then it
  uses a workspace-relative path (no leading slash, no `..` segments) suitable for
  resolution by `vscode.Uri.joinPath`.
- Given a Part B section exists with a stable anchor ID, when a `#LLD-` link targets
  it, then the anchor ID follows the ADR-0026 format (`LLD-<epic-id>-<section-slug>`)
  and the `click` directive uses the full anchor ID as its fragment target.

**Notes:** The `click` directive is the bridge between Epic 1 (template) and Epic 2
(extension). The extension intercepts `edf://` links in the preview; `#LLD-` anchors
work via native browser scrolling. The template must document both link types with
examples.

---

## Epic 2: VSCode Extension — Diagram Navigation [Priority: High]

> **[Review]:** This epic dissolves. Stories 2.1 and 2.2 move to V2/Future (see their
> individual markers). Stories 2.3 and 2.4 are no longer extension work — both are
> properties of the template's link format — and should fold into Epic 1. If nothing
> remains, delete the epic and renumber; if 2.3/2.4 stay grouped, retitle it to something
> like "Link Behaviour & Verification" and drop the extension framing.

The extension that makes `edf://` links functional in VSCode's markdown preview. Hover
to peek at source, click to open in an adjacent column, and navigate to Part B specs via
`#LLD-` anchors. Depends on Epic 1 for diagrams to carry `click` directives. Includes
graceful degradation so links are harmless when the extension is absent.

<a id="REQ-vscode-extension-diagram-navigation-hover-tooltip-source-preview"></a>

### Story 2.1: Hover tooltip showing source file preview

> **[Review]:** Move to V2/Future. Two reasons. (a) It depends on
> `vscode.window.onDidReceivePreviewMessage`, which could not be found in the public VS
> Code API — the claim traces to one unverified line in the discovery doc and remains
> unvalidated. (b) The feature as specified does not solve its own pain point: the
> persona needs *a named function's signature*, but "first 40 lines of the file" yields
> imports and headers. Solving it properly needs symbol resolution, which the discovery
> doc's Is-Not column rules out. Revisit after a spike answers (a).

**As an** LLD Reviewer,
**I want to** hover over an `edf://` link in the markdown preview and see the first ~40
lines of the referenced source file in a tooltip,
**so that** I can verify the real function signature matches the design's assumptions
without opening the file or losing my place in the diagram.

**Acceptance Criteria:**

- Given an LLD markdown preview is open with rendered Mermaid diagrams containing
  `edf://` links, when the reviewer hovers over an `edf://` link for 150ms, then a
  tooltip appears showing the first 40 lines of the referenced source file.
- Given a tooltip is displayed, when the reviewer moves the mouse away from the link,
  then the tooltip dismisses within 200ms.
- Given an `edf://` link points to a file that does not exist in the workspace, when
  the reviewer hovers, then the tooltip shows "File not found: <path>" and no file
  read is attempted.
- Given an `edf://` link contains a path with `..` segments that would resolve
  outside the workspace root, when the extension resolves the path, then the tooltip
  shows "Path outside workspace: <path>" and no file content is read.
- Given an `edf://` link contains a malformed or empty path, when the reviewer
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

> **[Review]:** Move to V2/Future alongside Story 2.1. Before rebuilding it there, spike
> whether VS Code's markdown preview already opens workspace-relative links clicked inside
> a Mermaid SVG — its preview handles relative file links natively. If it does, this story
> is delivered for free by Epic 1 and never needs an extension.

**As an** LLD Reviewer,
**I want to** click an `edf://` link and have the source file open in the adjacent VSCode
column while the markdown preview stays visible,
**so that** I can inspect the full implementation without tab-switching or losing
orientation in the design document.

**Acceptance Criteria:**

- Given a reviewer hovers over an `edf://` link in the markdown preview, when they
  click the link, then the referenced source file opens in the adjacent VSCode column
  using `vscode.window.showTextDocument(uri, { viewColumn: ViewColumn.Beside })`.
- Given a source file opens in the adjacent column, when the operation completes,
  then the markdown preview remains visible in its original column — it is not closed
  or replaced.
- Given an `edf://` link points to a file that does not exist, when clicked, then a
  VSCode error message "File not found: <path>" is shown and no editor tab is opened.
- Given an `edf://` link path resolves outside the workspace root (contains `..`
  segments escaping the root), when clicked, then the file is not opened, an error is
  logged to the "EDF Review" output channel with the raw URI and failure reason, and
  a VSCode information message "Cannot open file outside workspace" is shown.
- Given a click event occurs on an `edf://` link, when measured, then
  `showTextDocument` is issued within 100ms of the click event.
- Given the extension opens a file, when the file is already open in another tab,
  then the existing tab is focused (the same file is not opened twice).

### Visual Reference

- [Markdown Preview Navigation wireframe](../design/v1/vis-markdown-preview-navigation.html) — click state (source file in adjacent column, preview stays)

---

<a id="REQ-vscode-extension-diagram-navigation-lld-anchor-navigation-part-b"></a>

### Story 2.3: `#LLD-` anchor navigation to Part B specs

> **[Review]:** Fold into Epic 1 — this is no longer extension work. Verified: `#LLD-`
> fragments survive Mermaid's strict sanitizer and work natively in `flowchart` and
> `classDiagram`, no extension required. Drop the extension-fallback framing. Two fixes
> needed: AC1's example (`#LLD-delivery-service`) omits the epic-id that AC4 requires —
> align both on the ADR-0026 format. And because `click` is a parse error in
> `sequenceDiagram`, new components shown only in a sequence diagram have no working
> anchor path at all; state how they are reached, or require them to appear in a
> `flowchart`/`classDiagram`.

**As an** LLD Reviewer,
**I want to** click on a diagram participant marked as a new component (teal outline) and
have the preview scroll to its Part B internal decomposition section,
**so that** I can read the component's spec — function signatures, data shapes, and task
breakdown — in a single click instead of scroll-hunting through the document.

**Acceptance Criteria:**

- Given a diagram participant has a `click` directive with a `#LLD-` anchor (e.g.,
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

<a id="REQ-vscode-extension-diagram-navigation-graceful-degradation-edf-links"></a>

### Story 2.4: Graceful degradation of `edf://` links in external renderers

> **[Review]:** Fold into Epic 1 as its verification story, and rewrite — the outcome has
> changed qualitatively. With workspace-relative paths, GitHub resolves the link to the
> real file in the repo, so this is no longer "degradation" but working navigation in a
> second renderer. Retitle accordingly. ACs 1 and 4 rest on `<a>` elements that are never
> generated for sequence diagrams; replace them with verification that each diagram type
> renders and its links resolve, in GitHub and VS Code. This story is what makes Epic 1
> trustworthy — do not defer it.

**As a** Plugin Maintainer,
**I want to** ensure that `edf://` links render as inert, harmless links when the
markdown is viewed in GitHub, GitLab, or other non-VSCode renderers,
**so that** external reviewers and contributors never encounter broken links, error
states, or confusing UI when reading LLDs outside VSCode.

**Acceptance Criteria:**

- Given an LLD is viewed in GitHub's markdown renderer, when `edf://` links appear in
  Mermaid diagrams, then they render as standard `<a>` elements with `cursor: pointer`
  but produce no navigation, no error, and no console warning on click (unknown URL
  scheme is silently ignored by browsers).
- Given an LLD is viewed in GitLab's markdown renderer, when `edf://` links are
  rendered, then the links are inert — no broken-link styling, no error page on
  click, no JavaScript exceptions in the browser console.
- Given an LLD is viewed as raw markdown in a text editor without preview, when the
  markdown source is read, then `edf://` URLs are clearly identifiable as
  workspace-relative file references (human-readable paths like
  `edf://src/lib/auth/middleware.ts`).
- Given the Mermaid `click` directive uses `target="_self"`, when the `<a>` element
  is generated by Mermaid, then clicking the link in any browser attempts navigation
  in the same frame (where the unknown scheme produces no effect).
- Given the extension is not installed, when `edf://` links are tested in a
  fresh browser profile against the current versions of GitHub and GitLab, then
  no navigation, error, or console warning occurs on click — the link is inert.

**Notes:** This is primarily a verification and documentation story. The template
already specifies `_self` targets and the "harmless dead link" convention. The
extension does not need to handle the degradation case — it is only active in VSCode.
The story deliverable is a verification report confirming degradation across GitHub,
GitLab, and at least one other renderer, plus any template adjustments needed.

---

## Epic 3: VSCode Extension — Review Feedback [Priority: Medium]

Closes the preview→source round-trip for adding review comments. When a reviewer
identifies an issue in the diagram preview, they can insert a `[Review]` marker under
the relevant LLD section heading without hunting through the source editor. Depends on
Epic 2 for the extension infrastructure (commands, activation, markdown preview
integration).

<a id="REQ-vscode-extension-review-feedback-quick-pick-insert-review-comment"></a>

### Story 3.1: Quick-pick section → insert `[Review]` comment

> **[Review]:** Functional gap: AC1 assumes the command is invoked while the markdown
> preview is focused, but in that state `vscode.window.activeTextEditor` is `undefined` —
> the webview holds focus. No AC specifies how the preview is resolved back to its source
> document. Add one. This is now the only story in V1 requiring extension code, so the
> gap is blocking.

> **[Review]:** No story covers how the extension is tested or delivered. Add ACs (or a
> sibling story) for the TypeScript test framework and for `.vsix` packaging — per the
> Principle 7 marker, an unpackaged extension cannot deliver this story's value.

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

> **[Review]:** Three fixes. (a) AC4 says the `#LLD-` anchor is "derived from the
> component name, lower-kebab-case", dropping the `<epic-id>` that ADR-0026 and Story 1.4
> AC6 both require — AC4 is the wrong one. (b) AC1/AC3 need updating for
> workspace-relative paths and for the per-diagram-type `click` support matrix (fatal
> parse error in `sequenceDiagram`; ignored in `erDiagram`; no `_self` target in
> `stateDiagram-v2`). (c) Add `classDiagram` if Story 1.1's scope contradiction resolves
> in its favour.

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
  then the skill generates a `click` directive with an `edf://` URL resolving to the
  workspace-relative source path.
- Given a diagram participant is identified as a new component, when Step 2 executes,
  then the skill generates a `click` directive with a `#LLD-` anchor matching the
  Part B anchor ID (derived from the component name, lower-kebab-case).
- Given enforcement boundaries are identified (authZ, validation, external calls,
  error propagation), when Step 2 executes, then the skill places `Note` annotations
  at the corresponding interaction points with the enforcement mechanism stated.
- Given the generation rules exist in SKILL.md, when the rules are reviewed against
  the template (`lld/template.md`), then every concern has at least one worked example
  in the skill: diagram type selection (example with gate condition), `classDef`
  application (example with colour assignment), `click` generation (example with
  `edf://` and `#LLD-` paths), and `Note` annotation placement (example with
  enforcement mechanism text).
- Given the template (`lld/template.md`) is updated, when the SKILL.md generation
  rules are reviewed, then every template feature has a corresponding generation rule
  in the skill (co-versioning per Design Principle 6).

**Notes:** The SKILL.md rules must reference the template as the single source of
truth for the palette hex values, diagram syntax, and annotation format. The skill
must not duplicate template content — it references it.

---

<a id="REQ-skill-instructions-quality-gates-self-critique-checklist-diagram-navigability"></a>

### Story 4.2: Self-critique checklist item for diagram navigability

> **[Review]:** AC1 ("every diagram participant has a `click` directive") is now unsafe —
> on a sequence diagram, a `click` directive is a fatal parse error, so an LLD that
> satisfies this check would fail to render entirely. Rewrite the check per diagram type,
> and make it verify whatever mechanism Story 1.4 settles on for sequence participants.
> AC4 must also change: it checks that `edf://` paths resolve, which no longer applies.
> Add a check that every diagram actually parses.

**As a** Plugin Maintainer,
**I want to** add a diagram navigability check to the `/lld` Step 2.5 self-critique
checklist (every participant has a `click`, enforcement points are annotated, palette
is applied, `edf://` links use valid paths),
**so that** every LLD author catches navigability gaps during self-review, before the
document reaches a human reviewer.

**Acceptance Criteria:**

- Given an LLD is generated by `/lld`, when Step 2.5 (self-critique) executes, then
  a "Diagram navigability" check verifies: every diagram participant has a `click`
  directive — no dead labels.
- Given the self-critique runs, when enforcement points are evaluated, then the check
  verifies: every interaction crossing a trust boundary (authZ, validation, external
  service, error propagation) has a `Note` annotation stating the enforcement
  mechanism.
- Given the self-critique runs, when the `classDef` palette is evaluated, then the
  check verifies: the palette block is present at the top of Part A and is applied
  consistently — no participant that matches a defined role uses default styling.
- Given the self-critique runs, when `edf://` paths are evaluated, then the check
  verifies: each `edf://` path references a file that exists in the workspace
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

> **[Review]:** The "Extension permissions" bullet rests on a false model of VS Code's
> security architecture and must be rewritten. `extensionKind: "workspace"` controls
> *where* an extension runs in remote scenarios — it does not deny network access.
> `activationEvents` control *when* activation happens, not what is accessible. `"scripts"`
> is npm tooling, unrelated to runtime process execution. VS Code extensions run with full
> Node privileges and there is no manifest-level permission system. State the real
> guarantee: the extension performs only these operations, enforced by code review.

> **[Review]:** The path-traversal and no-code-execution bullets are owned by Stories 2.1
> and 2.2, both moving to V2. Move them with those stories, and keep only what Story 3.1
> actually needs.

- **Path traversal prevention (owned by Stories 2.1, 2.2):** The `edf://` protocol
  handler must validate that resolved file paths are within the workspace root. An
  `edf://../../../etc/passwd` link must not resolve to a file outside the workspace.
  Implemented by resolving the `edf://` path against `vscode.workspace.workspaceFolders[0].uri`
  and verifying the resulting URI's `fsPath` starts with the workspace root `fsPath`.
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

> **[Review]:** All three bullets are owned by Stories 2.1/2.2/2.3/3.1 — the first three
> move to V2 or fold into Epic 1, leaving nothing to measure in V1. Move them with their
> stories. If the MutationObserver budget returns in V2, note that "under 1ms per
> invocation" is already violated by the scaffold's unthrottled full-document
> `querySelectorAll` on every mutation.

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

> **[Review]:** Both bullets are scoped to the preview script and `edf://` resolution,
> which leave V1 with Stories 2.1/2.2. Reduce to whatever Story 3.1 needs — if anything.

- **Extension errors (owned by Stories 2.1, 2.2, 3.1):** Every failed `edf://`
  resolution (file not found, path outside workspace, malformed URI) produces a log
  entry in the VSCode output channel `EDF Review` with the raw URI and the failure
  reason.
- **Preview script errors (owned by Stories 2.1, 2.2):** JavaScript errors in
  `media/preview.js` are caught and relayed to the extension host via
  `postMessage({ command: 'logError', ... })` for logging to the `EDF Review` output
  channel. Unhandled errors must not crash the preview webview.

---

## What We Are NOT Building

> **[Review]:** The first bullet excludes diagram types beyond the three named in Story
> 1.1, which contradicts `classDiagram` being present in the template and in-scope in the
> HLD. Resolve together with the Story 1.1 marker.

> **[Review]:** Add hover-to-peek and click-to-open as explicit V1 exclusions, pointing at
> their V2/Future entries, so the deferral is visible here and not only in the story
> bodies.

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

> **[Review]:** Add Stories 2.1 (hover tooltip) and 2.2 (click-to-open) here, each with
> the spike question that would reopen it: does `onDidReceivePreviewMessage` exist, and
> does VS Code's preview already open relative links from inside a Mermaid SVG?

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

> **[Review]:** Three of the four are stale and should be closed using the strikethrough
> convention already applied to OQ3. **OQ1** — answered: with relative paths, links
> resolve in GitHub rather than degrading; verification folds into the rewritten Story 2.4.
> **OQ2** — the postMessage mechanism was never validated and the API appears not to
> exist; the question moves to V2 with Stories 2.1/2.2 rather than staying open here.
> **OQ4** — regex extraction was already chosen and is reflected in Story 3.1's ACs.

| # | Question | Context | Options | Impact |
|---|----------|---------|---------|--------|
| 1 | Should F11 (graceful degradation) be verified against specific GitHub markdown renderer versions, or is "harmless dead link" behaviour sufficient as a general requirement? | The discovery doc states `_self` target + unrecognised URL scheme → cursor changes, no navigation, no error. GitHub's Mermaid renderer may evolve independently. | (a) General requirement: link must not cause errors or navigation in any renderer; (b) Specific: test against GitHub, GitLab, and Bitbucket renderers | If GitHub changes its Mermaid link handling, Story 2.4's ACs may need updating. Currently, all major renderers treat unknown URL schemes as inert in `<a>` tags. Story 2.4 ACs default to option (a) with verification against GitHub and GitLab. |
| 2 | What is the exact mechanism for the preview→extension communication channel for hover tooltips? | Discovery references `markdown.previewScripts` + `onDidReceivePreviewMessage` with "panel reference for reply." The exact API surface should be validated during implementation. | (a) Use `postMessage` from preview script → extension `onDidReceivePreviewMessage`; (b) Use a custom `vscode-resource` URI scheme | The `postMessage` approach is the standard VSCode extension pattern and is the assumed mechanism in Stories 2.1/2.2. An implementation spike should confirm the API works for hover events specifically. |
| 3 | ~~Should the `classDef` palette colours be chosen now or deferred to implementation?~~ **Resolved.** The palette hex values are already defined in `lld/template.md`: error `#f7d6d6`, auth `#f7eed6`, external `#d6e8f7`, new `#d4f0d4`. The glossary and Story 1.2 reference these as the canonical source of truth. |
| 4 | Does F13 (quick-pick → insert `[Review]`) need the section headings parsed from the markdown AST, or is a regex-based extraction of `##`/`###` headings sufficient? | The discovery says "using the LLD's own section structure as the navigation anchor." Parsing accuracy affects robustness. | (a) Use a simple regex for `##`/`###` headings; (b) Parse the markdown AST with a library | Regex is simpler and sufficient for the LLD's predictable heading structure. Story 3.1 defaults to regex extraction. An AST parser adds dependency weight for marginal gain given the LLD's constrained heading format. |
