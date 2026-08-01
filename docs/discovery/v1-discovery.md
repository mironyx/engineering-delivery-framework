# Discovery: Review-focused LLD Diagram Improvements

Date: 2026-08-01
Source: Freeform brief (review-experience improvements)
Status: Draft — Problem Space

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
| | Changes to `lld/template.md`, `lld/SKILL.md`, and new `extensions/edf-review/` | Changes to other skills, agents, or the PR review flow |

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
