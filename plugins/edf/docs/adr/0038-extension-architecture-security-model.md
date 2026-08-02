# 0038. VSCode Extension Architecture & Security Model for `edf://` Protocol

**Date:** 2026-08-02
**Status:** Accepted
**Deciders:** LS / Claude

## Context

V1 introduces a VSCode extension (EDF Review) that makes `edf://` links functional in the
markdown preview. When a reviewer hovers over a diagram participant in an LLD, the
extension shows the first ~40 lines of the referenced source file in a tooltip. When they
click, the file opens in the adjacent VSCode column while the preview stays visible. A
command-palette action presents a filterable quick-pick of document headings and inserts a
review-feedback marker into the source editor (exact marker format and insertion-point
rules are owned by [Story 3.1](../../requirements/v1-requirements.md#story-31-quick-pick-section--insert-review-comment), not this ADR).

This ADR records the extension's architecture — the communication channel between the
preview webview and the extension host, the security boundary for path resolution, the
minimum permissions, and the V1 distribution model.

The requirements doc records an open question about the preview↔extension communication
mechanism ([Open Question 2](../../requirements/v1-requirements.md#open-questions)):
postMessage vs a custom `vscode-resource` URI scheme. The HLD
([C2.4](../design/v1/v1-design.md#c24-edf-review-extension)) commits to `postMessage`.

Prior decisions that constrain this one:

- **ADR-0018** — Epic/task model. The extension is delivered as tasks within V1 epics.
- **ADR-0026** — Stable IDs. `#LLD-` anchors use the ADR-0026 format; the extension's
  `#LLD-` fallback must resolve those anchors.
- **ADR-0034** — Design review gates. The extension is a design artefact, not an
  implementation detail — its architecture warrants an ADR.
- **Principles 3, 4, 5, 7** from the [requirements](../../requirements/v1-requirements.md):
  graceful degradation by default, convention over configuration, thin extension surface,
  Dev-Host-only distribution.

## Options Considered

### Option 1: `postMessage` channel (chosen)

The extension injects a preview script via `markdown.previewScripts`. The script sends
structured messages (`{ command, path }`) to the extension host via `postMessage`. The
host validates, reads files, and opens editors — the preview script never touches the
filesystem.

- **Pros:** Standard VSCode extension pattern (documented API). Keeps filesystem access
  server-side where validation and logging are single-path. Preview script stays under
  5 KB (no FS API, no Node). Channel works for hover, click, and error-relay in one
  contract. MutationObserver pattern handles late-rendered Mermaid SVGs.
- **Cons:** Requires the markdown preview webview to support `postMessage` — API is
  stable but the hover-event path (mouseover on SVG `<a>` elements) needs validation
  during implementation. Two-hop latency (preview→host→preview for tooltip content).
- **Implications:** The message contract becomes the extension's internal API. Adding a
  new command (e.g. "run tests for this section" in a future version) means adding a
  `command` value, not a new channel.

### Option 2: `vscode-resource` URI scheme

The extension registers a custom URI scheme handler. `edf://` links are rewritten to
`vscode-resource://` URIs that the webview can fetch directly.

- **Pros:** No postMessage overhead for file reads. Preview script can use `fetch()` to
  retrieve file content directly.
- **Cons:** Filesystem access moves into the preview webview — security validation is
  distributed across two surfaces (URI handler + webview). Harder to enforce the
  workspace-containment check in a single path. VSCode's `vscode-resource` policy has
  changed across versions (deprecation risk). More complex error logging (webview errors
  must be relayed back to the host anyway).
- **Implications:** Would require a `vscode.Uri` handler registration and content-security
  policy adjustments. Rejected because the security benefit of server-side validation
  outweighs the latency cost of postMessage.

## Decision

**Option 1 — `postMessage` channel, with workspace-containment as the primary security
boundary.**

### Architecture

```
Markdown Preview (webview)          Extension Host (Node)
┌─────────────────────────┐         ┌──────────────────────────┐
│ media/preview.js         │         │ extension.ts              │
│                          │         │                          │
│ MutationObserver         │         │ onDidReceivePreviewMessage│
│   → attach listeners     │         │   → validatePath(uri)     │
│                          │         │   → readFile(uri)         │
│ mouseover (150ms deb)    │ postMsg │   → showTextDocument(uri) │
│   → {cmd:'hover', path}  │────────▶│                          │
│                          │         │                          │
│ click                    │ postMsg │                          │
│   → {cmd:'click', path}  │────────▶│                          │
│                          │         │                          │
│ catch (err)              │ postMsg │                          │
│   → {cmd:'logError', …}  │────────▶│   → EDF Review channel   │
└─────────────────────────┘         └──────────────────────────┘
```

### Message contract

All messages from preview script to extension host use the envelope:

```typescript
{ command: 'hover' | 'click' | 'logError', path: string, error?: string }
```

The host responds to `hover` with `{ content: string }` (first 40 lines) or
`{ error: string }` (failure reason). The host responds to `click` by opening the file
or showing an information message. `logError` is fire-and-forget.

### Security boundary

1. **Path containment (primary).** Every `edf://` path is resolved against
   `vscode.workspace.workspaceFolders[0].uri`. The resolved `fsPath` must start with the
   workspace root `fsPath`. Paths with `..` segments that would escape the root are
   rejected before any `readFile` or `showTextDocument` call. Rejections are logged to
   the `EDF Review` output channel with the raw URI and failure reason.

2. **No arbitrary code execution.** File content is read via
   `vscode.workspace.fs.readFile` as UTF-8 text. The extension never evaluates,
   `import()`s, or otherwise interprets file contents.

3. **Minimum permissions.** `package.json` declares only `workspace.fs` read and
   `window.showTextDocument`. No network access (`"extensionKind": "workspace"`), no
   filesystem write, no process execution (build-only `"scripts"`).

4. **Error containment.** JavaScript errors in `media/preview.js` are caught and relayed
   to the host via `postMessage({ command: 'logError', ... })`. Unhandled errors must not
   crash the preview webview. All host-side failures are logged to the `EDF Review`
   output channel.

### Additional conventions

- **Tooltip styling** uses VSCode theme variables (`--vscode-editor-background`,
  `--vscode-editor-foreground`, `--vscode-editor-font-family`) — no hardcoded colours.
- **MutationObserver** detects late-rendered Mermaid SVGs (they may arrive after DOM
  ready). The observer callback completes in under 1ms per invocation.
- **Preview script** is kept under 5 KB minified.
- **`#LLD-` fallback** is owned by C2.4: if native scroll-to-fragment does not work for
  SVG anchor clicks in VSCode's preview webview, the preview script adds a click listener
  that sets `window.location.hash` to the fragment.
- **Distribution in V1** is via VSCode Extension Development Host only. Marketplace
  publishing, `.vsix` packaging, and consumer-facing installation instructions are
  deferred to a future version (per Design Principle 7).

## Consequences

- **Single validation path.** Every file read and file-open goes through the same
  workspace-containment check in the extension host. There is no path to the filesystem
  that bypasses validation.
- **Extensible message contract.** Adding a future command (e.g. "run tests for this
  section") means adding a `command` value to the envelope — no new channel, no
  architectural change.
- **Preview script stays simple.** At ~2-3 KB of listener + MutationObserver + error
  handling, well within the 5 KB budget. The script does not import libraries, parse
  markdown, or touch the filesystem.
- **Dev-Host-only means no consumer install UX.** The extension is loaded via F5 in
  VSCode. `.vsix` packaging, marketplace metadata, and installation docs are deferred.
- **Mermaid `click` does not work on `sequenceDiagram` participants.** Spike validated
  2026-08-02: Mermaid only generates `<a>` elements for `click` directives in `flowchart`,
  `stateDiagram`, `erDiagram`, and `classDiagram`. In `sequenceDiagram`, the `click`
  directive is silently ignored — no `<a>` element is created, so `querySelectorAll` finds
  nothing. **Fix:** `media/preview.js` injects click/hover handlers onto SVG `<rect>`
  elements (sequence diagram participant boxes) via DOM traversal, driven by a hidden
  participant→path mapping block in the markdown (a `<!-- edf-map ... -->` comment or
  similar inline data block generated by the LLD template). Native `click` directives
  continue to work for non-sequence diagram types. This finding affects Stories 1.4
  (`click` directives on every participant — the template must emit the mapping block for
  sequence diagrams), 2.1 (hover tooltip — now driven by DOM injection, not `<a>`
  elements), and 2.2 (click-to-open — same).
- **No telemetry, no analytics.** The extension declares no network access. We get no
  usage data. This is intentional for V1 — the `EDF Review` output channel is the only
  observability surface.
