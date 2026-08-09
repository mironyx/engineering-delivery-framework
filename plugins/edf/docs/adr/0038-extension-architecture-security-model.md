# 0038. VSCode Extension Architecture & Security Model for Diagram Navigability Links

**Date:** 2026-08-02
**Status:** Accepted
**Deciders:** LS / Claude

## Context

V1 introduces a VSCode extension (EDF Review) that makes diagram navigability links
functional in the markdown preview. The links are **workspace-relative source paths** and
`#LLD-` anchors that Mermaid's native `link`/`click` directives render as `<a>` elements
inside the preview's SVG diagrams; the extension intercepts those anchors. (An earlier
design used an `edf://` custom URL scheme — abandoned; see the 2026-08-09 amendment.)

When a reviewer hovers over a diagram participant in an LLD, the extension shows the
first ~40 lines of the referenced source file in a tooltip. When they click, the file
opens in the adjacent VSCode column while the preview stays visible. A
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
│   → {cmd:'peek', path}   │────────▶│                          │
│                          │         │                          │
│ click                    │ postMsg │                          │
│   → {cmd:'open', path}   │────────▶│                          │
│                          │         │                          │
│ catch (err)              │ postMsg │                          │
│   → {cmd:'logError', …}  │────────▶│   → EDF Review channel   │
└─────────────────────────┘         └──────────────────────────┘
```

### Message contract

All messages from preview script to extension host use the envelope:

```typescript
{ command: 'peek' | 'open' | 'logError', path: string, error?: string }
```

The host responds to `peek` with `{ command: 'peekResult', text: string | null }`
(first 40 lines of the file; on failure the text carries the specific reason — "File
not found", "Path outside workspace", or "Invalid path"). The host responds to `open`
by opening the file in the adjacent column or showing an error message. `logError` is
fire-and-forget.

### Security boundary

1. **Path containment (primary).** Every diagram-navigability path is resolved against
   `vscode.workspace.workspaceFolders[0].uri`. The resolved `fsPath` must start with the
   workspace root `fsPath`. Paths with `..` segments that would escape the root are
   rejected before any `readFile` or `showTextDocument` call. Rejections are logged to
   the `EDF Review` output channel with the raw URI and failure reason.
   With the scheme dropped, containment is now the *only* signal distinguishing a
   navigability link from ordinary markdown links, so it is also the only path filter.

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
- **Navigability links are type-dependent; erDiagram supports no interaction.** Mermaid
  generates `<a>` elements for the `link` directive on `sequenceDiagram` participants and
  for the `click` directive on `flowchart`, `stateDiagram`, and `classDiagram` nodes.
  `erDiagram` supports no interaction at all. The template therefore uses
  `link <actor>: <label> @ <url>` on sequence diagrams, `click <node> href "<url>" "<tooltip>"`
  on flowchart / classDiagram / stateDiagram (the third argument is the tooltip string,
  not a target keyword), and no links on erDiagram. `media/preview.js` intercepts the
  resulting `<a>` elements — no DOM injection onto SVG nodes and no hidden
  `<!-- edf-map -->` mapping block is required. This supersedes the spike finding
  (2026-08-02) that sequence diagrams needed a DOM-injection fix.
- **Interception is scoped to SVG anchors.** With the `edf://` scheme gone, diagram
  links are indistinguishable from ordinary markdown links by href alone — both are
  `<a href="...">`. `preview.js` must therefore scope its discovery to anchors rendered
  *inside* the preview's SVG diagrams (`querySelectorAll('svg a[xlink\\:href], svg a[href]')`)
  and skip all other links in the document, so hovering/clicking a reviewer's regular
  `[text](file.md)` link is never hijacked. The anchor must also carry a workspace-relative
  path or `#LLD-` fragment — absolute URLs (`http`, `mailto`, …) are ignored.
- **Navigability degrades to a harmless 404 on GitHub.** A workspace-relative href is
  preserved by Mermaid in every renderer (custom schemes are not), but outside VSCode
  it resolves against the page URL and 404s — an inert click, never a navigation or an
  error. `#LLD-` anchors scroll natively everywhere.
- **No telemetry, no analytics.** The extension declares no network access. We get no
  usage data. This is intentional for V1 — the `EDF Review` output channel is the only
  observability surface.

---

**Amendment (2026-08-08).** Corrected the navigability mechanism after verification with
mermaid-cli: sequence diagrams use the native `link` directive (renders `<a>`), `click`
is limited to flowchart / classDiagram / stateDiagram with a tooltip as its third
argument, and erDiagram supports no interaction. The earlier consequence proposing
DOM-injection onto SVG `<rect>` elements plus an `<!-- edf-map -->` mapping block is
obsolete and removed — `preview.js` intercepts the native `<a>` elements directly.
Message-contract command names aligned to the implementation (`peek` / `open`).

**Amendment (2026-08-09).** Dropped the `edf://` custom URL scheme. Empirical verification
with mermaid-cli 11.16.0 showed Mermaid's default `securityLevel: strict` strips custom
URL schemes from rendered `<a href>` elements in every diagram type, so `edf://` links
render inert in the very renderer the extension targets (VS Code's markdown-mermaid uses
strict by default); the `%%{init: {"securityLevel":"loose"}}%%` directive cannot override
it (securityLevel is initialize-time-only). Workspace-relative paths and `#LLD-` fragments
survive strict and render as real links. Navigability links therefore use the bare
workspace-relative path (`click A href "src/lib/x.ts" "source"`); interception is scoped
to SVG-rendered anchors so ordinary markdown links are untouched, and containment is now
the sole path filter. Title, context, security-boundary 1, and the consequences updated;
`edf://` no longer appears in requirements, template, or skill rules. Requirement ACs
(Stories 1.4 / 2.3 / 2.4 / 4.1 / 4.2) and the E1/E2 LLDs were updated in the same sweep.
