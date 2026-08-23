# Session log — EDF-50

## Approach rationale

- **Issue:** #50 — "v1-e1-2: Insert Review Comment command, target resolution and output channel",
  Task 3 of epic E1.2 (#30). Branch `feat/insert-review-command` in worktree
  `engineering-delivery-framework-feat-50-insert-review-command`.
- **Approach chosen:** register `edf-review.insertReviewComment` per the LLD §2.3 Part B
  decomposition. Three new/changed `src/` modules: `editor-tracker.ts` (bounded MRU stack of
  markdown editors — deduped on focus, cap 5, closed documents pruned via
  `onDidCloseTextDocument` — plus title-first + MRU `resolveTarget`), `log.ts` (an `EDF Review`
  output channel wrapper), and `extension.ts` (command registration + the `insertReviewComment`
  orchestration: resolve → extract headings → quick-pick → single-edit insertion with cursor
  placement/focus). The two pure modules from #49 (`extractHeadings`,
  `findReviewInsertLine`/`REVIEW_MARKER`) are consumed unchanged.
- **LLD deviations:** (1) quick-pick label includes the `## `/`### ` level prefix
  (`'#'.repeat(h.level) + ' ' + h.text`) rather than the LLD Part B's literal `label = heading.text`
  — the wireframe (`vis-review-comment-insertion.html`) and the BDD "lists ## and ### headings"
  both show the level marker, and it is the only field QuickPick matches on (case-insensitive),
  so without it a `##` vs `###` heading is indistinguishable. (2) `insertReviewComment` is
  exported (LLD shows it module-private) so the integration specs can inject a deterministic
  tracker/log; same for the message constants, which the LLD already says specs assert against.
  No behaviour change — the module's `main`-visible surface (`activate`/`deactivate`) is
  unchanged. (3) — 0.6 only, removed by 0.7: the intermediate design threaded a `log` parameter
  beyond the LLD's `resolveTarget(tracker, activeTab)` signature; 0.7 restores the 2-param
  signature and moves logging into the command handler (see the 0.7 section). (4) The markdown
  preview tab is detected by duck-typing `viewType === 'markdown.preview'` on `tab.input` —
  `@types/vscode` 1.88 ships no `TabInputWebviewPanel`, so the LLD's `TabInput.WebviewPanel`
  reference is matched structurally at runtime. (5) The intermediate 0.5 `correctForPreviewTab`
  hybrid-correction step was superseded by the 0.6 title-first + MRU redesign (LLD commit
  `a18503c`); the 0.6 design was itself superseded by the coordinator's 0.7 never-guess revision
  (LLD commit `a287750`) — see the 0.7 section below.
- **Pressure:** standard — ~130 source lines across 3 source files (2 new, 1 modified); 2 new
  test files. Under the Step 3c table this is the Standard track.

## Concerns & Deferred Items

- **Coverage gap (delegated, not asserted):** case-insensitive quick-pick filtering (LLD §2.3
  "filters the list case-insensitively") is delegated to VS Code's built-in QuickPick matching
  and is not independently asserted in the integration specs. `matchOnDetail: false` keeps the
  `line N` description out of the match so only the label participates. Accepted — re-asserting
  VS Code's own matching in the host is brittle and adds no contract value.
- **Coverage gap (by design):** no `executeCommand` end-to-end test. The handler is exercised
  through its direct-call form with injected deterministic tracker/log; the command's
  registration surface is covered by the scaffold spec "exposes no command other than those
  declared in the manifest". An end-to-end `vscode.commands.executeCommand` test would exercise
  the real tracker (focus-dependent) and be non-deterministic in the shared host.
