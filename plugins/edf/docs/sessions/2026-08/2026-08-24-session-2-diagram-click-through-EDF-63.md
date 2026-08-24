# Session log — [EDF-63]

## Approach rationale
- **Issue:** #63
- **Approach chosen:** Re-add `contributes.markdown.previewScripts` → `./media/overlay.js`; a plain-DOM webview script overlays a real HTML `<a>` over each Mermaid SVG click target's bounding box (carrying the same href), kept in sync across scroll/resize/re-render via a MutationObserver scoped to `svg[id^="mermaid"]` plus scroll/resize listeners. `src/overlay-bridge.ts` reuses §2.3's `createLog` to relay caught script errors to the `EDF Review` output channel via a declared `edf-review.overlayLog` command. Security review amended.
- **LLD deviations:** (1) `contributes.commands` gains the `edf-review.overlayLog` command (hidden from the palette) — the LLD's manifest table lists only `previewScripts`, but the existing scaffold invariant ("no registered edf-review.* command is undeclared") forces any registered command to be declared; (2) the overlay's design-root containment is a webview translation of ADR-0039's path-prefix rule (workspace-folder heuristic) since the webview has no filesystem access; (3) error relay is best-effort — research shows the built-in markdown preview drops unknown previewScript postMessage types, so the registered command is the designed hook and the two halves are covered by tests.
- **Pressure:** heavy — ~220 source lines across 3 source files (overlay.js, overlay-bridge.ts, extension.ts) plus the manifest; security-sensitive (path traversal containment on untrusted hrefs), so the full track incl. evaluator security-boundary pass.

