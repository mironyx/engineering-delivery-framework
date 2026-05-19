# 0035. Visual Specifications in the Design Pipeline

**Date:** 2026-05-19
**Status:** Proposed
**Deciders:** LS / Claude

## Context

The pipeline produces three views of a feature before implementation:

```
Behavioural flows (sequence diagrams) → how the system interacts
Structural overview (class diagrams)   → how the pieces connect
Visual specification (???)             → what the user sees
```

The first two are covered. The third is missing. Today, UI surfaces are
described entirely in text — component trees, page routes tables, UI state
tables with values like "Skeleton" or "Error message + retry." These tell the
implementing agent *that* a loading state exists but not *what it looks like*.

The agent fills the gap by guessing. Layout, spacing, visual hierarchy, the
specific form of a skeleton or empty state — all are invented at implementation
time. When the guess is wrong, the fix costs ~10× what specifying it upfront
would have cost (same multiplier ADR-0034 cites for acceptance criteria).

The problem compounds across the pipeline:

| Stage | What happens to visual intent |
|-------|------------------------------|
| Requirements | "As a user, I want a dashboard" — no visual |
| HLD | "DashboardPage component" — no visual |
| LLD | Component tree + UI states table — text only |
| `/feature` | Agent invents visual decisions → drift |

The `frontend-design` skill exists in the harness and produces HTML/CSS
prototypes with high design quality. It is not currently integrated into any
pipeline stage.

## Decision

**Add visual specifications as a pipeline artifact, produced during
requirements and propagated through to LLD Part A alongside behavioural
and structural diagrams.**

### 1. Production: during `/requirements`

After stories are drafted and before Gate 2 (complete), stories with UI impact
are identified. For each UI-impacting story (or cluster of related stories
sharing screens), a visual spec is generated and saved to
`docs/design/visuals/<screen-name>.html`.

Each story that has a visual reference gets a `## Visual Reference` subsection
linking to the wireframe file. The reference is keyed to the story's REQ-
anchor so traceability is mechanical.

#### Two modes

Visual spec generation has two modes. The mode is **auto-inferred** from the
story context and can be overridden explicitly with `--fe-mode full|lite`.

**Full mode** (`frontend-design` skill):
- For completely new screens, pages, or views.
- Produces a production-grade HTML/CSS prototype with design tokens,
  typography scale, spacing system, and color palette.
- ~300-500 lines of HTML/CSS per screen.
- The implementing agent uses it as a pixel-accurate reference.

**Lite mode** (lightweight structural HTML):
- For modifications to existing screens — adding a filter, rearranging a
  layout, adding a new state to an existing component.
- Produces a grayscale structural skeleton: grid/flexbox layout, placeholder
  content, all relevant states, no design tokens or color system.
- ~40-80 lines of HTML/CSS per screen.
- The implementing agent uses the screenshot for spatial reference; the HTML
  is not production code.

Both modes show:
- Layout and spatial hierarchy of the screen
- All relevant UI states (loading, empty, error, success, edge cases)
- Interactive elements and their relative priority

#### Mode inference

| Signal | → Full | → Lite |
|--------|--------|--------|
| Screen exists in `docs/design/visuals/` | | x |
| Story references existing component from frontend-architect catalog | | x |
| Story REQ- anchor maps to a known page route in prior LLD | | x |
| No prior visual artifact exists | x | |
| Story describes a complete new page/screen | x | |
| ACs are net-new interactions, not modifications | x | |

When signals conflict (e.g. a major redesign of an existing screen — the file
exists but the ACs describe a fundamentally new layout), the inference biases
toward **lite**. Lite is cheaper, and if the result is underwhelming the human
re-runs with `--fe-mode full`. The cost of being wrong is lower on the lite
side.

Explicit override: `--fe-mode full` or `--fe-mode lite` bypasses inference
entirely. Use when you know ahead of time what fidelity you need.

### 2. Propagation: into LLD Part A

Part A of the LLD is what the human reviewer and the implementing agent both
read. It currently has behavioural flows (sequence diagrams) and structural
overview (class diagrams). Visual specifications become the third view.

Each LLD section that covers frontend work includes a **Visual Specifications**
subsection in Part A, placed after Structural Overview and before Invariants.
It contains:

- A table mapping each screen/page to its visual reference (HTML wireframe)
- Screenshots of the wireframes embedded directly in the markdown, showing
  the key screens with all relevant states
- A cross-reference column linking each visual spec to the REQ- anchors and
  HLD components it satisfies

Screenshots are the embedded view; the HTML file is the source of truth. If
the LLD refines visual details (e.g. a new state discovered during LLD), the
HTML wireframe is updated and new screenshots are taken.