- **Test-host event constraints (0.6):** the @vscode/test-electron host never fires
  `onDidCloseTextDocument` (no close command closes an API-opened document — `closeActiveEditor`,
  `closeAllEditors`, `closeAllGroups` all leave `isClosed === false`) and never re-presents an
  already-focused editor (each `showTextDocument` mints a new `TextEditor`; `editor.show()` fires
  `onDidChangeActiveTextEditor` with `undefined`; tab-switch commands fire nothing). The
  tracker's dedupe and closed-document-prune branches are therefore exercised deterministically
  by stubbing the two event sources and invoking the captured handlers directly
  (`stubTrackerEvents` in `resolution.test.ts`) — the same monkey-patch pattern the `createLog`
  spec uses for `createOutputChannel`. Real-host integration coverage is retained for the focus
  path ("tracks the most recently focused markdown editor", "does not track non-markdown
  editors").
- **Evaluator verdict: PASS WITH WARNINGS** (Step 6b). All LLD §2.3 contract properties covered;
  warnings are the two delegated/structural gaps above. The evaluator wrote **5 adversarial
  tests** (above the note threshold) in `command-wiring.eval.test.ts` covering properties the
  test-author's files did not assert: runtime half of the palette AC (`activate` actually
  registers `edf-review.insertReviewComment`), LLD Invariant 18 (source tree reads nothing via
  `workspace.fs`/`readFile`/`fetch`/`child_process`), and three §2.3 error-table rows (closed
  tracked editor → visible fallback; closed tracked + no visible → `none` naming the tracker;
  `editor.edit` returning `false` → log + message, no retry, no cursor move, no refocus).
  **Process feedback:** the test-author sub-agent prompt should be tightened to require
  coverage of the LLD's error-handling table and the invariant block, not just the BDD happy
  paths.
- **PR review (Step 9):** `edf:pr-review` on PR #73 found **3 warnings, 0 blockers**, all
  triaged to resolution:
  1. **CRLF line endings** (bug/warn, `extension.ts` `applyMarker`) — the insert hard-coded
     `'\n'`, producing a mixed line-ending edit on CRLF markdown (the norm on Windows). Fixed:
     the inserted newline now honors `editor.document.eol`. Regression test added.
  2. **Stale heading index** (bug/warn, `extension.ts`) — headings extracted before the
     quick-pick; if the document shrank while the pick was open, `findReviewInsertLine` returns
     the stale index unchanged and `Position(at + 1, 0)` would throw an unhandled RangeError.
     Fixed: `applyMarker` guards `at + 1 > lines.length`, logging "selected heading no longer
     exists in the document" + `showErrorMessage`. Regression test added.
  3. **Deviation-form** (warn) — `applyMarker` threads a `log` parameter beyond the LLD's
     prescribed `applyMarker(editor, headingLine)` signature, needed to implement the LLD's own
     `editor.edit`-false error-table row. Documented: `Justification:` comment in code + PR body
     Design deviations bullet.
- **PR review re-run (Step 9, post-0.6):** after force-pushing the 0.6 title-first + MRU code,
  `edf:pr-review` re-ran on PR #73 (285 source diff lines → 2-agent path: Quality + Design
  Conformance). **0 blockers, 3 warnings**, posted as a PR comment — triaged, none blocking the
  0.6 spec the coordinator required:
  1. **No-trailing-newline insert** (bug/warn, `extension.ts`) — when the selected heading (or
     the last consecutive marker) is the final content line and the document lacks a trailing
     newline, `Position(at + 1, 0)` is end-of-document and the marker is appended onto the
     heading line. Edge case (markdown conventionally ends with a newline); the stale-heading
     guard from the prior review is unaffected. **Deferred** — LLD does not specify; raise at
     feature-end triage.
  2. **Cold-start tracker** (bug/warn, `editor-tracker.ts`) — `activationEvents` is empty, so on
     the very first command invocation the tracker is empty and `resolveTarget` returns `none`
     when ≥2 markdown editors are visible but none is a focused preview. This is the LLD 0.6
     contract exactly (`resolveTarget` has no `activeTextEditor` fallback); an added fallback
     would deviate from the spec the coordinator mandated. **Deferred as an LLD-level limitation**
     — surfaces only until the user switches tabs once.
  3. **Test-harness duplication** (maintainability/warn) — the three test files re-implement
     small stubs (`settle`, `stubQuickPick`, `closedEditor`, …) rather than sharing a helper
     module. **Deferred** — consistent with the existing suite's self-contained test-file style;
     a shared helper module is a refactor, not a correctness fix.
  Design Conformance agent returned no findings (all implemented functions match the LLD 0.6
  designed list; every deviation is documented in the PR body).