## Cost checkpoints
| Step | Timestamp | Cost (cumulative) | Tokens (cumulative) | Note |
|------|-----------|--------------------|----------------------|------|
| 3c | 2026-08-24T09:18:09Z | $0.00 | 0 in / 0 out | pressure: heavy — ~220 src lines across 3 source files + manifest; security-sensitive (path traversal) |
| 4bF | 2026-08-24T09:43:31Z | $0.00 | 0 in / 0 out | test-author complete — 21 BDD/invariant properties, all covered (design-root derivation unspecified) |
| 4dF | 2026-08-24T09:49:12Z | $0.00 | 0 in / 0 out | implementation complete — 86 host tests green (21 overlay new) |
| 5 | 2026-08-24T09:50:55Z | $0.00 | 0 in / 0 out | green — 86 host tests; tsc clean; prod audit 0 vulns (dev-only mocha vulns pre-existing); Python suite skipped (pytest not installed) |
| 6 | 2026-08-24T09:51:45Z | $0.00 | 0 in / 0 out | diag skipped — .diagnostics/ absent (worktree); CodeScene + SonarQube MCP not connected in session |
| 6b | 2026-08-24T10:00:32Z | $0.00 | 0 in / 0 out | evaluator: PASS WITH WARNINGS — 2 adversarial tests (observer wiring, scroll wiring) pass; Inv 25/26 remain build gates |
| 8 | 2026-08-24T10:04:55Z | $0.00 | 0 in / 0 out | [PR #75](https://github.com/mironyx/engineering-delivery-framework/pull/75) |
| 9 | 2026-08-24T10:22:04Z | $0.00 | 0 in / 0 out | review clean after 3 warn fixes (designRootOf regex, console.error, jsdom bump); re-review [] |
| 10 | 2026-08-24T10:22:17Z | $0.00 | 0 in / 0 out | report done — PR #75 open; CI N/A (no checks on branch) |

## Concerns & Deferred Items
- **Design-root derivation (webview).** The LLD §2.5 constraint says `resolveAndValidateHref` must "reuse the exact containment logic ADR-0039 fixes", but the webview has no file access (Invariant 28) and no webview→host channel (ADR-0038), so it cannot read `kb/file-map.md`'s declared per-project `design-root`. The implementation derives design-root from the preview document's own URI: EDF design docs live at `<design-root>/docs/design/<version>/` (ADR-0036), so the design-root is the path above the `docs/design` subtree; the fallback (no `docs/design` marker) bounds containment to the workspace top-level folder. This matches the fixture the test-author pinned (`plugins/edf` from `.../docs/design/v1/lld.md`). A drift risk: a project whose LLDs live outside `docs/design/` gets the more permissive fallback. Recorded for `/lld-sync`.
- **Error-relay mechanism is best-effort.** Measured during implementation: the built-in markdown preview's `onDidReceiveMessage` handles a fixed set of message types and drops `{ type: 'edf-overlay-error' }` (no generic command relay — confirmed against `vscode@main` and `1.88.0` preview.ts). The overlay still catches + swallows (never crashes), posts the message, and the bridge registers the `edf-review.overlayLog` command as the designed hook; the two halves are covered by tests. A live-preview end-to-end relay may not fire until VS Code exposes a previewScript→extension-host channel.
- **Test-harness fix.** `overlay.test.ts` created the jsdom without `runScripts: 'outside-only'`, so `window.eval` evaluated in a bare VM context where `document`/`window`/`MutationObserver` are not globals and the overlay failed to load. Added `runScripts: 'outside-only'` to `makeOverlayDom` (harness mechanics only; all assertions unchanged).
- **Evaluator warnings (PASS WITH WARNINGS).** (1) Invariant 25's minified-size check and Invariant 26's sub-1ms callback budget remain build/manual gates: no minifier step exists in the extension, and jsdom's DOM is too slow for a hard p95<1ms assert (the test asserts the path completes and logs the mean). (2) The overlay's mutation callback reacts to SVG add/remove only; an in-place anchor swap inside a persistent SVG would not refresh overlays — out of spec (VS Code re-render replaces the SVG), noted for `/lld-sync`.
- **PR review #75 findings (all warn, resolved).** (1) `designRootOf` fallback regex bug — `/^[A-Za-z]:/.test(p)` never matched because a URL pathname starts with `/`, so the Windows drive branch was dead code and the fallback root degenerated to the drive root (`/C:`); fixed to `/^[A-Za-z]:$/.test(s[0] || '')` and locked with a new fallback-containment test. (2) Error-relay observability — `reportError` now also writes `console.error('[edf-review]', msg)` so a relay failure is never fully silent (the postMessage relay itself remains best-effort per the design deviation). (3) jsdom type/runtime mismatch — bumped `jsdom` to `^27.4.0` to match `@types/jsdom ^27.0.0` (was `^26.1.0`).

## Work completed

- **`media/overlay.js`** — created; a plain-DOM webview script injected via `contributes.markdown.previewScripts`. Overlays a real HTML `<a>` over each Mermaid SVG `click` target's bounding box (same href) so the built-in preview click handler opens the resolved file. MutationObserver scoped to `svg[id^="mermaid"]` + scroll/resize listeners keep overlays in sync; stale overlays are removed; design-root containment (ADR-0039) validated before each overlay is created; errors caught, relayed best-effort, and never crash the webview. 4962 bytes raw (< 5KB budget).
- **`src/overlay-bridge.ts`** — created; `createOverlayLog(context)` registers the `edf-review.overlayLog` command and returns `{ log, handleMessage }`; `handleMessage` coerces a relayed value to a line and writes it to the `EDF Review` channel; never throws.
- **`src/log.ts`** — modified; the `EDF Review` channel is now cached per context (WeakMap) so §2.3's review command and §2.5's overlay relay write to a single channel.
- **`src/extension.ts`** — modified; `activate()` calls `createOverlayLog(context)`.
- **`package.json`** — re-added `contributes.markdown.previewScripts → ["./media/overlay.js"]`, added the `edf-review.overlayLog` command (hidden via `commandPalette`), added `jsdom`/`@types/jsdom` devDeps.
- **`test/suite/overlay.test.ts`** — created; 24 specs (LLD §2.5 BDD blocks + invariants 23-28 + evaluator adversarial + fallback-containment).
- **`plugins/edf/docs/design/v1/extension-security-review.md`** — amended: replaced the "no preview script injection" row with three preview-script properties.
- **LLD sync** — `lld-v1-e1-2-review-feedback.md` §2.5 bumped to 1.1; coverage manifest entry for `REQ-…-diagram-click-through-overlay` flipped to Revised.

PR: [#75](https://github.com/mironyx/engineering-delivery-framework/pull/75), branch `feat/diagram-click-through`. 89 host tests pass (24 new). Typecheck clean; production audit 0 vulns.

## Decisions made

- **`contributes.commands` gains `edf-review.overlayLog`** (hidden via `commandPalette` with `when: false`) — the LLD's manifest table listed only `previewScripts`, but the scaffold invariant "no registered `edf-review.*` command is undeclared" forces any registered command to be declared.
- **Design-root is derived, not read.** The webview has no file access (Invariant 28), so `resolveAndValidateHref` cannot read `kb/file-map.md`'s declared design-root. It derives design-root from the document URI: the path above the `docs/design/` subtree (ADR-0036), falling back to the workspace top-level folder.
- **Error relay is best-effort.** Measured that the built-in markdown preview drops unknown previewScript postMessage types; the overlay posts the message and the bridge registers the command as the designed hook. Both halves unit-tested; `console.error` added so a failure is never silent.
- **Shared channel.** `log.ts` caches the `EDF Review` channel per extension context so §2.3 and §2.5 log to one channel (honouring the LLD's "shared with §2.3's Logger").
- **jsdom test harness.** `runScripts: 'outside-only'` is required for `window.eval` to expose DOM globals; `jsdom` aligned to `^27.4.0` to match `@types/jsdom`.

## Review feedback addressed

PR review #75 (3 warn findings, all resolved):
1. `designRootOf` fallback regex dead code → fixed to test the first path segment; locked with a fallback-containment test.
2. Error-relay observability → `reportError` now writes `console.error('[edf-review]', msg)`.
3. jsdom type/runtime mismatch → bumped to `^27.4.0`.

Re-review confirmed no new issues (`[]`). Reviewer confirmed the fix tightens containment and introduces no regression.

## LLD Sync report

```
## LLD Sync — Issue #63: v1-e1-2 diagram click-through navigation via previewScripts overlay

### Corrections (spec was wrong)
- Manifest table: LLD listed only contributes.markdown.previewScripts; implementation also added
  edf-review.overlayLog to contributes.commands (hidden via commandPalette) — required by the
  scaffold "no undeclared command" invariant.
- Overlay-bridge relay: LLD assumed the built-in markdown preview exposes an onDidReceiveMessage
  equivalent; measured it drops unknown previewScript postMessage types — the command is a
  best-effort hook, both halves tested.
- Design-root containment: webview has no file access, so design-root is derived from the
  document URI's docs/design/ subtree (ADR-0036); the startsWith(root) rule is ADR-0039's exact
  check.
- log.ts shared channel: made literally shared via a per-context WeakMap cache.

### Additions (not in spec)
- jsdom + @types/jsdom devDeps; window.__edfOverlay test seam; console.error in reportError;
  fallback-containment test.

### Omissions (in spec but not built)
- Invariant 25 (minified <5KB) and Invariant 26 (sub-1ms callback) remain build/manual gates.
- Live end-to-end error relay deferred until VS Code exposes a previewScript→host channel.

### Confirmations (notable)
- Overlay mechanism works as ADR-0039 R5 specified; activationEvents stays []; Invariant 28 holds.

### LLD updated
File: plugins/edf/docs/design/v1/lld-v1-e1-2-review-feedback.md §2.5
Version: 1.0 → 1.1 (Status Revised v8 → Revised v9)
```

## Cost retrospective

No Prometheus cost data exists for this repo (`EDF_FEATURE_PROM_DIR` not configured); PR body and
final labels record **$0.0000 / 0 tokens**. Qualitative:

- **Cost driver:** the pr-review pass found 3 warn findings that required a follow-up fix commit.
  Two of them (designRootOf fallback regex, error-relay observability) were genuine
  implementation defects; the jsdom version mismatch was a test-author dependency choice. The
  fix cycle was cheap (one small commit) but the re-review + re-run added ~25 min.
- **Improvement action:** the `designRootOf` compaction bug (a correct check changed to a dead
  branch during byte-shaving for the 5KB budget) shows that size-driven compaction can introduce
  security regressions. Recommendation: keep the budget assertion but re-verify containment
  logic after any byte-shaving edit, and add the fallback-containment test alongside the
  docs/design fixture tests.

## Next steps

- Suggested next board item: run `gh issue list --label kind:task --state open --limit 3`.
