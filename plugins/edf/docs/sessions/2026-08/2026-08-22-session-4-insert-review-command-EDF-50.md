# Session log — EDF-50

## Approach rationale

- **Issue:** #50 — "v1-e1-2: Insert Review Comment command, target resolution and output channel",
  Task 3 of epic E1.2 (#30). Branch `feat/insert-review-command` in worktree
  `engineering-delivery-framework-feat-50-insert-review-command`.
- **Approach chosen:** register `edf-review.insertReviewComment` per the LLD §2.3 Part B
  decomposition. Three new/changed `src/` modules: `editor-tracker.ts` (continuous tracking
  of the last focused markdown editor via `onDidChangeActiveTextEditor`, plus the three-way
  `resolveTarget`), `log.ts` (an `EDF Review` output channel wrapper), and `extension.ts`
  (command registration + the `insertReviewComment` orchestration: resolve → extract headings →
  quick-pick → single-edit insertion with cursor placement/focus). The two pure modules from
  #49 (`extractHeadings`, `findReviewInsertLine`/`REVIEW_MARKER`) are consumed unchanged.
- **LLD deviations:** (1) quick-pick label includes the `## `/`### ` level prefix
  (`'#'.repeat(h.level) + ' ' + h.text`) rather than the LLD Part B's literal `label = heading.text`
  — the wireframe (`vis-review-comment-insertion.html`) and the BDD "lists ## and ### headings"
  both show the level marker, and it is the only field QuickPick matches on (case-insensitive),
  so without it a `##` vs `###` heading is indistinguishable. (2) `insertReviewComment` is
  exported (LLD shows it module-private) so the integration specs can inject a deterministic
  tracker/log; same for the `NO_DOCUMENT_MSG`/`NO_HEADINGS_MSG` constants, which the LLD already
  says specs assert against. No behaviour change — the module's `main`-visible surface
  (`activate`/`deactivate`) is unchanged.
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
