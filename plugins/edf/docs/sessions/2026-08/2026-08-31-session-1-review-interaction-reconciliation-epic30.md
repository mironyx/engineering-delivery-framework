# Session log — Epic #30 doc reconciliation (review-interaction state)

## Approach rationale

- **Issue:** epic #30 (V1 E1.2 Review Feedback), docs-only follow-on after PRs #68/#72/#73/#74/#75 merged.
- **Approach chosen:** `/architect` review mode over the V1 E1.2 design docs. Read the true shipped state from
  `extensions/edf-review/src/*.ts` (extension.ts, editor-tracker.ts, review-insert.ts, headings.ts), then reconciled
  every living spec that claimed the Review command worked as originally designed:
  - **ADR-0040** (new) records the interaction decision — the heading quick-pick was removed during Task 3 (#50) in
    favour of a line-based insert — and the measured finding that line-based inference is **unreliable** (markers can
    land at the end of the file). The user's rationale to preserve: *"line based does not work… we currently just using
    native click setting."* The robust fix (overlay `data-line` capture bridged to the host) is deferred until a
    confirmed preview→host channel exists.
  - **ADR-0038** amended with a superseded-in-part note (its Context still described the quick-pick).
  - **requirements / HLD / LLD / coverage / README** updated in place with change-log entries.
- **Historical docs untouched:** discovery, plans, prior session logs, and the LLD's historical "Recent revisions"
  entries stay as written. Only living specs and the shipped extension README were reconciled.
- **Cost:** documentation-only — no feature-track cost checkpoints apply.

## Work completed

- **`docs/adr/0040-review-comment-insertion-interaction.md`** (new, ADR-0039 style): quick-pick rejected (Option 1);
  line-based insert chosen but measured unreliable (Option 2); overlay `data-line` capture deferred (Option 3). The
  research finding is recorded in four points: (1) a single preview click never moves the source cursor in this build
  (`markdown.preview.markEditorSelection` is inert/CSS-only); (2) `insertionLineFor` reads a stale top-visible signal,
  so markers land at EOF; (3) the robust fix needs a preview→host channel the built-in preview does not provide
  (drops unknown `previewScripts` postMessage types); (4) what does work is the native click handling (overlay +
  ADR-0039 R5) and live-visible-editor target resolution (0.2.10).
- **`docs/adr/0038-extension-architecture-security-model.md`** — added "Superseded in part (2026-08-31)" note in
  Context pointing to ADR-0040; the ADR stays rejected and unopened.
- **`docs/requirements/v1-requirements.md`** — v1.5→1.6; Epic 2 intro and Story 2.1 rewritten to the line-based
  interaction (anchor keeps its `-quick-pick-` slug per ADR-0026); new ACs for live-visible fallback, cursor-or-top-
  visible insert, and the known defect; Open-Question row 4 (F13 regex extraction) marked moot.
- **`docs/design/v1/v1-design.md`** — v1.4→1.5; C2.4 purpose/responsibilities and Flow 3 sequence diagram rewritten
  to the shipped resolution fallback + `insertionLineFor` inference + known-defect note.
- **`docs/design/v1/lld-v1-e1-2-review-feedback.md`** — 1.1→1.2; Part A §2.2/§2.3 reconciled (quick-pick state
  obsolete, line-inference flow, known open defect, live fallback); Part B implementation sections rewritten to the
  shipped signatures (`insertionLineFor`, `applyMarker`, `visibleMarkdownEditorsNamed`, `editorTabName`) with
  `headings.ts` marked orphaned and the stale quick-pick constraints/error-table rows replaced.
- **`docs/design/v1/coverage-v1-e1-2.yaml`** — Story 2.1 entry comment reconciles the historical anchor slug with the
  line-based shipped state (no field changes — anchors stay valid per ADR-0026).
- **`extensions/edf-review/README.md`** — Usage section rewritten: source-focused insert is reliable, preview-focused
  insert is a stated known defect, and diagram click-through works via the native preview handling + workspace
  settings.

## Decisions made

- **The marker-format contract survives.** `> **[Review]:** ` (`REVIEW_MARKER`) and `findReviewInsertLine` are
  unchanged and correct; only the *target line* inference is unreliable. Docs say so, they do not claim it works.
- **`headings.ts` is orphaned, not deleted.** `extractHeadings` is no longer in the command path; retained with its
  test file pending a removal decision. LLD §2.2 marks it as such.
- **REQ anchor slug is historical.** ADR-0026 forbids renaming the `-quick-pick-` anchor; docs annotate rather than
  rename.
- **The overlay XSS hardening stays reverted.** The earlier trim + leading-slash rejection broke diagram click-through
  and was reverted by user choice; it remains documented security debt in ADR-0040, not re-applied without approval.
- **README was in scope.** It is a shipped, living usage doc that claimed the unreliable scroll-to-top behaviour;
  reconciled alongside the design docs.

## LLD Sync report

Skipped — no `edf:lld-sync` run. This session *is* the LLD reconciliation: the LLD was updated in place (revision
1.2, its own change-log entry) rather than through the post-implementation sync agent. Coverage manifest comments
updated to match.

## Next steps

- Open question for the user: whether to schedule the robust fix (ADR-0040 Option 3, overlay `data-line` capture) for
  V2 once a confirmed preview→host channel exists, and whether to remove orphaned `headings.ts` + its test file.