### 3. Review gates: extending ADR-0034

Two new checklist items extend the review gates established by ADR-0034:

**Requirements review (before Gate 2):**
- Visual coverage — every UI-impacting story has a visual reference or an
  explicit deferral note. Flag stories that describe UI surfaces in ACs but
  lack a linked wireframe.

**LLD review (after Step 2.5):**
- Visual specification presence — every LLD section with a Frontend layer has
  a Visual Specifications subsection in Part A. Flag sections where FE work
  is described in Part B but no visual spec exists in Part A.
- Visual state coverage — the visual spec shows all states declared in the
  UI states table (loading, error, empty, success) plus any edge cases
  identified in BDD specs. Flag missing states.

### Integration summary

```
/requirements
  Step 3: Draft stories
  Step 3a: [NEW] Identify UI-impacting stories → infer mode (full/lite) → generate
           wireframes (lite by default, full when context demands it)
  Step 4: Draft ACs (informed by visual specs)
  Step 5: Gate 2 — requirements review checks visual coverage
  → docs/design/visuals/<screen>.html

/kickoff
  HLD references visual specs when describing FE components

/architect → /lld
  Part A includes Visual Specifications subsection
  LLD review checks visual spec presence and state coverage
  → screenshots embedded, HTML wireframes updated if LLD refines visuals
```

### What the implementing agent gets

Before this ADR, the `/feature` agent received:
- A component tree (ASCII)
- A page routes table
- A UI states table (text descriptions)

After this ADR, it additionally receives:
- A screenshot of what each screen should look like
- A screenshot of each UI state (loading, error, empty, success)
- The HTML wireframe (full mode: production-grade reference for spacing, color,
  typography; lite mode: grayscale structural skeleton for spatial layout)

The text tables still declare *what* states exist. The visual spec answers
*what they look like*. The mode determines how precise that answer is.

## Consequences

- **Reduced implementation drift.** The agent no longer invents layout,
  spacing, and visual hierarchy. Visual decisions are made once at design
  time, reviewed, and locked in.
- **Stronger requirements.** ACs written after wireframes are more precise —
  "the submit button is disabled until all required fields are filled" is
  easier to write when you can see the form layout.
- **LLD Part A becomes a complete design document.** A reviewer can read
  behavioural flows + structural diagrams + visual specs and build a full
  mental model without switching to an external design tool.
- **Version-controlled visual design.** HTML wireframes live in the repo
  alongside other design artifacts. They survive Figma link rot and are
  diffable (HTML is text). They are not a replacement for a design tool —
  teams that use Figma can link to Figma instead. The requirement is that
  visual intent is captured; the HTML wireframe is the default mechanism,
  not the only one.
- **Additional pipeline cost.** Lite mode adds ~2-3K tokens per screen
  (trivial structural HTML). Full mode adds roughly one `/pr-review` worth of
  token spend per screen cluster. Since most stories are modifications
  (lite), the steady-state cost is low. The return is avoided rework on FE
  implementation — a single bad FE cycle costs ~100K+ tokens.
- **Not every story needs this.** Pure backend stories, CLI tools, API-only
  changes, and schema migrations have no visual surface. The requirements
  review gate checks for UI impact; stories without it skip visual spec
  generation.

## Alternatives considered

- **Figma/Sketch references only.** Rejected as the default — links rot,
  files are not version-controlled alongside the code, and access requires
  tool licenses. But the Visual Reference field accepts a Figma link; the
  requirement is that visual intent is captured, not that HTML is the only
  format.
- **ASCII wireframes in markdown.** Rejected — too limited to convey spatial
  relationships, visual hierarchy, and states with fidelity.
- **Produce visual specs during `/kickoff` instead of `/requirements`.**
  Rejected — ACs are written during requirements. Writing ACs without seeing
  the interface produces weaker ACs. Visual specs must exist before ACs are
  finalized.
- **Produce visual specs during `/architect` only.** Rejected — same
  late-binding problem ADR-0034 identifies. Visual decisions made at LLD
  time don't inform requirements or HLD review.
- **Single mode (always full `frontend-design`).** Rejected — running
  full production-grade design for every minor UI change (new filter, new
  state, layout tweak) is wasteful. Most FE stories are modifications to
  existing screens, not greenfield pages. Two modes with auto-inference
  keeps the common case cheap while preserving the option for full fidelity
  when needed.
- **Skip screenshots, link HTML only.** Rejected — the LLD is a markdown
  document reviewed by humans and parsed by agents. An embedded screenshot
  provides immediate visual reference; an HTML link requires a context switch
  and a browser. Both are kept — the screenshot for review, the HTML for
  implementation detail.
