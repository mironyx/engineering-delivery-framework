# Discovery: Review-focused LLD Diagram Improvements

Date: 2026-08-01
Source: Freeform brief (review-experience improvements)
Status: Draft — Complete

---

## Activity 1 — Vision statement

For **EDF reviewers** who read LLD Part A documents to build theory about a feature
before code review, the **LLD Part A diagram surface** is a navigable review cockpit
that **delivers instant code context without tab-switching**. Unlike the current
experience — where a reviewer sees component names in a diagram but must manually grep
to find the corresponding source, losing their place in the design doc — **our approach**
embeds code references directly into the diagrams themselves, making the markdown
preview a clickable map of the codebase. Hover to peek, click to open, review without
leaving the design surface.

---

## Activity 2 — Boundaries (Is / Is Not)

| | Is | Is Not |
|---|---|---|
| **The product** | A richer diagram vocabulary for LLD Part A (state, ER, flowchart types) | A general-purpose diagramming tool |
| | Consistent styling palette matching EDF pipeline conventions | A design-system framework or theme engine |
| | Standard annotations marking enforcement points in sequence diagrams | Automated security analysis of designs |
| | Clickable diagram participants linking to source code (existing) or Part B specs (new) | A full code-to-diagram synchronisation engine |
| | A thin VSCode extension that intercepts diagram clicks in the markdown preview | A standalone application or web service |
| | `[Review]` comment convention for collecting and addressing feedback on LLDs | A real-time collaborative editing system |
| **The scope (V1)** | `stateDiagram-v2`, `erDiagram`, `flowchart TD` as conditional diagram types in the LLD template | `C4Context`, `gantt`, `pie`, or other diagram types |
| | `classDef` palette (error/auth/external/new) applied across all diagrams | Per-project or per-team palette customisation |
| | `Note` annotations on sequence diagrams for authZ, validation, external boundaries | Automated annotation generation from code analysis |
| | `click` directives on every diagram participant (`edf://` for existing code, `#LLD-` for new) | Bidirectional nav (code → diagram) |
| | Hover tooltip showing ~40 lines of referenced source file | Full file inline rendering or deep code analysis |
| | Click opens source file in adjacent VSCode column | Code-aware zoom or drill-down navigation |
| | `[Review]` markers supported in LLD documents | New tooling for comment collection or batching |
| | Changes to `lld/template.md`, `lld/SKILL.md`, and new `extensions/edf-review/` | Changes to other skills or agents — TBD: the solution space may reveal upstream/downstream impacts on `lld-sync`, `pr-review`, `architect`, or `feature-core` |

---

## Activity 3 — Personas

### Persona: LLD Reviewer (Developer)

**Profile:** A developer reviewing an LLD Part A before or alongside a PR. They read
the design document to build theory — what components exist, how they interact, what
enforcement points protect each boundary, and what invariants must hold. Then they open
the PR or branch and need to verify: does the code match the design? Did the implementer
add functions not in the spec? Are the enforcement points actually enforced?

**Goals:**
- Understand the feature's component interactions and data flow at a glance
- Quickly verify that the implementation matches the design's named functions and signatures
- Check that enforcement points (authZ, validation, error handling) are actually present
- Provide feedback on design gaps or implementation mismatches without friction
- Stay oriented in the design document while inspecting source code

**Pain points:**
- Diagrams are flat — participant names like `AuthHelper` mean nothing unless they already know the codebase
- To check a referenced function's real signature, they must: remember the name, Ctrl+P to find the file, scroll to the function, read it, Ctrl+Tab back to the LLD, re-find their place
- Security and validation stories are buried in Part B prose — invisible in the diagrams that are the primary review surface
- Feedback requires switching to a different tool (GitHub comments, Slack) and manually referencing LLD section numbers
- New components (not yet implemented) have no spec to check against — Part B is a separate scroll target, often far from Part A
- Preview-to-source switching for comments — diagrams render beautifully in the preview, but adding a `[Review]` comment requires switching back to the source editor, finding the right line, and breaking the visual flow
- Tests are hard to reach — the PR branch is checked out locally, but running the tests to verify the implementation works requires knowing the project's test commands and conventions

