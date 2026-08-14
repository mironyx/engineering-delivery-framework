# Review-Focused LLD Diagram Improvements — V1 Requirements

## Document Control

| Field | Value |
|-------|-------|
| Version | 1.2 |
| Status | Draft — Complete |
| Author | LS / Claude |
| Created | 2026-08-01 |
| Last updated | 2026-08-13 |

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-08-01 | LS / Claude | Initial draft — epics, stories, roles |
| 0.2 | 2026-08-01 | LS / Claude | Acceptance criteria for all 11 stories; closed stale open questions; added security ACs to Stories 2.1/2.2; added extension packaging deferral |
| 0.3 | 2026-08-01 | LS / Claude | Testability fixes: tightened 3 vague ACs (Story 1.3 AC5, Story 2.4 AC5, Story 4.1 AC6) |
| 0.4 | 2026-08-01 | LS / Claude | Review fixes: corrected visual reference paths; aligned #LLD- anchor format with ADR-0026; resolved AC1/AC4 contradiction in Story 1.2; removed cross-epic AC dependency on Story 4.2 |
| 1.0 | 2026-08-01 | LS / Claude | Finalised — Gate 2 approved |
| 1.2 | 2026-08-13 | LS / Claude | `/kickoff` Gate 1 fix: struck GitLab from Story 1.3 AC5, which contradicted Story 1.6's Notes ("GitLab is not separately verified in V1"). As written, AC5 was an acceptance criterion no component owned and no verification exercised — it would have passed by assumption, the same failure mode as the `edf://` design. V1 now claims only what Story 1.6 measures. |
| 1.1 | 2026-08-02 | LS / Claude | Review cycle following ADR-0038's rejection: retired `edf://` from the requirements in favour of workspace-relative paths (still outstanding as real, unfinished work in `template.md`/`SKILL.md` — not yet migrated); dissolved Epic 2 (hover tooltip / click-to-open moved to V2/Future pending a communication-channel spike; anchor navigation and link-resolution verification folded into Epic 1 as Stories 1.5/1.6); added `classDiagram` as a fourth conditional diagram type (Story 1.1); resolved Design Principle 7 to local `.vsix` packaging and added Story 2.2 for the test/packaging work; fixed the `click`-support-matrix ACs across Stories 1.4, 1.5, 1.6, 3.1 (ex-4.1), 3.2 (ex-4.2), including a `stateDiagram-v2` inconsistency for new-component anchors caught by automated review; rewrote Design Principle 2 to match the current Story 2.1 and moved its stronger "preview stays open" guarantee to the deferred click-to-open story; trimmed Cross-Cutting Concerns to what the remaining V1 stories actually need; closed three stale open questions |

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
changes add diagram types (state, ER, flowchart, class), a standard colour palette,
enforcement annotations, and workspace-relative `click` directives on every participant
that supports one. A thin VSCode extension closes the review-comment loop: reviewers insert
`[Review]` markers from a command-palette quick-pick without leaving the preview.
Hover-to-peek and click-to-open source previews were drafted for V1 but moved to V2/Future
after a spike found their assumed preview↔extension communication channel does not exist in
the public VS Code API (see ADR-0038's rejection note). Workspace-relative links and
`#LLD-` anchors resolve natively in GitHub and VSCode without any extension, so the core
navigability story survives independently of that spike's outcome.

The discovery doc ([v1-discovery.md](../discovery/v1-discovery.md)) defines 14 features
across three waves. V1 delivers the Wave 1 features that remain viable after the spike —
the complete review-enabling surface minus the two extension features that need further
architecture work. Wave 2 (review convention documentation, upstream/downstream impact
assessment) and Wave 3+ (contextual test execution, bidirectional navigation) are deferred,
alongside the spike-blocked stories.

**Implementation note:** `lld/template.md` and `lld/SKILL.md` already carry the
click-support-matrix fix (which diagram types accept `click` and their per-type caveats)
as part of the standard EDF pipeline (discovery → requirements → kickoff → feature) — that
part of Stories 1.4 and 3.1 is verify-and-harden work. The `edf://` → workspace-relative
path migration is **not yet done** in either file as of this revision: both still use
`edf://` in their existing-code `click` examples. That migration is real, outstanding work
for Stories 1.4 and 3.1, not verification of something already shipped. The
`extensions/edf-review/` scaffold exists in the repository as a work-in-progress artefact
for Epic 2. Where work already exists, the story scope is to complete, verify, and harden
it against the acceptance criteria below — but do not assume everything described here is
already built.

## Glossary

| Term | Definition |
|------|-----------|
| **LLD Part A** | The first half of an LLD document — behavioural diagrams (sequence, state, ER, flowchart, class) and an invariants table. The primary review surface. |
| **LLD Part B** | The second half of an LLD document — internal decomposition, function signatures, data shapes, and task breakdown for each component. |
| **`click` directive** | A Mermaid syntax element (`click ParticipantId href "url" [_self]`) that makes a diagram node clickable. Support is not uniform: `flowchart`, `classDiagram`, and `stateDiagram-v2` support it (each with caveats — see the support matrix in `lld/template.md`); `erDiagram` parses it but generates no link; `sequenceDiagram` treats any form of it as a fatal parse error. Used to link participants to source files or Part B anchors. |
| **Workspace-relative path** | A repo-relative file path (e.g. `src/lib/auth/helper.ts`, no leading slash, no `..` segments) used as a `click` href. Survives Mermaid's strict URL sanitizer and resolves natively in both GitHub and VSCode — unlike a custom URL scheme, which the sanitizer strips regardless of diagram type. |
| **`classDef` palette** | A set of Mermaid `classDef` declarations defining colour-coded styles for diagram participants. The canonical palette is defined in `lld/template.md`: error (`#f7d6d6`), auth (`#f7eed6`), external (`#d6e8f7`), new (`#d4f0d4`). |
| **Enforcement point** | A location in a sequence diagram where a cross-cutting concern (authZ, validation, SSRF boundary, error propagation) is enforced. Marked with a `Note` annotation. |
| **`[Review]` marker** | A blockquote convention (`> **[Review]:** <feedback>`) used to collect inline review feedback in EDF documents. Already established in `/requirements` and `/discovery`. |
| **Markdown preview** | VSCode's built-in rendered-markdown view (Ctrl+Shift+V). |
| **Renderer-native navigation** | The principle that diagram links must resolve correctly using each renderer's own native behaviour (GitHub's page-internal linking and relative-file resolution, VSCode's preview scrolling) — no extension required for the baseline experience. |

## Design Principles / Constraints

1. **Diagram-first review surface** — Diagrams are the primary navigation surface for
   reviewers. Every diagram participant in a diagram type that supports `click` must
   resolve to something actionable (source file or Part B spec). No dead labels within
   that constraint — sequence-diagram participants are exempt because `click` cannot be
   emitted there at all (see the glossary entry).
2. **Non-disruptive feedback** — Inserting a `[Review]` comment (Story 2.1) must not
   close, replace, or scroll away from the markdown preview the reviewer was reading —
   only the resolved source editor gains focus for typing. The reviewer's place in the
   rendered document is preserved. (The stronger version of this principle — opening a
   *source file* beside the preview without closing it — belongs to the deferred
   click-to-open story; see its carried-forward requirements in V2/Future.)
3. **Renderer-native navigation** — Every diagram link must work without any extension —
   GitHub PR reviews, external contributors, and non-VSCode users get a working link, not
   a harmless dead one. Where an extension exists, it makes the experience richer than the
   renderer-native baseline, not different from it. This supersedes the original "graceful
   degradation" framing: with workspace-relative paths, links resolve to real files in
   GitHub rather than degrading to inert placeholders.
4. **Convention over configuration** — The `classDef` palette, diagram type selection rules,
   and annotation placement are defined once in the template and skill instructions. No
   per-project or per-team customisation in V1.
5. **Thin extension surface** — The VSCode extension does one thing in V1: quick-pick
   section selection and `[Review]` comment insertion. No code analysis, no diagram
   generation, no bidirectional sync. Complexity lives in the LLD generation, not the
   extension.
6. **Template and skill co-versioned** — Template changes (`lld/template.md`) and skill
   instruction changes (`lld/SKILL.md`) must stay in lockstep. Every template feature must
   have a corresponding generation rule in the skill.
7. **Extension distribution (V1) — local packaging** — The extension is built and packaged
   as a local `.vsix` file (`vsce package` + `code --install-extension`), so a reviewer can
   install it in their normal VSCode window without launching a separate Extension
   Development Host. Marketplace publishing (gallery listing, publisher verification,
   installation docs for external users) remains deferred to a future version. This
   resolves the V1.0 tension between Dev-Host-only distribution and Story 2.1's premise of
   not breaking the reviewer's flow — see Story 2.2's Notes for the full reasoning, and
   flag at Gate 2 if a different resolution (e.g. staying Dev-Host-only and dropping Story
   2.1 from V1 instead) is preferred.

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
standard colour palette, enforcement-point annotations, and workspace-relative `click`
directives on every participant that can carry one. Also owns navigation to Part B specs
and verification that links actually resolve in GitHub and VSCode — both are properties of
the template's link format, not of any extension, so they live here rather than in a
separate extension epic. Story 2.1 (the one remaining extension story) depends on this
epic only for the document structure it scans for headings, not for its link format.

<a id="REQ-lld-template-diagram-vocabulary-conditional-diagram-types"></a>

### Story 1.1: Conditional diagram types (state, ER, flowchart, class)

**As a** Plugin Maintainer,
**I want to** extend the LLD template with conditional support for `stateDiagram-v2`,
`erDiagram`, `flowchart TD`, and `classDiagram` diagram types, gated by "When required"
conditions,
**so that** LLD authors can express state machines, data models, module structure, and
branching logic directly in Part A instead of resorting to prose workarounds.

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
- Given an LLD for a feature that introduces new modules/classes, modifies module
  boundaries, or adds new dependencies between existing modules, when `/lld` Step 2
  evaluates the feature's characteristics, then a `classDiagram` is included showing the
  structural overview (modules, classes, or interfaces and their dependency direction).
- Given an LLD for a feature with none of the above characteristics, when `/lld`
  Step 2 evaluates, then no conditional diagram types are added — the document
  contains only the standard sequence diagram.
- Given any conditional diagram type is included, when the resulting markdown is
  rendered in GitHub's Mermaid renderer, then the diagram renders without syntax
  errors.
- Given a `classDiagram` participant's name would otherwise contain a `/` (e.g. a module
  path like `engine/scoring`), when the diagram is generated, then the template's
  display-label workaround is used (`class EngineScoring["engine/scoring"]`) instead of
  the raw path as the class identifier — a bare `/` in a class name is a Mermaid parse
  error.
