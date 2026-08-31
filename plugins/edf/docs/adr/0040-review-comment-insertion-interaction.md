# 0040. Review Comment Insertion — Line-Based Interaction, with Known Open Defect

**Date:** 2026-08-31
**Status:** Accepted
**Deciders:** LS / Claude

## Context

Epic 1.2 (`v1-e1-2`, issue #30) ships the VSCode extension that closes the
preview→source round-trip for review comments. The original design — recorded in
[requirements Story 2.1](../../requirements/v1-requirements.md#REQ-vscode-extension-review-feedback-quick-pick-insert-review-comment)
and [HLD C2.4](../design/v1/v1-design.md#c24-review-comment-command) — was a **quick-pick**:
the command presented a filterable list of `##`/`###` headings extracted from the document,
and on selection inserted a `> **[Review]:** ` marker under that heading.

Two things diverged from that design during implementation, and both need recording so the
design documents do not claim behaviour that does not exist:

1. **The quick-pick was removed.** Review feedback during Task 3 (issue #50) redirected the
   interaction to a **line-based insert**: the marker is inserted below the line the reviewer
   means — the clicked preview line when the preview holds focus, else the source cursor line
   — with no heading list at all (shipped as edf-review 0.2.9).
2. **The line-based insert does not reliably land the marker where the reviewer means.**
   Measured in real use, the marker can land at the end of the file. This is a known open
   defect, and the robust fix is unimplemented. See the research finding below.

What *does* work, and is not in question:

- **Diagram click-through** works through the native VSCode preview click handling, bridged
  by the `markdown.previewScripts` overlay (ADR-0039 §Revision R5). The overlay lays a real
  HTML `<a>` over each SVG click target; the *existing* built-in handler opens it per the
  workspace settings `.vscode/settings.json` (`markdown.preview.openMarkdownLinks: "inEditor"`,
  `markdown.links.openLocation: "beside"`).
- **Target resolution no longer requires close-and-reopen.** `resolveTarget`
  ([`editor-tracker.ts`](../../../extensions/edf-review/src/editor-tracker.ts)) resolves the
  preview title through the bounded MRU stack, falling back to the **live** visible-editor set
  (0.2.10) so an editor opened without focus is still found.

This ADR records the interaction decision and the measured finding that motivates the open
defect, following the evidence-and-revision style of ADR-0039.

## Options Considered

### Option 1: Quick-pick heading selection (original design) — rejected

The command extracts `##`/`###` headings with line numbers and presents a filterable
quick-pick; selecting one inserts the marker under that heading.

- **Pros:** Deterministic — the reviewer names the exact heading, so the marker always lands
  under the intended section. No dependence on preview↔editor scroll or cursor state.
- **Cons:** Two extra keystrokes per comment (open list, select entry). The list re-derives
  what the reviewer is already looking at — the diagram click already points at a specific
  section, and the reviewer's eyes are on the preview, not a heading list. Review feedback
  during implementation judged the round-trip heavier than inserting at the visible line.
- **Verdict:** Rejected during Task 3 (#50). Superseded by Option 2.

### Option 2: Line-based insert, cursor/visible-line inference — chosen, measured unreliable

The command inserts the marker below the line the reviewer means: the source cursor line when
the source editor is focused, else the **top-visible line** of the resolved editor
(`insertionLineFor` in [`extension.ts`](../../../extensions/edf-review/src/extension.ts)) —
on the assumption that the built-in preview scrolls the source editor so the clicked line
sits at the top of the viewport (`markdown.preview.scrollEditorWithPreview`, default on; the
`revealLine` handler uses `TextEditorRevealType.AtTop`).

- **Pros:** Zero extra steps — invoke the command and the marker lands where the review is
  happening. No quick-pick, no heading list.
- **Cons:** **The assumption is false in real usage.** A single preview click does not move
  the source cursor and does not scroll the source editor to the clicked line in this build,
  so the top-visible line is stale — often the end of the file. Markers land at the wrong
  line. See the research finding below.
- **Verdict:** Shipped (0.2.9, fixed in 0.2.10), but the defect is live and recorded in this
  ADR rather than claimed away.

### Option 3: Overlay `data-line` capture bridged to the extension host (robust fix) — deferred

The overlay already knows which diagram element was clicked (it creates the `<a>` over the
SVG target). If the LLD template stamped each section with a `data-line`, the overlay could
send that line to the extension host over the existing `overlay-bridge` channel
([`overlay-bridge.ts`](../../../extensions/edf-review/src/overlay-bridge.ts)), and the host
would insert at that exact line — no inference, no cursor state.

- **Pros:** Deterministic marker placement, independent of scroll-sync behaviour. Reuses the
  overlay that already ships for click-through.
- **Cons:** **The built-in markdown preview drops unknown `previewScripts` postMessage types.**
  Measured during §2.5 (LLD 1.1): the command hook is best-effort only — there is no
  confirmed channel from the preview webview back to the extension host in this build (the
  same `onDidReceivePreviewMessage` absence that ADR-0038's rejection note and ADR-0039 R5
  recorded). The bridge cannot be relied on to deliver the line.
- **Verdict:** Deferred. Reopen when a confirmed preview→host channel exists (custom webview,
  or a future API), per the "Deferred from V1" conditions in the requirements.

## Decision

**The V1 interaction is line-based insert with no quick-pick** (Option 2), shipped as
edf-review 0.2.9/0.2.10. The quick-pick design is removed from the command; the heading
extraction module (`headings.ts`) is no longer invoked by the command path.

**The marker-placement inference is accepted as unreliable.** The marker lands below the
inferred line — the source cursor line when the source editor is focused, else the top-visible
line — and when the preview holds focus and the click-to-scroll assumption fails, the marker
can land at the end of the file. This is a **known open defect**, recorded here rather than
hidden. The robust fix (Option 3, overlay `data-line` capture) is deferred until a confirmed
preview→host channel exists.

Diagram click-through and target resolution are not part of this decision: they work through
the native click handling + previewScripts overlay (ADR-0039 R5) and the MRU + live-visible
fallback respectively, and are unchanged.

## Research finding — why line-based insertion does not work reliably

Recorded from implementation and live testing of edf-review 0.2.9–0.2.12. This is the
rationale the user asked to be preserved in the record: *"line based does not work… we
currently just using native click setting."*

1. **A single preview click never moves the source cursor in this build.**
   `markdown.preview.markEditorSelection` is inert — it adds a CSS class to the preview
   webview's selected line, it does not move the cursor in the source editor. The source
   cursor only moves via `didClick` on a **double-click**, when the preview is configured
   with `doubleClickToSwitchToEditor` — the user rejected that flow because it yanks focus
   out of the preview and displaces the preview, which defeats the review round-trip.
2. **The `insertionLineFor` inference reads a stale signal.** With the preview focused,
   `vscode.window.activeTextEditor` is `undefined`, so the function reads
   `visibleRanges[0].start.line` (top-visible). The assumption that the preview click scrolled
   the source editor so the clicked line is at the top was measured wrong in real usage: a
   single preview click does not scroll the source editor, and when the source editor is not
   visible or not scrolled, the top-visible line is wherever the editor last was — frequently
   the end of the file. Markers land at the wrong line.
3. **The robust fix needs a preview→host channel that does not exist.** The overlay could
   capture the clicked element's line and post it to the host, but the built-in markdown
   preview drops unknown `previewScripts` postMessage types (recorded in LLD 1.1 §2.5) —
   the overlay-bridge command is best-effort only. Without a confirmed channel the data-line
   capture cannot be delivered.
4. **What does work is the native click handling.** Diagram links open their targets through
   the built-in preview handler (overlay + ADR-0039 R5), and target resolution finds the
   source editor without close-and-reopen (live visible-editor fallback, 0.2.10). The working
   half of the extension is the diagram navigability; the review-marker insertion is the
   open-defect half.

## Consequences

- **Requirements, HLD and LLD must not claim a quick-pick.** The living specs
  (`v1-requirements.md` Story 2.1, `v1-design.md` C2.4, `lld-v1-e1-2-review-feedback.md`
  §2.2/§2.3) are reconciled to the line-based interaction, with the marker-at-EOF defect
  stated, not assumed away. The REQ anchor keeps its `-quick-pick-` slug — ADR-0026 stable IDs
  forbid renaming a referenced anchor.
- **The marker-format contract survives.** `> **[Review]:** ` (`REVIEW_MARKER`,
  `review-insert.ts`) and the insert-after-existing-markers rule (`findReviewInsertLine`) are
  unchanged and correct; only the *target line* inference is unreliable.
- **`headings.ts` is orphaned.** `extractHeadings` is no longer called by the command; it
  remains with its test file until a removal decision is made. Its presence is a
  documentation artefact of the quick-pick design, not live code.
- **Diagram click-through stays on the native click setting.** The earlier security
  hardening of `overlay.js` (trim-before-scheme + leading-slash rejection) was reverted
  because it broke repo-root-relative Mermaid click links; the unhardened scheme check remains
  a documented security-debt item, not re-applied without user approval.

## References

- [ADR-0038](0038-extension-architecture-security-model.md) — Rejected. Its quick-pick
  description (Context, "command-palette action presents a filterable quick-pick") is
  superseded in part by this ADR; the ADR itself stays rejected and unopened.
- [ADR-0039 §Revision R5](0039-workspace-relative-paths-for-diagram-navigability.md) — the
  overlay mechanism that makes diagram click-through work through the native handler
- [ADR-0026](0026-stable-ids-requirements-lld.md) — the REQ anchor format; why the
  `-quick-pick-` anchor slug is not renamed
- [v1-requirements.md Story 2.1](../../requirements/v1-requirements.md#REQ-vscode-extension-review-feedback-quick-pick-insert-review-comment)
- [v1-design.md C2.4](../design/v1/v1-design.md#c24-review-comment-command)
- [lld-v1-e1-2-review-feedback.md §2.2/§2.3](../design/v1/lld-v1-e1-2-review-feedback.md)