**Context:** Opens the LLD in VSCode's native markdown preview (Ctrl+Shift+V). Switches
between the preview and the source editor. May be looking at a PR in the browser on a
second monitor. Typically reviews 2–5 LLDs per week, 15–45 minutes each.

**Quote:** "I see `AuthHelper` in the diagram — is that the one from `src/lib/auth/helper.ts` or a new thing? Let me grep for it. ...OK, found it. Now where was I in the design doc?"

### Persona: Plugin Maintainer (Developer)

**Profile:** A developer working on the EDF plugin itself. After implementing
improvements to the framework, they need to verify that the generated LLDs follow
the new conventions, that the VSCode extension works correctly, and that the
documentation is consistent.

**Goals:**
- Verify that `/lld` produces diagrams following the new conventions
- Test that the VSCode extension correctly intercepts `edf://` links
- Ensure the template and skill instructions stay in sync
- Keep the framework maintainable — new conventions should be self-documenting

**Pain points:**
- Template and SKILL.md can drift — the skill instructions and the template must be manually kept consistent
- Testing VSCode extensions requires extension development host — adds friction to iteration
- New conventions must degrade gracefully in GitHub and other renderers that don't have the extension

**Context:** Works in the EDF plugin repo itself. Uses `/lld` to generate test LLDs
and verifies the output. Runs the extension in VSCode's Extension Development Host.

**Quote:** "Does the `click` directive work in GitHub's Mermaid renderer? It needs to degrade gracefully or we'll get bug reports from users who don't have the extension."

---

## Activity 4 — User journeys

### Journey: LLD Reviewer — Review a PR with the LLD as navigation surface

**Trigger:** A PR is assigned for review. The reviewer opens it in VSCode using the
GitHub Pull Requests extension.

**Prerequisites:** GitHub Pull Requests extension installed and authenticated.
EDF Review extension installed (provides `edf://` link handling in markdown preview).

**Steps:**

1. **Open the PR** — In the GitHub Pull Requests sidebar, select the PR and click
   "Checkout". The branch is pulled locally and the diff opens. The reviewer now
   has full codebase context, not just the web diff.
2. **Open the LLD** — Navigate to the LLD referenced in the PR description or
   issue body. Open markdown preview (Ctrl+Shift+V). Part A renders with Mermaid
   diagrams showing the feature's component interactions.
3. **Build theory from Part A** — Read the behavioural flows (sequence diagrams
   showing component interactions with enforcement points annotated). Scan the
   structural overview (class diagram or ER diagram showing module/data structure).
   Review the invariants table.
4. **Peek at referenced code** — Hover over a diagram participant marked as
   existing code. A tooltip shows the first ~40 lines of the source file.
   Verify: does the real function signature match the design's assumptions?
5. **Deep-dive into a file** — Click a diagram participant. The source file opens
   in the adjacent VSCode column. The preview stays open — no context switch.
   Read the implementation, then click another participant to jump to the next file.
6. **Check new code against specs** — Click a diagram participant marked as new
   (teal outline). The preview scrolls to the Part B section with the component's
   internal decomposition and function signatures. Verify the implementation
   against the spec.
7. **Review the diff** — Use the GitHub extension's diff editor to see what
   actually changed. Cross-reference: does every new function in the diff appear
   in the LLD's internal decomposition? Did the implementer add unspecified
   functions?