- Given a conditional diagram type is included, when the template's "When required"
  gate is evaluated, then the gate condition is stated as a concrete, checkable rule
  (not a vague "if it seems useful").

**Notes:** The "When required" gates must be deterministic — the same feature
characteristics must always produce the same diagram types. The template defines
these gates; `/lld` SKILL.md Step 2 applies them. `classDiagram` was added in the v1.1
review cycle: it was already present in the committed template (`lld/template.md`) and
treated as in-scope by the HLD (C1), so the original three-type scope in v1.0 was a
contradiction, not a deliberate exclusion — see the matching fix in "What We Are NOT
Building".

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
- Given a participant plausibly matches more than one role (e.g. a new component that
  is also an external service, or an auth-boundary participant on an error path), when
  a class is assigned, then only one class applies — the roles are mutually exclusive
  by convention, and the LLD author picks the single most reviewer-relevant role for
  that participant (new/external over error/auth, since "what is this" outranks "how
  does it fail" for a first-pass reviewer).

**Notes:** The canonical hex values are defined in `lld/template.md` and are the
single source of truth. Story 3.1 ensures the skill instructions reference the
template's palette. The palette matches EDF pipeline flowchart conventions. The palette
block itself lives in a `text` fence (not a bare `mermaid` fence) since a `classDef`
block alone is not a valid diagram — it must be pasted inside one.

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
- Given a `Note` annotation exists, when the diagram is rendered in VSCode's markdown
  preview and in GitHub, then the note renders without Mermaid syntax errors and the
  note text is visible (not truncated, not hidden by `display: none`, not positioned
  outside the diagram bounds). GitLab is out of scope for V1 verification, consistent
  with Story 1.6's Notes — V1 claims only what Story 1.6 measures.
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

**As an** LLD Reviewer,
**I want to** click on any diagram participant that supports it and navigate to its
source file (for existing code) or its Part B spec (for new components via `#LLD-`
anchors),
**so that** I can verify implementation against design without leaving the markdown
preview or manually grepping the codebase.

**Acceptance Criteria:**

- Given a diagram participant representing existing code in a `flowchart`,
  `classDiagram`, or `stateDiagram-v2`, when the diagram is generated, then it carries
  a `click` directive with an href resolving to the workspace-relative source file path
  (e.g., `click AuthMiddleware href "src/lib/auth/middleware.ts" _self` in a
  `flowchart`; `stateDiagram-v2` omits the `_self` target — see AC below).
- Given a diagram participant representing a new component in a `flowchart`,
  `classDiagram`, or `stateDiagram-v2`, when the diagram is generated, then it carries
  a `click` directive with a `#LLD-` anchor referencing the Part B section's stable
  anchor ID as defined by ADR-0026 (format `LLD-<epic-id>-<section-slug>`, e.g.,
  `click DeliveryService href "#LLD-v1-e1-delivery-service" _self` in a `flowchart`;
  `stateDiagram-v2` omits the `_self` target per the AC below).
- Given a `stateDiagram-v2` `click` directive, when generated, then it never includes a
  `_self` target — supplying one is a Mermaid parse error for this diagram type.
- Given a `sequenceDiagram` is generated, when Part A is produced, then no participant
  carries a `click` directive of any form — it is a fatal parse error for this diagram
  type and takes the whole diagram down, not just the link. Sequence-diagram
  participants are reached instead through the `classDiagram` or `flowchart` in the
  section's Structural Overview (Story 1.5), when one exists.
- Given an `erDiagram` is generated, when Part A is produced, then no `click` directive
  is emitted on entities — Mermaid parses but silently ignores it (no link is
  generated), so emitting it adds no navigability and is omitted.
- Given a diagram is fully generated for a type that supports `click` (`flowchart`,
  `classDiagram`, `stateDiagram-v2`), when the diagram source is inspected, then no
  participant is a "dead label" — every participant has a `click` directive resolving
  to either a workspace-relative path or a `#LLD-` anchor.
- Given a workspace-relative path is constructed for a `click` href, when the path is
  built, then it has no leading slash and no `..` segments — suitable for resolution by
  `vscode.Uri.joinPath` and for GitHub's native relative-link resolution.
- Given a Part B section exists with a stable anchor ID, when a `#LLD-` link targets
  it, then the anchor ID follows the ADR-0026 format (`LLD-<epic-id>-<section-slug>`)
  and the `click` directive uses the full anchor ID (including the epic ID) as its
  fragment target.

**Notes:** The `click` directive is the bridge between this story's diagram surface and
Story 1.5's Part B navigation and Story 1.6's cross-renderer verification. A component
that appears only in a sequence diagram (no accompanying `classDiagram` or `flowchart`)
has no click-based path to its Part B spec in V1 — it remains reachable via normal
document scrolling. `edf://` (the v1.0 protocol scheme) is removed entirely: Mermaid's
strict sanitizer strips unrecognised URL schemes in every diagram type, so it never
worked as designed.

---

<a id="REQ-lld-template-diagram-vocabulary-lld-anchor-navigation-part-b"></a>

### Story 1.5: `#LLD-` anchor navigation to Part B specs

**As an** LLD Reviewer,
**I want to** click on a diagram participant marked as a new component (teal outline) in
a `classDiagram`, `flowchart`, or `stateDiagram-v2` and have the preview scroll to its
Part B internal decomposition section,
**so that** I can read the component's spec — function signatures, data shapes, and task
breakdown — in a single click instead of scroll-hunting through the document.

**Acceptance Criteria:**

- Given a diagram participant has a `click` directive with a `#LLD-` anchor (e.g.,
  `#LLD-v1-e1-delivery-service`), when the reviewer clicks it in GitHub's rendered
  markdown or VSCode's markdown preview, then the view scrolls to the corresponding
  Part B `<a id="LLD-v1-e1-delivery-service">` element using standard page-internal
  linking — no extension required in either renderer.
- Given a `#LLD-` anchor target does not exist in the document (broken anchor), when
  clicked, then the view does not scroll and no error is displayed (silent no-op).
- Given a Part B section has a stable anchor ID, when the LLD is generated, then the
  anchor ID follows the ADR-0026 format (`LLD-<epic-id>-<section-slug>`, including the
  epic ID) and the `click` directive's `#LLD-` fragment target matches that anchor ID
  exactly.
- Given a new component is introduced by the design, when it is shown only in a
  `sequenceDiagram` (no `classDiagram`, `flowchart`, or `stateDiagram-v2`
  representation), then it has no `#LLD-` click path in V1 — its Part B spec remains
  reachable via the document's normal heading structure, not via diagram click.

### Visual Reference

- [Markdown Preview Navigation wireframe](../design/v1/vis-markdown-preview-navigation.html) — anchor state (Part B section scrolled into view)

---

<a id="REQ-lld-template-diagram-vocabulary-verify-diagram-link-resolution"></a>

### Story 1.6: Verify diagram link resolution in GitHub and VSCode

**As a** Plugin Maintainer,
**I want to** verify that workspace-relative `click` links and `#LLD-` anchors resolve
correctly across every diagram type that supports `click`, in both GitHub's markdown
renderer and VSCode's built-in markdown preview,
**so that** Epic 1's navigability claims are backed by evidence, not assumption — this is
what makes the rest of the epic trustworthy.

**Acceptance Criteria:**

- Given an LLD with a `flowchart` containing workspace-relative `click` links, when
  viewed in GitHub, then each link navigates to the correct file in the repository.
- Given the same diagram viewed in VSCode's built-in markdown preview, when a link is
  clicked, then the verification records the actual behaviour observed (VSCode may or
  may not open the file natively via its own relative-link handling — no extension
  exists to guarantee this in V1) rather than assuming an outcome.
- Given an LLD with a `classDiagram` using the display-label workaround for
  slash-containing names, when rendered in GitHub and in VSCode, then the diagram
  parses without error in both and the `click` link resolves to the correct file in
  both.
- Given a `stateDiagram-v2` with `click` directives that omit the `_self` target, when
  rendered in GitHub and in VSCode, then the diagram parses without error in both and
  links resolve correctly.
- Given an `erDiagram` with no `click` directives (per Story 1.4), when rendered in
  GitHub and in VSCode, then the diagram parses without error in both, confirming the
  omission does not itself break anything.
- Given a `sequenceDiagram` generated with no `click` directive on any participant
  (per Story 1.4), when rendered in GitHub and in VSCode, then the diagram parses and
  renders without error in both.
- Given a `#LLD-` anchor link, when clicked in GitHub's rendered markdown, then the
  browser scrolls to the corresponding Part B section using standard page-internal
  linking.
- Given the same `#LLD-` anchor link, when clicked inside VSCode's markdown preview,
  then the preview scrolls to the corresponding Part B section.

**Notes:** This is a verification and documentation story, not new template work — the
other Epic 1 stories already define the conventions this one tests. GitLab is not
separately verified in V1 (assumed to behave like GitHub for unknown-scheme and
relative-link handling, given both use the same class of Mermaid renderer, but not
tested). The deliverable is a short verification report (pass/fail per diagram type per
renderer), committed alongside the template, plus a finding on whether VSCode natively
opens relative links from a Mermaid SVG click — see the "Deferred from V1" table in V2 /
Future, which depends on this finding.

---

## Epic 2: VSCode Extension — Review Feedback [Priority: Medium]

Closes the preview→source round-trip for adding review comments. When a reviewer
identifies an issue in the diagram preview, they can insert a `[Review]` marker under
the relevant LLD section heading without hunting through the source editor. This is the
only V1 story requiring extension code — hover-to-peek and click-to-open (the stories
that needed a preview↔host communication channel) moved to V2/Future after a spike found
the assumed channel does not exist in the public VS Code API (ADR-0038's rejection note).
This epic depends on Epic 1 only for the document structure (`##`/`###` headings) it
scans, not for any diagram link format.

<a id="REQ-vscode-extension-review-feedback-quick-pick-insert-review-comment"></a>

### Story 2.1: Quick-pick section → insert `[Review]` comment

**As an** LLD Reviewer,
**I want to** invoke a command from the markdown preview that shows a quick-pick list of
LLD Part A section headings, and on selection inserts a `> **[Review]:** ` template under
that heading in the source editor with focus switched for typing,
**so that** I can add review feedback without manually finding the corresponding line in
the source markdown or breaking my review flow.

**Acceptance Criteria:**

- Given the command is invoked while the markdown preview panel has focus (not a text
  editor), when the extension resolves the target document, then it uses the most
  recently focused markdown text editor — tracked via
  `vscode.window.onDidChangeActiveTextEditor` before the preview took focus, since
  `vscode.window.activeTextEditor` is `undefined` while a webview holds focus — falling
  back to the single markdown editor in `vscode.window.visibleTextEditors` if no
  tracked reference exists, and showing an information message "No source document
  found for this preview" if neither resolves.
- Given the target document is resolved, when the reviewer invokes "EDF: Insert Review
  Comment" from the command palette (Ctrl+Shift+P), then a quick-pick list appears
  showing all `##` and `###` headings extracted from that document, each annotated
  with its line number.
- Given the quick-pick list is open, when the reviewer types in the filter input,
  then the heading list filters in real-time to matching entries (case-insensitive
  substring match).
- Given the reviewer selects a heading from the quick-pick and presses Enter, then a
  `> **[Review]:** ` template followed by a space is inserted on a new line
  immediately after the selected heading's line in the resolved source editor.
- Given the template is inserted, when the operation completes, then the resolved
  source editor gains focus with the cursor positioned at the character immediately
  after the inserted `> **[Review]:** ` text, ready for typing.
- Given the quick-pick is open, when the reviewer presses Escape, then the
  quick-pick dismisses and no changes are made to the document.
- Given the resolved document has no `##` or `###` headings, when the command is
  invoked, then a VSCode information message "No section headings found in this
  document" is shown.
- Given the document being previewed is not an LLD (no Part A / Part B structure),
  when the command is invoked, then the quick-pick still shows all `##`/`###`
  headings — the command works for any markdown document with headings.
- Given a heading already has one or more `[Review]` markers directly beneath it,
  when a new review comment is inserted, then the new template is inserted after the
  existing markers, preserving their order.

### Visual Reference

- [Review Comment Insertion wireframe](../design/v1/vis-review-comment-insertion.html) — quick-pick open and inserted states

---

<a id="REQ-vscode-extension-review-feedback-test-framework-local-packaging"></a>

### Story 2.2: Extension test framework and local `.vsix` packaging

**As a** Plugin Maintainer,
**I want to** establish a test framework for the EDF Review extension and package it as
a local `.vsix` file,
**so that** Story 2.1's behaviour is verified by automated tests and reviewers can
install the extension in a normal VSCode window without running a separate Extension
Development Host.

**Acceptance Criteria:**

- Given the extension's test suite, when run via `@vscode/test-electron` (the standard
  VS Code extension integration-test runner) driving Mocha specs, then Story 2.1's
  quick-pick, filter, insert, and focus-resolution behaviours each have at least one
  passing test.
- Given the extension is built for packaging, when `vsce package` is run against
  `package.json`, then a `.vsix` file is produced with no packaging errors (missing
  `publisher` field, missing required manifest fields, etc.).
- Given a produced `.vsix` file, when installed via
  `code --install-extension edf-review-<version>.vsix`, then the extension activates
  in a normal VSCode window (not a Dev Host) and "EDF: Insert Review Comment" is
  available in the command palette.
- Given the extension is installed via `.vsix`, when a reviewer uses Story 2.1's
  command, then the behaviour matches the Dev-Host-tested behaviour exactly — no
  packaging-only regressions (e.g. missing bundled assets).
- Given the `.vsix` package, when its `package.json` is inspected, then it declares no
  marketplace-publishing metadata beyond what packaging strictly requires (`publisher`,
  `name`, `version`, `engines.vscode`) — no marketplace listing content (icon, gallery
  banner, categories) is authored in V1.

**Notes:** This story resolves Design Principle 7. V1.0 planned Dev-Host-only
distribution on the premise that the two hover/click stories were the extension's main
value; with those moved to V2/Future, Story 2.1 is the only extension deliverable left,
and requiring reviewers to launch a debug VSCode instance just to leave review comments
would undermine the "don't break your review flow" premise. Local `.vsix` packaging is a
low-cost middle ground — no marketplace review, no public listing, just a build artefact
a reviewer installs once. This was a judgement call made during the v1.1 review cycle,
not dictated by the original `[Review]` marker (which offered packaging or dropping the
story as equally valid options) — flag at Gate 2 if Dev-Host-only-and-drop-the-story is
preferred instead.

---

## Epic 3: Skill Instructions & Quality Gates [Priority: Medium]

Updates to `/lld` skill instructions so the template conventions are self-documenting
and mechanically verifiable. Diagram type selection rules, `click` generation logic
(including the per-diagram-type support matrix), annotation placement guidelines, and a
self-critique checklist item for navigability. Ensures the Plugin Maintainer can verify
that generated LLDs follow conventions.

<a id="REQ-skill-instructions-quality-gates-diagram-generation-rules-lld-skill"></a>

### Story 3.1: Diagram generation rules in `/lld` SKILL.md

**As a** Plugin Maintainer,
**I want to** update the `/lld` SKILL.md Step 2 with concrete generation rules for
diagram type selection, `click` directive generation (respecting the per-diagram-type
support matrix), `classDef` application, and `Note` annotation placement,
**so that** every `/lld` invocation produces diagrams that follow the new conventions
without the author needing to remember them.

**Acceptance Criteria:**

- Given a developer runs `/lld`, when Step 2 executes, then the skill follows
  documented rules for diagram type selection: state diagrams for FE state-management
  features, ER diagrams for new/changed data entities, flowcharts for branching
  business logic, and class diagrams for new modules/classes or changed module
  boundaries — each gated by a concrete "When required" condition.
- Given a diagram type is selected, when Step 2 executes, then the skill applies the
  `classDef` palette (error, auth, external, new) from `lld/template.md` to all
  participants matching those roles.
- Given a diagram participant is identified as existing code and the diagram type
  supports `click` (`flowchart`, `classDiagram`, `stateDiagram-v2`), when Step 2
  executes, then the skill generates a `click` directive with a workspace-relative
  path to the source file — never an `edf://` URL.
- Given a diagram participant is identified as a new component and the diagram type
  supports `click`, when Step 2 executes, then the skill generates a `click` directive
  with a `#LLD-` anchor in the format `LLD-<epic-id>-<section-slug>` per ADR-0026 —
  including the epic ID, not just the component name.
- Given a diagram is a `sequenceDiagram`, when Step 2 executes, then the skill never
  emits a `click` directive on any participant — this is a fatal parse error, not a
  stylistic choice.
- Given a diagram is an `erDiagram`, when Step 2 executes, then the skill does not
  emit `click` directives on entities — Mermaid silently ignores the directive there,
  so it adds no navigability.
- Given a `classDiagram` participant's name contains `/`, when Step 2 executes, then
  the skill uses the display-label workaround (`class EngineScoring["engine/scoring"]`)
  rather than the raw path as the class identifier.
- Given enforcement boundaries are identified (authZ, validation, external calls,
  error propagation), when Step 2 executes, then the skill places `Note` annotations
  at the corresponding interaction points with the enforcement mechanism stated.
- Given the generation rules exist in SKILL.md, when the rules are reviewed against
  the template (`lld/template.md`), then every concern has at least one worked example
  in the skill: diagram type selection (example with gate condition), `classDef`
  application (example with colour assignment), `click` generation (example with a
  workspace-relative path and a `#LLD-` path, per supporting diagram type), and `Note`
  annotation placement (example with enforcement mechanism text).
- Given the template (`lld/template.md`) is updated, when the SKILL.md generation
  rules are reviewed, then every template feature has a corresponding generation rule
  in the skill (co-versioning per Design Principle 6).

**Notes:** The SKILL.md rules must reference the template as the single source of
truth for the palette hex values, diagram syntax, click-support matrix, and annotation
format. The skill must not duplicate template content — it references it.

---

<a id="REQ-skill-instructions-quality-gates-self-critique-checklist-diagram-navigability"></a>

### Story 3.2: Self-critique checklist item for diagram navigability

**As a** Plugin Maintainer,
**I want to** add diagram-parsing and navigability checks to the `/lld` Step 2.5
self-critique checklist,
**so that** every LLD author catches parse errors and navigability gaps during
self-review, before the document reaches a human reviewer.

**Acceptance Criteria:**

- Given an LLD is generated by `/lld`, when Step 2.5 (self-critique) executes, then a
  "diagram parses" check runs first and verifies: no `click` directive in any
  `sequenceDiagram` (any form is a parse error), no `_self` target on a
  `stateDiagram-v2` `click`, and no `/` in a `classDiagram` class identifier.
- Given the "diagram parses" check passes, when the "diagram navigability" check
  runs, then it verifies — for `flowchart`, `classDiagram`, and `stateDiagram-v2`
  only — that every participant has a `click` directive: a workspace-relative path for
  existing code, a `#LLD-` anchor for new code.
- Given the self-critique runs, when enforcement points are evaluated, then the check
  verifies: every interaction crossing a trust boundary (authZ, validation, external
  service, error propagation) has a `Note` annotation stating the enforcement
  mechanism.
- Given the self-critique runs, when the `classDef` palette is evaluated, then the
  check verifies: the palette block is present (in a `text` fence, not a bare
  `mermaid` fence) at the top of Part A and is applied consistently — no participant
  that matches a defined role uses default styling.
- Given a check fails, when reported to the author, then the failure message
  identifies the specific participant, interaction, diagram type, or path that needs
  fixing — not a generic "diagram could be improved."
- Given the checklist item exists, when an LLD author runs `/lld` and receives the
  self-critique output, then navigability and parse issues are surfaced at the same
  prominence level as other checklist items (security, error paths, reused helpers).

**Notes:** The checklist item must be written so that an automated agent (the `/lld`
skill itself) can execute the checks. Prefer mechanical checks (grep for `click`,
verify path existence, verify diagram-type/click combinations) over judgment calls. The
checklist item in SKILL.md must match the template conventions defined in Epic 1.

---

## Cross-Cutting Concerns

### Security

- **Extension code review (owned by Story 2.1):** VSCode extensions run with full Node
  privileges — there is no manifest-level permission system, and `activationEvents`,
  `extensionKind`, or an empty `"scripts"` entry do not restrict runtime filesystem or
  network access. The V1 guarantee is enforced by code review, not by the manifest: the
  extension's code is reviewed to confirm it performs only heading extraction,
  quick-pick display, and text insertion into the resolved editor — no file reads
  beyond the open document, no network calls, no process execution.

### Performance

No V1 performance requirements. The two latency-sensitive stories (hover tooltip,
click-to-open) moved to V2/Future — see the "Deferred from V1" table below for their
carried-forward budgets, including a known violation that must be fixed before either is
reopened.

### Observability

- **Extension errors (owned by Story 2.1):** A failure to resolve the source document
  for the focused preview (see Story 2.1's focus-resolution AC) produces a log entry in
  the VSCode output channel `EDF Review` stating the reason no document could be
  resolved.

---

## What We Are NOT Building

- **Additional diagram types (C4Context, gantt, pie, etc.)** — V1 is scoped to
  `stateDiagram-v2`, `erDiagram`, `flowchart TD`, and `classDiagram` as conditional
  additions to the existing sequence diagram foundation. Other diagram types may be
  considered in future versions.
- **Per-project or per-team palette customisation** — The `classDef` palette is a
  single convention applied uniformly. Customisation adds configuration surface that
  V1 does not need.
- **Automated annotation generation from code analysis** — Enforcement point
  annotations are authored by the LLD writer (guided by skill instructions), not
  inferred from static analysis of the codebase.
- **Hover tooltip showing source file preview** — Drafted for V1, moved to V2/Future
  after the assumed preview↔extension communication API could not be found (see
  "Deferred from V1" below).
- **Click opens source file in adjacent column** — Drafted for V1, moved to V2/Future
  pending Story 1.6's finding on whether VSCode already does this natively (see
  "Deferred from V1" below).
- **Bidirectional navigation (code → diagram)** — Clicking a function in source code
  does not highlight the corresponding diagram participant. This requires Tree-sitter
  or equivalent code parsing and is deferred to Wave 3+.
- **Full code-to-diagram synchronisation engine** — Diagrams are not auto-updated
  when code changes. The `lld-sync` skill handles drift at the document level;
  real-time diagram sync is out of scope.
- **Real-time collaborative editing** — `[Review]` markers are an async convention,
  not a CRDT-backed live commenting system.
- **Extension marketplace publishing** — V1 packages the extension as a local `.vsix`
  file (Story 2.2). Marketplace listing content, publisher verification, and
  consumer-facing installation instructions beyond `code --install-extension` are
  deferred to a future version.
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

These Wave 2 and Wave 3+ discovery features, plus two V1 stories deferred by a spike
finding, are out of scope for V1 but captured here as input for future discovery and
requirements cycles.

### Deferred from V1 (spike-blocked)

These stories were drafted for V1 but moved after a spike (recorded in ADR-0038's
rejection note) established that their assumed VS Code API does not exist. Reopening
either requires a new architecture answer, not just implementation time.

| Feature | Description | Reopening condition |
|---------|--------------|----------------------|
| Hover tooltip showing source file preview | Hover over a diagram link to see ~40 lines of the referenced file in a tooltip. | The V1 spike could not find `vscode.window.onDidReceivePreviewMessage` in the public VS Code API — the built-in markdown preview has no confirmed two-way channel back to the extension host. Reopen only after a spike finds a working preview→host communication channel, or the story is rebuilt against a custom webview panel instead of the built-in preview. |
| Click opens source file in adjacent column | Click a diagram link to open the file beside the preview, which stays visible. | Story 1.6 verifies whether VSCode's built-in markdown preview already opens workspace-relative links natively when clicked inside a rendered Mermaid SVG. If it does, this feature may already be delivered for free by Epic 1 with no extension code — check Story 1.6's verification report before re-scoping this. |

Carried-forward requirements (apply only if either feature above is reopened):

- **UX — preview-sticky opening:** Opening a source file from a diagram link must not
  close or replace the markdown preview — the preview stays visible in its original
  column so the reviewer keeps their place in the design document. (The original
  Design Principle 2 in v1.0 stated this for the click-to-open story specifically;
  V1's surviving principle only covers the lighter guarantee that inserting a
  `[Review]` comment doesn't disrupt the preview.)
- **Security — path traversal prevention:** Path resolution for a hovered/clicked link
  must validate that the resolved file path is within the workspace root, rejecting
  `..`-segment escapes before any `readFile` or `showTextDocument` call.
- **Security — no arbitrary code execution:** File content must be read via
  `vscode.workspace.fs.readFile` as UTF-8 text only — never evaluated, `import()`ed, or
  otherwise interpreted.
- **Performance — hover tooltip latency:** Tooltip content must appear within 200ms of
  the hover event (excluding a 150ms debounce).
- **Performance — file open latency:** `showTextDocument` must be issued within 100ms
  of the click event.
- **Performance — preview script overhead:** The injected preview script must stay
  under 5KB minified; its `MutationObserver` callback must complete in under 1ms per
  invocation. The V1 scaffold's unthrottled full-document `querySelectorAll` on every
  mutation already violates this budget and must be fixed as part of reopening, not
  inherited as-is.
- **Observability — preview script errors:** JavaScript errors in the preview script
  must be caught and relayed to the extension host for logging to the `EDF Review`
  output channel; unhandled errors must not crash the preview webview.

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

1. Run `edf:kickoff docs/requirements/v1-requirements.md` to re-verify the HLD and
   re-attempt the ADR gate now that Epic 2's stories have changed — the existing HLD
   (`docs/design/v1/v1-design.md`) and the rejected ADR-0038 both reference the v1.0
   epic structure and the `edf://` scheme, and will need a pass to reflect this
   revision (renumbered epics, dropped protocol scheme, `.vsix` packaging).
2. The V2 / Future section above is input for the next discovery cycle — Wave 2
   features (F10, F12), Wave 3+ enhancements, and the two spike-blocked stories should
   be reconsidered after V1 ships.

---

## Open Questions

| # | Question | Context | Options | Impact |
|---|----------|---------|---------|--------|
| 1 | ~~Should F11 (graceful degradation) be verified against specific GitHub markdown renderer versions, or is "harmless dead link" behaviour sufficient as a general requirement?~~ **Resolved (2026-08-02).** | Superseded: with workspace-relative paths, links resolve to real files in GitHub rather than degrading to inert placeholders. | — | Verification is now Story 1.6's scope (renamed from "graceful degradation" to "verify diagram link resolution"). |
| 2 | ~~What is the exact mechanism for the preview→extension communication channel for hover tooltips?~~ **Resolved (2026-08-02).** | The assumed `vscode.window.onDidReceivePreviewMessage` API could not be found in the public VS Code API (see ADR-0038's rejection note). | — | The question moves to V2/Future with the hover-tooltip entry in "Deferred from V1" — reopening needs a new spike, not an implementation choice. |
| 3 | ~~Should the `classDef` palette colours be chosen now or deferred to implementation?~~ **Resolved.** | The palette hex values are already defined in `lld/template.md`. | error `#f7d6d6`, auth `#f7eed6`, external `#d6e8f7`, new `#d4f0d4`. | The glossary and Story 1.2 reference these as the canonical source of truth. |
| 4 | ~~Does F13 (quick-pick → insert `[Review]`) need the section headings parsed from the markdown AST, or is a regex-based extraction of `##`/`###` headings sufficient?~~ **Resolved.** | Regex is simpler and sufficient for the LLD's predictable heading structure. | Regex chosen over AST parsing. | Story 2.1 (renumbered from 3.1 in v1.0) defaults to regex extraction. |
