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
| 9 (re-run, 0.7) | 2026-08-23T18:00:00Z | $0.00 | 0 in / 0 out | [pr-review re-run](https://github.com/mironyx/engineering-delivery-framework/pull/73#issuecomment-5387620050) — 267 src diff lines → 2 agents (Quality + Design Conformance); 0 blockers, 5 warns: W1 marker-glue off-by-one → FIXED (`02ca524`), W2 AMBIGUOUS_MSG double-show → accepted (spec-inherited), W3 cold-start empty MRU stack → open (spec deviation, deferred to coordinator), W4 test-host helper duplication → accepted (follow-up), W5 `applyMarker` Justification gap → FIXED (`02ca524`) |
| 10 (0.7) | 2026-08-23T18:01:00Z | $0.00 | 0 in / 0 out | CI reconciled — `gh pr checks 73` reports no checks (no Actions workflows); PR #73 head `02ca524` after `--force-with-lease`, MERGEABLE, OPEN; suite 59 passing, 0 failing (+1 no-trailing-newline regression test for W1); cost checkpoint EDF-50 $0.00 / 0 tokens |
| 0.8 delta | 2026-08-23T18:20:00Z | $0.00 | 0 in / 0 out | LLD 0.8 (main `57f8dee`, approved by maintainer): `createEditorTracker` seeds the bounded MRU stack from `visibleTextEditors` at activation (markdown-only, cap applies) so a first command run after lazy activation finds an editor opened before the extension was alive; `NO_DOCUMENT_MSG` reworded to `Open the original markdown file in VS Code, then retry` (reachable zero-match cases are a closed source editor or eviction — not a dead end). 2 new seed specs; rebased onto `57f8dee`; suite 61 passing, 0 failing |

## Work completed

Final state delivered by PR #73 (head `6ccb834`): the `edf-review.insertReviewComment` command
with the LLD 0.8 never-guess target resolution and the `EDF Review` output channel.

- **Command + orchestration** (`extensions/edf-review/src/extension.ts`): `activate` registers
  `edf-review.insertReviewComment`; `insertReviewComment(tracker, log)` runs the
  resolve → extract-headings → quick-pick → single-edit pipeline; `applyMarker` ships the review
  hardening (log param, stale-heading guard, EOL-honouring newline, end-of-document separator).
- **Target resolution** (`extensions/edf-review/src/editor-tracker.ts`): `createEditorTracker`
  maintains a bounded MRU stack of markdown editors (cap 5, deduped on focus, pruned on close),
  **seeded from `visibleTextEditors` at activation** (LLD 0.8); `resolveTarget(tracker, activeTab)`
  resolves the focused markdown preview's title to exactly one open basename match, else stops
  with `NO_PREVIEW_MSG` / `NO_DOCUMENT_MSG` / `AMBIGUOUS_MSG` — never guesses.
- **Output channel** (`extensions/edf-review/src/log.ts`): `EDF Review` output channel wrapper;
  `createLog` injectable for specs.
- **Tests** (61 passing, 0 failing in the @vscode/test-electron host): `resolution.test.ts`
  (5-spec BDD + seed specs), `command.test.ts` (insertion incl. no-trailing-newline + CRLF +
  stale-heading regressions), `command-wiring.eval.test.ts` (5 evaluator adversarial specs),
  scaffold spec. No E2E (n/a per kb); `tsc --noEmit` strict clean.
- **Docs:** LLD synced to 0.9 (§2.3 decomposition + Implementation note); coverage manifest
  entry flipped to Revised; `kb/anti-patterns.md` gained a VS Code section.
- **PR:** https://github.com/mironyx/engineering-delivery-framework/pull/73

## Decisions made

- **Never guess (LLD 0.7, coordinator-approved):** the focused markdown preview is the ONLY
  trigger; ambiguous basenames warn and stop rather than guessing. Adopted exactly per LLD
  `a287750`.
- **Cold-start seed (LLD 0.8, maintainer-approved):** the tracker seeds its MRU stack from
  `visibleTextEditors` at activation (markdown-only, cap applies), so a first command run after
  lazy activation resolves an editor already open before the extension loaded.
- **Zero-match message reword (LLD 0.8):** `NO_DOCUMENT_MSG` is "Open the original markdown file
  in VS Code, then retry" — the reachable zero-match cases (closed source editor, evicted from
  the MRU) are a prompt to act, not a dead end.