## 0.7 (never guess) revision — supersedes 0.6

Coordinator's design revision applied exactly to PR #73 (spec: LLD `a287750` §2.3 and issue #50
body). Rebased the branch onto `origin/main` (LLD 0.7) so the PR carries the authoritative spec.

- **New chain, no fallbacks, never guess:** the focused markdown preview is the ONLY legitimate
  trigger. `resolveTarget(tracker, activeTab)`:
  1. `name = previewTitleName(activeTab)`; `!name` → `{ kind: 'none', reason: NO_PREVIEW_MSG }`
  2. `matches = mruMatchesForName(tracker, name)` — still-open MRU entries whose document
     basename equals the preview title's basename, in recency order
  3. `matches.length === 1` → `showTextDocument(matches[0].document, { preview: true,
     preserveFocus: true })` → `{ kind: 'resolved', editor }`
  4. `matches.length === 0` → `{ kind: 'none', reason: NO_DOCUMENT_MSG }`
  5. `matches.length > 1` → `showWarningMessage(AMBIGUOUS_MSG(name))` → `{ kind: 'none',
     reason: AMBIGUOUS_MSG(name) }` — never guess on ambiguity
- **`uniqueDocumentForName` → `mruMatchesForName`:** candidates now come from the bounded MRU
  stack (cap 5, deduped on focus, pruned on close), not `workspace.textDocuments`. A document
  evicted from the stack is not found (zero matches → `NO_DOCUMENT_MSG`). `Resolution` drops the
  `'visible'` kind; the MRU-walk and single-visible-editor fallbacks are removed.
- **Message constants** moved to `src/editor-tracker.ts` (where `resolveTarget` uses them):
  `NO_PREVIEW_MSG`, `NO_DOCUMENT_MSG`, `AMBIGUOUS_MSG(name)`; `NO_HEADINGS_MSG` stays in
  `extension.ts`. `extension.ts` no longer owns `NO_DOCUMENT_MSG` (the handler shows
  `res.reason`).
- **Handler:** on `kind === 'none'` → `log(res.reason)` then `showWarningMessage(res.reason)`
  (one call site, reason is the user-facing string). `resolveTarget`'s 0.6 `log` param is
  dropped — logging moved to the handler.
- **Tests:** `resolution.test.ts` rewritten to the issue's five-spec BDD (unique title match →
  resolved; non-preview tab → `NO_PREVIEW_MSG`; ambiguous basename → warn + stop; zero match →
  `NO_DOCUMENT_MSG`; failure → reason logged to `EDF Review`). `mruMatchesForName` specs added.
  `command-wiring.eval.test.ts` reworked: the removed `visible`/MRU-walk branches are replaced by
  0.7 closed-entry properties (closed entry never shadows an open match; only matching entry
  closed → `NO_DOCUMENT_MSG`), and the `editor.edit`-false spec's fake editor now carries a URI
  matching a stubbed preview title (0.7 always reveals via `showTextDocument` on resolve).
- **Test-host discovery:** `vscode.window.tabGroups` is a getter-only accessor — it cannot be
  assigned (assignment throws "has only a getter"). It is overridden with
  `Object.defineProperty(vscode.window, 'tabGroups', { value: …, configurable: true })` and
  restored by re-applying the captured descriptor. Every insertion spec stubs the active tab to a
  `markdown.preview` titled `Preview <basename>` matching the injected editor's file, because 0.7
  never reaches the quick-pick without a focused preview.