8. **Add comments** — Find an issue? Add a `[Review]` marker inline in the LLD
   source markdown (e.g. `> **[Review]:** signature mismatch — LLD says `fn(ctx,
   params)` but impl uses `fn(params)`). Switch to the diff editor and add inline
   comments via the GitHub extension for code-specific feedback.
9. **Complete the review** — In the GitHub extension, select Comment, Approve, or
   Request Changes. The review is submitted to GitHub.

**Outcome:** The reviewer has verified the implementation against the design,
checked enforcement points, and provided feedback — all within VSCode without
tab-switching between browser, editor, and design doc.

**Pain points addressed:**
- Diagram participants now resolve to real code (hover to peek, click to open)
- Enforcement points are visible in diagrams via `Note` annotations — no need to
  grep Part B prose
- New components link to their Part B spec — single click, no scroll-hunting
- Feedback stays in the LLD via `[Review]` markers alongside GitHub PR comments

### Journey: Plugin Maintainer — Verify generated LLDs follow conventions

**Trigger:** After making changes to the LLD template or skill instructions, the
maintainer needs to verify that `/lld` still produces correct output.

**Steps:**

1. **Generate a test LLD** — Run `/lld epic <number>` against a known epic in a
   test project. The skill follows the new template and generation rules.
2. **Open the preview** — Open the generated LLD in markdown preview. Verify:
   - `classDef` palette block is present at the start of Part A
   - Diagrams use the correct types (stateDiagram for FE states, erDiagram for DB,
     flowchart for branching logic)
   - Every diagram participant has a `click` directive — no dead labels
   - Enforcement points are annotated with `Note` blocks
3. **Test the extension** — In the Extension Development Host, open the LLD preview.
   Hover over an `edf://` participant — verify the tooltip shows code. Click —
   verify the file opens in the adjacent column. Click a `#LLD-` link — verify
   the preview scrolls to the Part B spec.
4. **Test graceful degradation** — Open the LLD on GitHub. Verify `edf://` links
   render as harmless dead links (cursor changes, nothing breaks). Verify `#LLD-`
   anchors work as standard page-internal links.

**Outcome:** The maintainer confirms that the conventions are self-documenting,
the extension works, and the output degrades gracefully outside VSCode.

### Journey: LLD Reviewer — Submit review comments via LLM

**Trigger:** After reviewing an LLD and adding `[Review]` markers, the reviewer
wants an LLM to process their feedback and update the document.

**Steps:**

1. **Add `[Review]` markers** — While reviewing the LLD in the markdown source,
   add blockquote comments at relevant locations:
   ```markdown
   > **[Review]:** Sequence diagram missing error path — the webhook failure case
   > isn't shown. Add a detail diagram for the error flow.
   ```
2. **Collect comments** — Before submitting, grep the document for all `[Review]`
   markers to see the full list of issues.
3. **Send to LLM** — Prompt: "Review the LLD at `docs/design/v{N}/lld-<epic>.md`,
   comments are marked with `[Review]` tags. Address each comment and update the doc."
4. **Verify updates** — The LLM processes each marker, applies changes, removes
   resolved markers. Reviewer checks the diff and approves.

**Outcome:** Feedback is collected inline with the design doc, processed by the LLM,
and incorporated — no separate issue tracker, no copy-paste between tools.

**Note:** This journey relies on the existing `[Review]` convention (already used
in `/requirements` and `/discovery`). No new tooling is needed — just extending
the convention to LLDs and documenting it.

### Journey: LLD Reviewer — Run tests from the PR branch

**Trigger:** After verifying the design against the implementation, the reviewer
wants to confirm the code actually works.

**Prerequisites:** PR branch checked out locally via GitHub Pull Requests extension.
Project has EDF test scripts configured (via `/edf:setup`).

**Steps:**

1. **Identify test files** — The LLD's Tasks section lists "Files to create/modify"
   including test files. The PR diff shows which tests were added or changed.
2. **Run the tests** — From the terminal or via `/edf:test`, run the test suite
   for the changed files. The EDF test runner scripts provide token-efficient output.
3. **Verify coverage** — Check that the tests cover the acceptance criteria and
   BDD specs listed in the LLD. If the LLD says "webhook replay is idempotent" and
   there's no test for it, that's a review finding.
4. **Add findings** — If tests fail or coverage gaps exist, add `[Review]` markers
   in the LLD and/or inline comments in the PR diff.

**Outcome:** The reviewer has confidence that the implementation not only matches
the design but also passes its tests — without leaving VSCode.

**Pain points addressed:**
- Test commands are discoverable via EDF conventions (the CLAUDE.md Verification
  Commands table already documents the exact commands)

**Note:** This journey relies on project setup already done (`/edf:setup` configures
test scripts in CLAUDE.md). The discovery does not propose building a test runner —
the EDF test skill and scripts already exist. The improvement is making the connection
between LLD → test files → run command visible and low-friction. A future enhancement
could add a "Run tests for this section" command to the LLD preview extension.

---

## Activity 5 — Feature catalogue

| # | Feature | Journey | Personas | Effort | Value | Notes |
|---|---------|---------|----------|--------|-------|-------|
| F1 | New diagram types in LLD template (state, ER, flowchart) | J1, J2 | Reviewer, Maintainer | S | H | Conditional on "When required" gates. Template changes only. |
| F2 | Standard `classDef` palette (error/auth/external/new) | J1, J2 | Reviewer, Maintainer | S | M | Colours match EDF pipeline flowcharts. Defined once, applied everywhere. |
| F3 | `Note` annotations on sequence diagrams for enforcement points | J1, J2 | Reviewer | S | H | AuthZ, validation, SSRF boundaries, error propagation. |
| F4 | `click` directives on every diagram participant | J1, J2 | Reviewer, Maintainer | M | H | `edf://` for existing code, `#LLD-` for new. Template + generation rules. |
| F5 | VSCode extension: hover tooltip showing ~40 lines of source | J1 | Reviewer | M | H | `markdown.previewScripts` + `onDidReceivePreviewMessage` with panel reference for reply. |
| F6 | VSCode extension: click opens file in adjacent column | J1 | Reviewer | S | H | `showTextDocument(ViewColumn.Beside)`. Preview stays open. |
| F7 | `#LLD-` anchor navigation (click new component → scroll to Part B spec) | J1 | Reviewer | S | M | Leverages existing stable LLD anchors (ADR-0026). Works in any markdown renderer. |
| F8 | Diagram generation rules in `/lld` SKILL.md | J2 | Maintainer | S | M | Step 2 rules for type selection, click generation, annotation placement. |
| F9 | Self-critique checklist: diagram navigability | J2 | Maintainer | S | M | Step 2.5 item: every participant has a `click`, enforcement points annotated. |
| F10 | `[Review]` convention documented for LLDs | J3 | Reviewer | S | M | Same convention as requirements/discovery. No code — documentation + template mention. |
| F11 | Graceful degradation: `edf://` links harmless in GitHub | J2 | Maintainer | S | H | `_self` target + unrecognised URL scheme → cursor changes, no navigation, no error. |
| F12 | Upstream/downstream skill impact assessment | J2 | Maintainer | S | M | Check `lld-sync`, `pr-review`, `architect`, `feature-core` for compatibility with new conventions. |
| F13 | Preview-to-source comment insertion | J3 | Reviewer | M | L | Command to jump from preview location to source editor and insert `[Review]` template. VSCode preview↔source mapping is fragile — assess feasibility before committing. |
| F14 | "Run tests for this section" in LLD preview | J4 | Reviewer | L | M | Contextual test execution from the LLD. Requires test file path extraction from LLD Tasks section + project test command discovery. |

---

## Activity 6 — MVP sequencer

### Wave 1 — Core (minimum viable)

**Features:** F1, F2, F3, F4, F5, F6, F7, F8, F9, F11

**Rationale:** This is the complete diagram improvement surface. F1–F4 are the
template/convention changes — they define what gets generated. F5–F7 are the VSCode
extension — they make the generated output interactive. F8–F9 are the skill
instructions — they ensure `/lld` follows the new conventions. F11 is non-negotiable:
the `edf://` protocol must degrade gracefully or it breaks LLDs viewed outside VSCode.

All Wave 1 features together deliver the vision: a reviewer opens an LLD in VSCode
preview, hovers over diagram participants to see code, clicks to open files, and
stays oriented in the design document throughout.

### Wave 2 — Review workflow

**Features:** F10, F12

**Rationale:** F10 (review convention) adds no new code — it's documentation.
F12 (impact assessment) is a discovery task that may produce additional work items
if other skills need updating. These naturally follow Wave 1 because they depend
on knowing the final shape of the conventions.

### Wave 3+ — Future

**Features:** F13, F14 — bidirectional navigation (code → diagram highlighting),
live drift detection between code and LLD diagrams, CodeBoarding-style auto-generated
diagrams post-implementation, inline code snippet rendering below diagrams in the
preview.

**Rationale:** F13 (preview-to-source comment insertion) depends on VSCode's
markdown source mapping, which may not be precise enough for diagram-heavy documents.
F14 (contextual test execution) requires extracting test file paths from LLD sections
and discovering project test commands — useful but needs the Wave 1 navigation
patterns to prove themselves first. The other future items are higher effort or
depend on external APIs (Gemini for auto-generated diagrams).