- **Quick-pick label carries the level prefix** (`'#'.repeat(h.level) + ' ' + h.text`): the LLD
  Part B said `label = heading.text`, but the wireframe and the "lists ## and ### headings" BDD
  both show the level marker, and it is the only field QuickPick matches on — without it `##` vs
  `###` headings are indistinguishable. Synced back into the LLD (0.9).
- **`applyMarker` hardening retained** across the 0.6→0.7→0.8 rewrites: the `log` parameter (to
  implement the LLD §2.3 "editor.edit returns false" error-table row), the stale-heading guard
  (fail explicitly rather than throw a RangeError when the document shrank while the pick was
  open), the EOL-honouring newline (CRLF documents must not gain a mixed line-ending edit), and
  the end-of-document separator (heading as final line with no trailing newline must not glue the
  marker onto the heading text).
- **Ambiguous double-show is spec-inherited:** LLD step 5 shows the warning inside
  `resolveTarget` and the handler's none-branch shows `res.reason` again, so the ambiguous case
  surfaces twice in the full path. No spec exercises the handler with an ambiguous tracker;
  removing the inline step-5 call is a one-line change if a future coordinator prefers a single
  message site.
- **Test-host constraints worked around:** `vscode.window.tabGroups` is getter-only → stubbed via
  `Object.defineProperty` and restored by re-applying the captured descriptor; the host never
  fires `onDidCloseTextDocument` → the tracker's prune branch is exercised by stubbing the event
  sources and invoking the captured handlers directly.

## Review feedback addressed

- **Finding #73 (edf:pr-review, 0 blockers / 3 warns) — all fixed:**
  1. CRLF mixed line endings in `applyMarker` → inserted newline honours `editor.document.eol`;
     regression test added.
  2. Stale heading index → `applyMarker` guards `at + 1 > lines.length`, logs "selected heading
     no longer exists in the document" + `showErrorMessage`; regression test added.
  3. `applyMarker` signature divergence (log param) → documented in a `Justification:` comment
     and the PR body Design deviations.
- **0.7 re-review (0 blockers / 5 warns):**
  - W1 marker-glue off-by-one → **fixed** (`02ca524`) with an end-of-document separator; added
    the no-trailing-newline regression test.
  - W2 AMBIGUOUS_MSG double-show → accepted, spec-inherited (see Decisions).
  - W3 cold-start empty MRU stack → **resolved by LLD 0.8** (seed from `visibleTextEditors`).
  - W4 test-helper duplication → accepted, deferred (a shared helper module is a refactor, not a
    correctness fix).
  - W5 `applyMarker` Justification gap → **fixed** (`02ca524`) with an expanded comment.
- **0.8 delta:** the two review bugs (mixed line endings, stale heading index) are the basis of
  the new "VS Code (edf-review extension)" section in `kb/anti-patterns.md`.

## LLD Sync report

`edf:lld-sync 50` — target: `docs/design/v1/lld-v1-e1-2-review-feedback.md` (§2.3 command-wiring),
coverage manifest `coverage-v1-e1-2.yaml`, kb.

### Corrections (spec was wrong)

- §2.3 `toItems` quick-pick label: LLD said `label = heading.text`; built emits
  `'#'.repeat(heading.level) + ' ' + heading.text` — the level prefix is the only field the
  quick-pick matches on (case-insensitive), and without it `##` vs `###` headings are
  indistinguishable. The deviation was documented in the PR body but never captured in the LLD.
- §2.3 `applyMarker` internal decomposition: LLD said `applyMarker(editor, headingLine)` inserting
  `REVIEW_MARKER + '\n'`; built ships `applyMarker(editor, headingLine, log)` with (a) a
  stale-heading guard that logs + shows an error + returns instead of throwing a RangeError, (b)
  an EOL-honouring newline (`'\r\n'` when `document.eol === CRLF` — a hard-coded `'\n'` produced
  a mixed line-ending edit on CRLF markdown), and (c) an end-of-document separator when the
  heading is the final line and the file has no trailing newline (otherwise the marker glues onto
  the heading text).