- **Deviations / quirks (documented, non-blocking):**
  - `applyMarker` retains the pr-review #73 hardening (`log` param, stale-heading guard, EOL
    honouring) — the 0.7 directive did not touch it, so the improvements from review finding #73
    are preserved.
  - **Ambiguous-case double message (spec-inherited):** the LLD's step 5
    `showWarningMessage(AMBIGUOUS_MSG(name))` is implemented literally inside `resolveTarget`,
    and the handler's none-branch also shows `showWarningMessage(res.reason)`. The ambiguous case
    therefore surfaces the warning twice in the full handler path. No spec exercises the handler
    with an ambiguous tracker, so the suite stays green; if the coordinator prefers the handler to
    be the single message site, removing the inline step-5 call is a one-line change. The BDD
    "warns to close the wrong document" is asserted at the `resolveTarget` level (one call), which
    is where the coordinator's step-6 test placement locates it.

## Cost checkpoints

| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-08-22T18:19:33Z | $0.00 | 0 in / 0 out | pressure: standard — ~130 src lines across 3 source files |
| 4bF | 2026-08-22T18:36:44Z | $0.00 | 0 in / 0 out | test-author complete — 15 BDD properties, all covered (2 delegated) |
| 4dF | 2026-08-22T18:37:03Z | $0.00 | 0 in / 0 out | implementation complete — 43 tests green in host (14 new) |
| 5 | 2026-08-22T18:37:52Z | $0.00 | 0 in / 0 out | green on attempt 1 — 43 tests in extension host; npm audit 0 vulns; no E2E (n/a per kb) |
| 6 | 2026-08-22T18:38:42Z | $0.00 | 0 in / 0 out | diag: diagnostics-exporter skipped (worktree, no .diagnostics); CodeScene/SonarQube MCP unavailable; tsc strict clean |
| 6b | 2026-08-22T18:48:00Z | $0.00 | 0 in / 0 out | evaluator: PASS WITH WARNINGS — 5 adversarial tests written, all pass; AC5 filter delegated to native widget |
| 8 | 2026-08-22T18:50:40Z | $0.00 | 0 in / 0 out | [PR #73](https://github.com/mironyx/engineering-delivery-framework/pull/73) |
| 0.6 rework | 2026-08-22T23:47:00Z | $0.00 | 0 in / 0 out | LLD → 0.6 title-first + MRU (`a18503c`); tracker rewritten to bounded MRU stack, resolveTarget title-first; suite green 58 passing, 0 failing (4 new resolution specs: title-first, MRU walk, newest-closed fallback, closed-doc eviction) |
| 9 (re-run) | 2026-08-23T00:00:00Z | $0.00 | 0 in / 0 out | [pr-review re-run](https://github.com/mironyx/engineering-delivery-framework/pull/73#issuecomment-5383239946) — 285 src diff lines → 2 agents; 0 blockers, 3 warnings (all deferred, see Concerns) |
| 10 | 2026-08-23T00:01:00Z | $0.00 | 0 in / 0 out | CI reconciled synchronously — `gh pr checks 73` reports no checks (no Actions workflows); external Comprehension Check not awaited per task; PR #73 head `82f9862` reports 0.6 code; suite 58 passing |
| 0.7 rework | 2026-08-23T17:50:00Z | $0.00 | 0 in / 0 out | coordinator 0.7 never-guess revision applied exactly — rebased onto LLD `a287750`; `uniqueDocumentForName`→`mruMatchesForName`, `Resolution` drops `visible`, `resolveTarget` 2-param never-guess chain, handler logs+shows `res.reason`; resolution.test.ts rewritten to the 5-spec BDD; eval reworked for removed branches; `tabGroups` stub via `defineProperty`; suite green 58 passing, 0 failing |
| 9 (re-run, 0.7) | 2026-08-23T17:55:00Z | $0.00 | 0 in / 0 out | `edf:pr-review` re-run on PR #73 (0.7 head, force-pushed); source diff line count recomputed |
| 10 (0.7) | 2026-08-23T17:56:00Z | $0.00 | 0 in / 0 out | CI reconciled — `gh pr checks 73` reports no checks; PR #73 head re-confirmed after `--force-with-lease`; suite 58 passing |
