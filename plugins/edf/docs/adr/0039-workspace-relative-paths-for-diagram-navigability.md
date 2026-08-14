# 0039. Workspace-Relative Paths for LLD Diagram Navigability

**Date:** 2026-08-13
**Status:** Accepted
**Deciders:** LS / Claude

## Context

LLD Part A diagrams are the primary surface a reviewer uses to build theory about a feature.
A participant labelled `AuthHelper` is only useful if the reviewer can reach what it names —
the source file for existing code, or the Part B specification for something being built.
Without that, the reviewer leaves the document to grep, and loses their place.

This requires choosing a **link form** for diagram participants. The choice is load-bearing
in an unusual way: it is embedded in `lld/template.md`, applied by `lld/SKILL.md`, checked by
the self-critique gate, and then reproduced in every LLD the framework generates, in every
project that adopts EDF. Changing it later means migrating documents that already exist.

**This decision has been made once already and was wrong.** V1.0 chose a custom `edf://`
scheme, intercepted by a VSCode extension that would resolve paths, show hover previews, and
open files. An HLD, a template section, a skill section, and roughly 250 lines of extension
code were built on it. A spike in August 2026 falsified the premise, and the record of that
spike is [ADR-0038's rejection note](0038-extension-architecture-security-model.md), which
explicitly defers the replacement decision to this ADR rather than pre-writing it.

The reason the mistake was cheap to make is worth stating plainly: a custom URL scheme is the
*natural-looking* design for an editor integration. It reads as clean, it is what a
protocol-handler-based tool would do, and nothing about it looks wrong until it is measured.

### What the measurement established

Verified against Mermaid 11.12.2 — the version pinned by `mjbvz/vscode-markdown-mermaid`,
merged into VS Code 1.121 as the built-in *Mermaid Markdown Features* extension:

1. **Custom schemes do not survive the renderer.** That extension never sets `securityLevel`,
   so Mermaid defaults to `strict`, whose URL sanitizer strips the `href` attribute for any
   unrecognised scheme. Confirmed stripped: `edf://`, `vscode://`, `file://`, and arbitrary
   custom schemes. Confirmed surviving: workspace-relative paths, absolute paths,
   `#fragment`, `https:`, `mailto:`. This applies to **every** diagram type — so the link
   never reached the DOM for any extension to intercept.
2. **`click` support is not uniform, and fails in two different ways.** `sequenceDiagram`
   treats any form of `click` as a **fatal parse error** that takes down the whole diagram —
   not the silent no-op the earlier design assumed. `erDiagram` parses `click` and generates
   no anchor at all. `stateDiagram-v2` parse-errors on the `_self` target.
3. **`vscode.window.onDidReceivePreviewMessage` does not exist** in the public VS Code API.
   The built-in markdown preview has no confirmed channel back to the extension host, so the
   interception architecture had no foundation independent of the sanitizer problem.

## Options Considered

### Option 1: Custom URL scheme (`edf://`) — rejected

Diagram participants link to `edf://src/lib/auth/helper.ts`; a VSCode extension registers a
handler and intercepts clicks and hovers.

- **Pros:** Unambiguous namespace — an `edf://` link is self-evidently ours. Decouples the
  link from repository layout. Enables rich behaviour (hover preview, open-beside) that plain
  links cannot express.
- **Cons:** **Does not work.** Mermaid's sanitizer strips it before rendering, in every
  diagram type. Even had it survived, it would be inert for every reader without the
  extension — external contributors reviewing in a GitHub PR, anyone not using VSCode.
- **Verdict:** Rejected on evidence, not preference.

### Option 2: Absolute repository URLs

Participants link to `https://github.com/<org>/<repo>/blob/main/src/lib/auth/helper.ts`.

- **Pros:** Survives the sanitizer. Resolves in any renderer, including ones with no notion
  of a workspace. Unambiguous about which repository and which revision is meant.
- **Cons:** Bakes the host, organisation, repository name, and branch into every diagram in
  every LLD. Breaks on fork, rename, host migration, or default-branch change — silently, as
  a 404 rather than an error. Does not resolve to the local working copy, so a reviewer
  reading in VSCode is sent to a browser showing possibly-different code. Pins `main` while
  the reviewer reads a feature branch, which is precisely when the two diverge.
- **Verdict:** Rejected. It trades a correctness problem for a maintenance and accuracy
  problem, and the accuracy problem is worst exactly during review.

### Option 3: Workspace-relative paths, with `#LLD-` fragments for new components — chosen

Participants representing existing code link to a repo-relative path
(`src/lib/auth/helper.ts` — no leading slash, no `..` segments). Participants representing
components this LLD introduces link to a `#LLD-<epic-id>-<section-slug>` fragment resolving
to their Part B specification.

- **Pros:** Both forms survive the sanitizer, verified. Both resolve through each renderer's
  own native behaviour — GitHub resolves relative links against the document's location and
  handles page-internal fragments; VSCode's preview scrolls to fragments. **No extension is
  required for any of it.** Survives fork, rename, and branch change, because the path is
  relative to the document that contains it. A reviewer on a feature branch sees that
  branch's code.
- **Cons:** Constrained by Mermaid's per-type `click` support, so some participants cannot
  carry a link at all (see the matrix below). Relative resolution depends on the document's
  own location, so moving an LLD between directories invalidates its links. A path pointing
  at a deleted file fails silently.
- **Verdict:** Chosen.

### Option 4: No diagram links; prose cross-references only

- **Pros:** Nothing to break, no renderer dependency, no support matrix.
- **Cons:** This is the status quo the whole capability exists to fix. It leaves the reviewer
  grepping.
- **Verdict:** Rejected, but worth recording as the baseline any of the above must beat.

## Decision

**Option 3.** Diagram participants carry workspace-relative paths for existing code and
`#LLD-` fragments for new components, governed by an explicit per-diagram-type support
matrix.

### Link forms

| Target | Form | Example |
|---|---|---|
| Existing source file | Workspace-relative path | `src/lib/auth/helper.ts` |
| Component specified in Part B | Anchor fragment, ADR-0026 format | `#LLD-v1-e1-review-command` |

A path form carries **no leading slash and no `..` segments**. Both constraints matter for
the same reason: an absolute or escaping path can still resolve on the author's own machine
while breaking for every other reader — the identical failure mode to `edf://`, just quieter.

### Support matrix

This matrix is normative. It is not a style guide; two of its rows describe behaviour that
breaks documents.

| Diagram type | `click` support | Rule |
|---|---|---|
| `flowchart` | Yes | Emit `click X href "<path-or-fragment>" _self` |
| `classDiagram` | Yes | As above. An identifier containing `/` is a parse error — use a display label, `class EngineScoring["engine/scoring"]` |
| `stateDiagram-v2` | Yes, with caveat | Emit **without** the `_self` target — supplying one is a parse error |
| `erDiagram` | Parses, no anchor | Emit nothing. Mermaid generates no link, so a directive adds no navigability |
| `sequenceDiagram` | **Fatal parse error** | Emit nothing, in any form. A `click` here takes down the entire diagram, not just the link |

The sequence-diagram `link` directive (`link API: source @ <url>`, distinct syntax from
`click`) is **not** used. It was tried with `edf://` during V1.0 and caused problems, which
is consistent with the sanitiser finding above. It is not re-evaluated with a
workspace-relative path in V1: the Structural Overview already provides a click path to the
same components, so the payoff would be redundant navigation.

Participants appearing only in a `sequenceDiagram` are reached through the accompanying
`classDiagram` or `flowchart` in the section's Structural Overview. Where no such diagram
exists, the participant has no click path in V1 and remains reachable by ordinary document
navigation. This is an accepted limitation, not an oversight.

### Verification obligation

The matrix is a claim about an external system at a pinned version. It is therefore recorded
with the versions it was measured against, and **a change to the pinned Mermaid or VS Code
version invalidates it and requires re-measurement**. Without that trigger the matrix decays
into exactly what it replaced: a confident assertion from memory.

## Consequences

### Positive

- **The baseline needs no extension.** Every reader gets working links — GitHub PR reviewers,
  external contributors, non-VSCode users. This is a stronger guarantee than the "graceful
  degradation" the earlier design aimed at, which promised only that broken links would be
  harmless.
- **The framework stops depending on a client it does not control.** Navigability is now a
  property of the document, so an LLD is fully navigable the moment it is committed.
- **The support matrix is mechanically checkable.** "No `click` in a `sequenceDiagram`" is a
  grep, so the self-critique gate can enforce it rather than relying on author discipline.
- **Parse checks can be ordered before navigability checks**, because the matrix distinguishes
  fatal from cosmetic. A document that does not render cannot usefully be assessed for dead
  labels.

### Negative

- **Not every participant can be linked.** Sequence-diagram participants are unreachable by
  click, which weakens the "no dead labels" principle to "no dead labels within the types that
  support links". The principle is narrower than it first appears, and saying so is better
  than quietly failing to meet it.
- **Relative links are position-dependent.** Moving an LLD between directories breaks its
  source links. Mitigated by ADR-0036's version-folder convention, which makes moves rare.
- **Deleted-file links fail silently.** Mitigated by the self-critique gate's file-existence
  check, which is why that check is not optional.

### Neutral

- **Hover preview and open-beside are given up** for now. They were never delivered — they
  depended on an API that does not exist — so nothing working is being lost. If they return,
  they must be rebuilt against a custom webview panel rather than the built-in preview.
- **This ADR supersedes nothing.** ADR-0038 was rejected before any artefact depended on it,
  so its contents bind nothing. This is a first decision, not a replacement.

## References

- [ADR-0038](0038-extension-architecture-security-model.md) — Rejected. Its rejection note is
  the empirical record this decision rests on, and it defers this ADR to the `/kickoff` gate
- [ADR-0026](0026-stable-ids-requirements-lld.md) — the `LLD-<epic-id>-<section-slug>` anchor
  format used by the fragment link form
- [ADR-0036](0036-document-organisation-convention.md) — version-scoped design folders, which
  bound how often relative links are invalidated by moves
- [v1-design.md](../design/v1/v1-design.md) — §C4 (renderer-native navigable surface), §C2.5
  (renderer constraints), §C2.8 (host renderer, per-renderer verification status)
- [v1-requirements.md](../requirements/v1-requirements.md) — Stories 1.4, 1.5; Design
  Principles 1 and 3