### Additions (not in spec)

- §2.3 Implementation note callout (issue #50) added below the message constants documenting the
  three `applyMarker` divergences and their rationale (the "editor.edit returns false" error-table
  row; fail-closed on a stale heading; EOL + separator for line-ending hygiene).

### Omissions (in spec but not built)

- None. The case-insensitive quick-pick filter AC is delegated to the native VS Code QuickPick
  matching (a host-side re-implementation would be brittle and add no contract value); the two
  ADR-0035 wireframe PNGs are captured in the PR.

### Confirmations (notable)

- The LLD 0.8 never-guess resolution chain was built exactly as specified: single-preview-title
  trigger; `mruMatchesForName` by basename over the seeded, capped MRU stack; 0 matches →
  `NO_DOCUMENT_MSG`, 1 → resolve via `showTextDocument(doc, { preview: true, preserveFocus: true })`,
  >1 → `AMBIGUOUS_MSG` warn + stop, no preview → `NO_PREVIEW_MSG`. Message constants match the
  LLD verbatim.
- The ambiguous double-show is a faithful implementation of LLD step 5, including its
  double-display quirk (see Decisions).

### Knowledge base

- `kb/anti-patterns.md`: added "### VS Code (edf-review extension)" with two patterns from review
  finding #73 — mixed line endings (insert `'\r\n'` when `document.eol === CRLF`) and a
  positional heading index captured before a modal UI and re-used after it without a version
  guard (re-read the document and fail explicitly).

### LLD updated

File: `docs/design/v1/lld-v1-e1-2-review-feedback.md` §2.3
Version: 0.8 → 0.9 (Status Revised v6 → Revised v7; Document Control `Revised` row added)

## Cost retrospective

All 13 `## Cost checkpoints` rows report `$0.00 / 0 tokens` (cumulative). Prometheus cost
telemetry was unavailable for this feature — the extension host never emitted the checkpoint
metrics the EDF cost pipeline reads, so there is no data-backed breakdown of where spend accrued.
The final query (`query-feature-cost.py --issue 50 --pr 73 --stage final`) returned
`$0.0000 / 0 in / 0 out`, time-to-PR 38 min, and applied `ai-cost-final:0.0000` +
`input/output-tokens-final:0` to issue #50 and PR #73.

- **Cost drivers (qualitative):** the visible cost drivers were context turns and review cycles,
  not tokens — the target-resolution contract moved three times while the branch was open
  (0.6 title-first + MRU → 0.7 never-guess → 0.8 seed + message reword), each requiring a rebase,
  a test rewrite, and a pr-review re-run (3 review rounds on PR #73). The only code-level fix
  cycle (W1 marker-glue off-by-one) was caught in re-review, not by the host.
- **Improvement actions:**
  1. Keep the LLD resolution design frozen once a branch is open; each 0.x redesign cost a full
     test-suite rewrite. The final never-guess shape (0.7) and its seed (0.8) should have been
     settled before implementation started.
  2. Add no-trailing-newline + CRLF insert cases to the test-author contract checklist — both
     were review-caught, not test-author-caught (the evaluator's process feedback about the
     error-table gap covers the mechanics; line-ending hygiene deserves its own row).
  3. The new `kb/anti-patterns.md` VS Code section lands these two review-caught bugs so the next
     extension PR is checked for them up front.

## Next steps

- **Deferred from review (accepted):** W4 test-helper duplication — extract a shared
  stub/settle helper module in the extension test suite (refactor, not correctness); optional
  follow-up.
- **Ambiguous double-show:** if the coordinator prefers a single message site for the AMBIGUOUS
  case, remove the inline step-5 `showWarningMessage` in `resolveTarget` (one-line change).
- **Suggested next board item:** the remaining Wave 3 tasks of epic E1.2 (#30) are
  [#51 v1-e1-2: vsix packaging, install verification and recorded security review] and
  [#63 v1-e1-2: diagram click-through navigation via previewScripts overlay]. #51 is the natural
  next pick (packaging is the gate for installing and verifying the shipped artifact); #63
  completes the previewScripts overlay story. Both are `kind:task` and currently open.
