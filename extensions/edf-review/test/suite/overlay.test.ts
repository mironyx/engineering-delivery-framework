/**
 * Issue #63 (v1-e1-2): diagram click-through via markdown.previewScripts overlay.
 *
 * DOM-level and host-level specs for LLD §2.5 (Diagram click-through overlay):
 * the four BDD blocks (overlay creation, lifecycle, click-through, error
 * handling) plus the unit-testable invariants 23-28.
 *
 * Two surfaces under test:
 *  - media/overlay.js — a plain IIFE webview script with no exports. It exposes
 *    `window.__edfOverlay = { resolveAndValidateHref, createOverlaysFor,
 *    removeStaleOverlays, observeMermaidContainers }` as its test seam, so the
 *    pure/DOM functions are driven directly via jsdom. The script is read from
 *    the compiled test location (out/test/suite → ../../../media/overlay.js) and
 *    evaluated inside a `file://` jsdom document, with `acquireVsCodeApi`
 *    defined BEFORE eval so error-relay postMessages are captured.
 *  - src/overlay-bridge.ts — createOverlayLog, the extension-host relay that
 *    writes relayed errors to the `EDF Review` output channel. It is driven with
 *    the same monkey-patched vscode.window.createOutputChannel / registerCommand
 *    stubs the rest of the suite uses (no HTTP, so the repo's respx rule does
 *    not apply).
 *
 * The overlay fixture mirrors ADR-0039 R1's resolution table: an LLD at
 * plugins/edf/docs/design/v1/lld.md whose design-root is plugins/edf/. So
 * `../../../skills/lld/template.md` resolves inside design-root (accepted) and
 * `../../../../../etc/passwd` escapes it (rejected).
 *
 * These specs are written test-first against the LLD contract. The current
 * media/overlay.js and src/overlay-bridge.ts are stubs that throw
 * `not implemented`, so every DOM/bridge spec here is expected to fail until the
 * implementation lands.
 */
import * as vscode from 'vscode';
import * as assert from 'assert';
import * as fs from 'fs';
import * as path from 'path';
import { JSDOM, VirtualConsole } from 'jsdom';
import { createOverlayLog } from '../../src/overlay-bridge';

// ---------------------------------------------------------------------------
// Fixture constants
// ---------------------------------------------------------------------------

const SVG_NS = 'http://www.w3.org/2000/svg';

/** Compiled location is out/test/suite/, so ../../../media resolves to the extension root's media/. */
const OVERLAY_SOURCE = path.join(__dirname, '../../../media/overlay.js');

/** The fixture preview document — an LLD at the same location ADR-0039 R1 resolves from. */
const PREVIEW_URL = 'file:///C:/proj/plugins/edf/docs/design/v1/lld.md';

/** The containment boundary for the fixture: ADR-0039's `plugins/edf` module root. */
const DESIGN_ROOT = 'file:///C:/proj/plugins/edf/';

/** Resolves to file:///C:/proj/plugins/edf/skills/lld/template.md — inside design-root. */
const INSIDE_HREF = '../../../skills/lld/template.md';

/** Resolves to file:///C:/proj/etc/passwd — escapes design-root. */
const ESCAPE_HREF = '../../../../../etc/passwd';

/** Resolves to file:///C:/proj/plugins/ — above design-root. */
const ESCAPE_HREF2 = '../../../..';

/** A fragment link — passes through unchanged, never leaves design-root. */
const FRAGMENT_HREF = '#LLD-v1-e1-2-overlay';

/** The message shape the overlay posts and the bridge relays. */
interface RelayMessage {
  type?: string;
  message?: string;
  [key: string]: unknown;
}

/** The test seam media/overlay.js exposes on window. */
interface OverlaySeam {
  resolveAndValidateHref: (href: string) => string | null;
  createOverlaysFor: (svg: Element) => void;
  removeStaleOverlays: () => void;
  observeMermaidContainers: () => void;
}

/**
 * The window surface the overlay tests touch. TS 5.9's lib.dom no longer exposes
 * `eval`/`MouseEvent` as Window members (they moved to globals), and the overlay
 * adds its own `__edfOverlay` seam, so the jsdom window is typed structurally.
 */
interface OverlayWindow {
  document: Document;
  eval(script: string): unknown;
  MouseEvent: typeof MouseEvent;
  Event: typeof Event;
  dispatchEvent(event: unknown): boolean;
  MutationObserver?: unknown;
  __edfOverlay?: OverlaySeam;
  acquireVsCodeApi?: () => VSCodeApi;
}

// ---------------------------------------------------------------------------
// Webview harness (jsdom)
// ---------------------------------------------------------------------------

/** A jsdom window plus the messages the overlay posts via acquireVsCodeApi. */
interface OverlayDom {
  dom: JSDOM;
  win: OverlayWindow;
  captured: RelayMessage[];
}

/** The minimal acquireVsCodeApi surface the overlay needs. */
interface VSCodeApi {
  postMessage: (message: unknown) => void;
  getState: () => unknown;
  setState: (state: unknown) => void;
}

/** Build a fresh preview document. `poisonMutationObserver` forces observeMermaidContainers to throw. */
function makeOverlayDom(opts: { poisonMutationObserver?: boolean } = {}): OverlayDom {
  const virtualConsole = new VirtualConsole();
  // Clicking an overlay drives the anchor's default navigation, which jsdom does
  // not implement — that jsdomError is expected noise, not a test failure.
  virtualConsole.on('jsdomError', (err: Error) => {
    if (!/not implemented: navigation/i.test(err.message)) {
      console.error(`[jsdom] ${err.message}`);
    }
  });

  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: PREVIEW_URL,
    pretendToBeVisual: true,
    virtualConsole,
    // Without `runScripts: 'outside-only'`, jsdom's window.eval evaluates in a
    // bare VM context where `document`/`window`/`MutationObserver` are not
    // globals — the evaluated overlay.js would fail with `document is not
    // defined`. This is a harness-mechanics fix; the assertions are unchanged.
    runScripts: 'outside-only'
  });
  const captured: RelayMessage[] = [];
  const win = dom.window as unknown as OverlayWindow;

  // acquireVsCodeApi must exist BEFORE eval so the error-relay postMessage is
  // captured (the harness contract).
  win.acquireVsCodeApi = () => ({
    postMessage: (message: unknown) => {
      captured.push(message as RelayMessage);
    },
    getState: () => ({}),
    setState: () => {}
  });

  if (opts.poisonMutationObserver) {
    win.MutationObserver = undefined;
  }

  return { dom, win, captured };
}

/** Eval media/overlay.js inside the fixture window (stub throws until implemented). */
function loadOverlay(opts: { poisonMutationObserver?: boolean } = {}): OverlayDom {
  const { dom, win, captured } = makeOverlayDom(opts);
  win.eval(fs.readFileSync(OVERLAY_SOURCE, 'utf8'));
  return { dom, win, captured };
}

/** Read the overlay's test seam off the window. */
function seam(win: OverlayWindow): OverlaySeam {
  return win.__edfOverlay as OverlaySeam;
}

/** A Mermaid-shaped SVG with one click target, mirroring svg[id^="mermaid"] a[href]. */
function mermaidSvg(
  win: OverlayWindow,
  opts: { id?: string; href?: string } = {}
): { svg: Element; anchor: Element } {
  const doc = win.document;
  const svg = doc.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('id', opts.id ?? 'mermaid-diagram-1');
  const anchor = doc.createElementNS(SVG_NS, 'a');
  anchor.setAttribute('href', opts.href ?? INSIDE_HREF);
  svg.appendChild(anchor);
  return { svg, anchor };
}

/** Stub a known bounding box on an element (jsdom returns zeros otherwise). */
function stubRect(el: Element, r: { left: number; top: number; width: number; height: number }): void {
  const rect = {
    left: r.left,
    top: r.top,
    right: r.left + r.width,
    bottom: r.top + r.height,
    width: r.width,
    height: r.height,
    x: r.left,
    y: r.top,
    toJSON(): unknown {
      return this;
    }
  };
  (el as unknown as { getBoundingClientRect: () => unknown }).getBoundingClientRect = () => rect;
}

/** The overlays appended to the preview body (SVG anchors live inside svg, so `body > a` excludes them). */
function bodyOverlays(doc: Document): HTMLAnchorElement[] {
  return Array.from(doc.querySelectorAll('body > a')) as unknown as HTMLAnchorElement[];
}

// ---------------------------------------------------------------------------
// Extension-host harness (monkey-patched vscode API, matching the suite's style)
// ---------------------------------------------------------------------------

/** Every subscriptions array handed to freshContext() this file. */
const fakeSubscriptionLists: vscode.Disposable[][] = [];

/** Minimal ExtensionContext stub — createOverlayLog only touches subscriptions. */
function freshContext(): vscode.ExtensionContext {
  const subscriptions: vscode.Disposable[] = [];
  fakeSubscriptionLists.push(subscriptions);
  return { subscriptions } as unknown as vscode.ExtensionContext;
}

/** Monkey-patch vscode.window.createOutputChannel and capture channel output. */
function stubOutputChannel(): {
  captured: () => { name: string; appendLineCalls: string[]; channel?: vscode.OutputChannel };
  restore: () => void;
} {
  const original = vscode.window.createOutputChannel;
  const testWindow = vscode.window as unknown as {
    createOutputChannel: typeof vscode.window.createOutputChannel;
  };
  const state: { name: string; appendLineCalls: string[]; channel?: vscode.OutputChannel } = {
    name: '',
    appendLineCalls: [],
    channel: undefined
  };
  testWindow.createOutputChannel = ((name: string) => {
    const channel = {
      name,
      appendLine: (value: string) => {
        state.appendLineCalls.push(value);
      },
      dispose: () => {}
    } as unknown as vscode.OutputChannel;
    state.name = name;
    state.channel = channel;
    return channel;
  }) as unknown as typeof vscode.window.createOutputChannel;
  return {
    captured: () => state,
    restore: () => {
      testWindow.createOutputChannel = original;
    }
  };
}

/** Monkey-patch vscode.commands.registerCommand and capture the registrations. */
function stubRegisterCommand(): {
  calls: () => Array<{ command: string; handler: unknown }>;
  restore: () => void;
} {
  const original = vscode.commands.registerCommand;
  const testCommands = vscode.commands as unknown as {
    registerCommand: typeof vscode.commands.registerCommand;
  };
  const calls: Array<{ command: string; handler: unknown }> = [];
  testCommands.registerCommand = ((command: string, handler: (..._args: unknown[]) => unknown) => {
    calls.push({ command, handler });
    return { dispose() {} };
  }) as unknown as typeof vscode.commands.registerCommand;
  return {
    calls: () => calls,
    restore: () => {
      testCommands.registerCommand = original;
    }
  };
}

afterEach(() => {
  while (fakeSubscriptionLists.length > 0) {
    const subscriptions = fakeSubscriptionLists.pop()!;
    for (const disposable of subscriptions) {
      disposable.dispose();
    }
  }
});

// ---------------------------------------------------------------------------
// Specs — overlay creation (LLD §2.5 BDD block 1)
// ---------------------------------------------------------------------------

describe('overlay creation (Issue #63, LLD §2.5)', () => {
  it('overlays a real anchor over each SVG click-target bounding box', () => {
    const { win } = loadOverlay();
    const doc = win.document;
    const svg = doc.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('id', 'mermaid-two-targets');
    const a1 = doc.createElementNS(SVG_NS, 'a');
    a1.setAttribute('href', INSIDE_HREF);
    const a2 = doc.createElementNS(SVG_NS, 'a');
    a2.setAttribute('href', FRAGMENT_HREF);
    svg.appendChild(a1);
    svg.appendChild(a2);
    doc.body.appendChild(svg);
    stubRect(a1, { left: 10, top: 20, width: 100, height: 40 });
    stubRect(a2, { left: 120, top: 20, width: 100, height: 40 });

    seam(win).createOverlaysFor(svg);

    const overlays = bodyOverlays(doc);
    assert.strictEqual(overlays.length, 2, 'one overlay per click target inside the SVG');
    const overlay = overlays[0];
    // R5 (ADR-0039): the built-in preview handler walks up checking
    // t.tagName === "A"; an SVG anchor reports lowercase "a", so the overlay
    // must be a real HTML anchor the existing handler recognises.
    assert.strictEqual(overlay.tagName, 'A', 'overlay is a real HTML anchor');
    assert.strictEqual(overlay.style.position, 'absolute', 'overlay is absolutely positioned');
    assert.strictEqual(overlay.style.left, '10px', 'overlay sits at the first anchor left edge');
    assert.strictEqual(overlay.style.top, '20px', 'overlay sits at the first anchor top edge');
    assert.strictEqual(overlay.style.width, '100px', 'overlay spans the first anchor width');
    assert.strictEqual(overlay.style.height, '40px', 'overlay spans the first anchor height');
    assert.strictEqual(overlays[1].style.left, '120px', 'the second click target gets its own overlay');
  });

  it('carries the same href as the underlying SVG anchor', () => {
    const { win } = loadOverlay();
    const { svg, anchor } = mermaidSvg(win);
    win.document.body.appendChild(svg);
    stubRect(anchor, { left: 0, top: 0, width: 50, height: 30 });

    seam(win).createOverlaysFor(svg);

    const overlay = bodyOverlays(win.document)[0];
    assert.strictEqual(
      overlay.getAttribute('href'),
      INSIDE_HREF,
      'the overlay keeps the original document-relative href'
    );
  });

  it('rejects a resolved href outside design-root, creating no overlay', () => {
    const { win } = loadOverlay();
    // Invariant 23: an escaping `../../..` href resolves above design-root and
    // must produce no overlay.
    assert.strictEqual(seam(win).resolveAndValidateHref(ESCAPE_HREF2), null, 'resolving above design-root is rejected');
    assert.strictEqual(seam(win).resolveAndValidateHref(ESCAPE_HREF), null, 'escaping design-root is rejected');

    const { svg, anchor } = mermaidSvg(win, { href: ESCAPE_HREF });
    win.document.body.appendChild(svg);
    stubRect(anchor, { left: 0, top: 0, width: 50, height: 30 });

    assert.doesNotThrow(() => seam(win).createOverlaysFor(svg));
    assert.strictEqual(bodyOverlays(win.document).length, 0, 'no overlay is created for a rejected href');
  });

  it('supports flowchart, classDiagram and stateDiagram-v2 click targets and both link forms', () => {
    const { win } = loadOverlay();
    const types = ['flowchart', 'classDiagram', 'stateDiagram-v2'] as const;
    // Story 2.3 AC: every diagram type that supports `click`, and both link forms
    // (document-relative path and #LLD- fragment).
    for (const type of types) {
      for (const href of [INSIDE_HREF, FRAGMENT_HREF]) {
        const { svg, anchor } = mermaidSvg(win, { id: `mermaid-${type}-${href === FRAGMENT_HREF ? 'frag' : 'path'}`, href });
        win.document.body.appendChild(svg);
        stubRect(anchor, { left: 0, top: 0, width: 40, height: 20 });
        seam(win).createOverlaysFor(svg);
      }
    }
    assert.strictEqual(
      bodyOverlays(win.document).length,
      types.length * 2,
      'every svg[id^="mermaid"] click target gets an overlay, for each type and link form'
    );
  });
});

// ---------------------------------------------------------------------------
// Specs — overlay lifecycle (LLD §2.5 BDD block 2)
// ---------------------------------------------------------------------------

describe('overlay lifecycle (Issue #63, LLD §2.5)', () => {
  it('repositions overlays on scroll and resize', () => {
    const { win } = loadOverlay();
    const { svg, anchor } = mermaidSvg(win);
    win.document.body.appendChild(svg);
    stubRect(anchor, { left: 0, top: 0, width: 50, height: 30 });
    seam(win).createOverlaysFor(svg);

    let overlays = bodyOverlays(win.document);
    assert.strictEqual(overlays.length, 1);
    assert.strictEqual(overlays[0].style.top, '0px');

    // Scroll/resize moves the target down the page; re-running creation must
    // track the current bounding box and never leave the overlay stale.
    stubRect(anchor, { left: 0, top: 100, width: 50, height: 30 });
    seam(win).createOverlaysFor(svg);

    overlays = bodyOverlays(win.document);
    assert.strictEqual(overlays.length, 1, 'repositioning must not duplicate the overlay');
    assert.strictEqual(overlays[0].style.top, '100px', 'overlay tracks the target after scroll/resize');
  });

  it('removes overlays whose source SVG is no longer present after a re-render', () => {
    const { win } = loadOverlay();
    const keep = mermaidSvg(win, { id: 'mermaid-keep' });
    const gone = mermaidSvg(win, { id: 'mermaid-gone' });
    win.document.body.appendChild(keep.svg);
    win.document.body.appendChild(gone.svg);
    stubRect(keep.anchor, { left: 0, top: 0, width: 40, height: 20 });
    stubRect(gone.anchor, { left: 0, top: 0, width: 40, height: 20 });
    seam(win).createOverlaysFor(keep.svg);
    seam(win).createOverlaysFor(gone.svg);
    assert.strictEqual(bodyOverlays(win.document).length, 2);

    // The re-render drops the second diagram from the document; its overlay must
    // be removed rather than left stale (Invariant 24).
    gone.svg.remove();
    seam(win).removeStaleOverlays();

    const overlays = bodyOverlays(win.document);
    assert.strictEqual(overlays.length, 1, 'stale overlay is removed');
    assert.strictEqual(overlays[0].getAttribute('href'), INSIDE_HREF, 'the surviving overlay belongs to the still-connected diagram');
  });

  it('creates no duplicate overlay for an SVG that re-renders unchanged', () => {
    const { win } = loadOverlay();
    const { svg, anchor } = mermaidSvg(win);
    win.document.body.appendChild(svg);
    stubRect(anchor, { left: 0, top: 0, width: 50, height: 30 });
    seam(win).createOverlaysFor(svg);
    seam(win).createOverlaysFor(svg); // unchanged re-render

    const overlays = bodyOverlays(win.document);
    assert.strictEqual(overlays.length, 1, 'an unchanged re-render must not stack overlays');
    assert.strictEqual(overlays[0].getAttribute('href'), INSIDE_HREF);
  });
});

// ---------------------------------------------------------------------------
// Specs — overlay click-through (LLD §2.5 BDD block 3)
// ---------------------------------------------------------------------------

describe('overlay click-through (Issue #63, LLD §2.5)', () => {
  it('opens the resolved file when the built-in handler processes an overlay anchor click', () => {
    const { win } = loadOverlay();
    const { svg, anchor } = mermaidSvg(win);
    win.document.body.appendChild(svg);
    stubRect(anchor, { left: 0, top: 0, width: 50, height: 30 });
    seam(win).createOverlaysFor(svg);

    const overlay = bodyOverlays(win.document)[0];
    // R5 (ADR-0039): the built-in markdown-preview click handler walks up from
    // the click target checking t.tagName === "A". An SVG anchor reports
    // lowercase "a", so only the overlay's real HTML anchor can satisfy it.
    assert.strictEqual(overlay.tagName, 'A', 'the built-in handler only recognises uppercase "A"');
    assert.strictEqual(overlay.getAttribute('href'), INSIDE_HREF, 'the overlay href is the underlying click href');

    const click = new win.MouseEvent('click', {
      bubbles: true,
      cancelable: true,
      view: win as unknown as Window
    });
    overlay.dispatchEvent(click);
    assert.strictEqual(
      click.defaultPrevented,
      false,
      'the overlay must not swallow the click; the built-in handler processes it'
    );
  });

  it('leaves the preview open in its original column after the file opens', () => {
    const { win } = loadOverlay();
    const { svg, anchor } = mermaidSvg(win, { href: FRAGMENT_HREF });
    win.document.body.appendChild(svg);
    stubRect(anchor, { left: 0, top: 0, width: 50, height: 30 });
    seam(win).createOverlaysFor(svg);

    const overlay = bodyOverlays(win.document)[0];
    // The overlay must not force a new browsing context/column, and must not do
    // its own JS navigation that would replace or close the preview — those are
    // the overlay-side conditions for the preview staying open in its column.
    assert.strictEqual(overlay.getAttribute('target'), null, 'no target attribute that could open a new column');
    assert.strictEqual(overlay.target, '', 'anchor target resolves to the same browsing context');

    const click = new win.MouseEvent('click', {
      bubbles: true,
      cancelable: true,
      view: win as unknown as Window
    });
    overlay.dispatchEvent(click);
    assert.ok(win.document.body.contains(overlay), 'the preview document stays live after the click');
    assert.strictEqual(win.document.querySelectorAll('body > a').length, 1, 'the overlay is not torn down');
  });
});

// ---------------------------------------------------------------------------
// Specs — overlay error handling (LLD §2.5 BDD block 4 + Invariant 27)
// ---------------------------------------------------------------------------

describe('overlay error handling (Issue #63, LLD §2.5)', () => {
  it('catches a script error and relays it to the extension host', () => {
    // Invariant 27: a throw inside observeMermaidContainers (here: MutationObserver
    // is missing, so the observer cannot be registered) is caught by the script's
    // top-level try/catch, posted to the extension host as
    // { type: 'edf-overlay-error', message }, and swallowed — eval must not propagate.
    const { win, captured } = loadOverlay({ poisonMutationObserver: true });

    const relay = captured.find((m) => m.type === 'edf-overlay-error');
    assert.ok(relay, 'a script error must be relayed via acquireVsCodeApi().postMessage');
    assert.strictEqual(typeof relay?.message, 'string');
    assert.ok((relay?.message?.length ?? 0) > 0, 'the relay carries a message');
    assert.ok(win.__edfOverlay, 'the webview must not crash — the test seam still exists');
  });

  it('logs a relayed error to the EDF Review output channel via the bridge', () => {
    const outputStub = stubOutputChannel();
    const commandsStub = stubRegisterCommand();
    try {
      const context = freshContext();
      const overlayLog = createOverlayLog(context);

      assert.ok(
        commandsStub.calls().some((r) => r.command === 'edf-review.overlayLog'),
        'createOverlayLog must register the edf-review.overlayLog command'
      );

      overlayLog.handleMessage({ type: 'edf-overlay-error', message: 'boom in overlay' });

      const captured = outputStub.captured();
      assert.strictEqual(captured.name, 'EDF Review');
      assert.ok(
        captured.appendLineCalls.some((line) => line.includes('boom in overlay')),
        `the relayed error must reach the EDF Review channel, got ${JSON.stringify(captured.appendLineCalls)}`
      );
      assert.ok(
        context.subscriptions.includes(captured.channel as vscode.Disposable),
        'the channel must be pushed onto context.subscriptions so it is disposed'
      );
    } finally {
      outputStub.restore();
      commandsStub.restore();
    }
  });

  it('continues functioning after a caught error, without crashing the webview', () => {
    const { win, captured } = loadOverlay({ poisonMutationObserver: true });
    assert.ok(
      captured.some((m) => m.type === 'edf-overlay-error'),
      'precondition: an error was relayed'
    );

    // The webview keeps working: pure resolution still answers...
    assert.strictEqual(seam(win).resolveAndValidateHref(FRAGMENT_HREF), FRAGMENT_HREF);

    // ...and a fresh overlay can still be created for a healthy diagram.
    const { svg, anchor } = mermaidSvg(win);
    win.document.body.appendChild(svg);
    stubRect(anchor, { left: 0, top: 0, width: 50, height: 30 });
    assert.doesNotThrow(() => seam(win).createOverlaysFor(svg));
    assert.strictEqual(bodyOverlays(win.document).length, 1, 'overlay creation still works after a caught error');
  });

  it('never throws on malformed relay messages (bridge)', () => {
    const outputStub = stubOutputChannel();
    const commandsStub = stubRegisterCommand();
    try {
      const overlayLog = createOverlayLog(freshContext());
      const malformed: unknown[] = [
        undefined,
        null,
        42,
        'a bare string',
        {},
        { type: 'other' },
        { type: 'edf-overlay-error' }, // missing message
        { type: 'edf-overlay-error', message: 42 } // non-string message
      ];
      for (const bad of malformed) {
        assert.doesNotThrow(
          () => overlayLog.handleMessage(bad),
          `handleMessage must not throw on ${JSON.stringify(bad)}`
        );
      }
      assert.doesNotThrow(() => overlayLog.log('anything'));
    } finally {
      outputStub.restore();
      commandsStub.restore();
    }
  });
});

// ---------------------------------------------------------------------------
// Specs — resolveAndValidateHref (LLD §2.5 Part B pure contract)
// ---------------------------------------------------------------------------

describe('resolveAndValidateHref (Issue #63, LLD §2.5 Part B)', () => {
  it('passes fragment-only hrefs through unchanged', () => {
    const { win } = loadOverlay();
    assert.strictEqual(seam(win).resolveAndValidateHref(FRAGMENT_HREF), FRAGMENT_HREF);
    assert.strictEqual(seam(win).resolveAndValidateHref('#LLD-v1-e1-2-command'), '#LLD-v1-e1-2-command');
  });

  it('rejects absolute URLs with a scheme', () => {
    const { win } = loadOverlay();
    for (const href of [
      'https://example.com/x.md',
      'mailto:reviewer@example.com',
      'javascript:alert(1)',
      'file:///C:/proj/plugins/edf/skills/lld/template.md'
    ]) {
      assert.strictEqual(seam(win).resolveAndValidateHref(href), null, `${href} must be rejected`);
    }
  });

  it('accepts a document-relative path that resolves inside design-root, returning the original href', () => {
    const { win } = loadOverlay();
    assert.strictEqual(seam(win).resolveAndValidateHref(INSIDE_HREF), INSIDE_HREF);
  });

  it('accepts a same-directory relative path', () => {
    const { win } = loadOverlay();
    assert.strictEqual(seam(win).resolveAndValidateHref('./template.md'), './template.md');
  });

  it('rejects a document-relative path that escapes design-root', () => {
    const { win } = loadOverlay();
    assert.strictEqual(seam(win).resolveAndValidateHref(ESCAPE_HREF2), null, 'resolving above design-root is rejected');
    assert.strictEqual(seam(win).resolveAndValidateHref(ESCAPE_HREF), null);
    assert.strictEqual(seam(win).resolveAndValidateHref('../../../../skills/lld/template.md'), null);
  });
});

// ---------------------------------------------------------------------------
// Specs — static invariants (LLD §2.5 Invariants 25, 28)
// ---------------------------------------------------------------------------

describe('overlay script static invariants (Issue #63, LLD §2.5)', () => {
  it('stays under 5KB minified — raw source is under 5000 bytes (Invariant 25)', () => {
    const src = fs.readFileSync(OVERLAY_SOURCE, 'utf8');
    const bytes = Buffer.byteLength(src, 'utf8');
    assert.ok(
      bytes < 5000,
      `media/overlay.js raw source is ${bytes} bytes; minifying can only shrink it, so it must stay under 5000 to guarantee the 5KB minified budget`
    );
  });

  it('performs no file reads, network calls, or dynamic evaluation (Invariant 28)', () => {
    const src = fs.readFileSync(OVERLAY_SOURCE, 'utf8');
    const forbidden = ['readFile', 'fetch', 'XMLHttpRequest', 'eval(', 'new Function', 'import('];
    for (const pattern of forbidden) {
      assert.ok(
        !src.includes(pattern),
        `media/overlay.js must not contain ${pattern} (LLD §2.5 Invariant 28 / security review)`
      );
    }
  });
});

// ---------------------------------------------------------------------------
// Specs — mutation-callback performance (LLD §2.5 Invariant 26)
// ---------------------------------------------------------------------------

describe('overlay mutation-callback perf (Issue #63, LLD §2.5 Invariant 26)', () => {
  it('mutation-observation path completes and overlay creation stays bounded', () => {
    const { win } = loadOverlay();

    // Invariant 26 budgets the mutation callback at under 1ms per invocation.
    // jsdom's DOM is far slower than a real webview, so a hard p95 < 1ms assert
    // here would be flaky noise. Measure the pure containment check and assert
    // the path completes; the 1ms budget itself is a real-browser/build-time
    // gate (Invariant 26 verification), not reproducible under jsdom.
    const pure = seam(win).resolveAndValidateHref;
    const pureStart = performance.now();
    for (let i = 0; i < 50; i++) {
      pure(INSIDE_HREF);
    }
    const pureMeanMs = (performance.now() - pureStart) / 50;
    assert.ok(Number.isFinite(pureMeanMs), 'the containment check runs 50 times without error');

    // The DOM path the observer callback drives must also complete and stay
    // bounded: 20 distinct re-renders each produce one overlay, no stacking.
    for (let i = 0; i < 20; i++) {
      const { svg, anchor } = mermaidSvg(win, { id: `mermaid-perf-${i}` });
      win.document.body.appendChild(svg);
      stubRect(anchor, { left: 0, top: 0, width: 30, height: 20 });
      seam(win).createOverlaysFor(svg);
    }
    assert.strictEqual(bodyOverlays(win.document).length, 20, 'each re-render adds exactly one overlay');

    console.log(
      `[overlay perf] resolveAndValidateHref mean ${pureMeanMs.toFixed(3)}ms over 50 jsdom runs; ` +
        'the Invariant-26 1ms budget is a real-webview build gate, not asserted under jsdom'
    );
  });
});

// ---------------------------------------------------------------------------
// Specs — evaluator adversarial tests (Issue #63)
//
// The BDD blocks above drive the exposed seam functions directly. These two
// specs exercise the wiring the seam bypasses: R-AC1's "on preview load or
// re-render" trigger (the MutationObserver registration + initial scan inside
// observeMermaidContainers) and R-AC2's scroll-event repositioning path
// (scheduleReposition → requestAnimationFrame → repositionAll).
// ---------------------------------------------------------------------------

describe('overlay wiring (evaluator, Issue #63)', () => {
  it('wires a MutationObserver on load — existing and newly added SVGs are overlaid, removed ones cleaned up', async () => {
    // R-AC1's trigger is "when the preview loads or re-renders": the IIFE must
    // (a) scan SVGs already in the document at load time and (b) react to later
    // DOM mutations. The sibling specs call createOverlaysFor directly, so a
    // regression that drops the observer registration or the initial scan loop
    // would pass every other spec in this file.
    const { dom, win } = makeOverlayDom();
    const doc = win.document;

    // (a) Initial scan — the diagram is present before the script loads.
    const initial = mermaidSvg(win, { id: 'mermaid-initial' });
    doc.body.appendChild(initial.svg);
    stubRect(initial.anchor, { left: 0, top: 0, width: 40, height: 20 });
    win.eval(fs.readFileSync(OVERLAY_SOURCE, 'utf8'));
    assert.strictEqual(
      bodyOverlays(doc).length,
      1,
      'a Mermaid SVG already in the document is overlaid on load'
    );

    // (b) Mutation callback — a re-render adds a second diagram with a fragment link.
    const added = mermaidSvg(win, { id: 'mermaid-added', href: FRAGMENT_HREF });
    doc.body.appendChild(added.svg);
    stubRect(added.anchor, { left: 0, top: 0, width: 40, height: 20 });
    await new Promise((r) => setTimeout(r, 0));
    assert.strictEqual(
      bodyOverlays(doc).length,
      2,
      'a newly added Mermaid SVG is overlaid by the mutation observer'
    );

    // (c) Removal path (Invariant 24) — dropping a diagram removes its overlay.
    initial.svg.remove();
    await new Promise((r) => setTimeout(r, 0));
    const overlays = bodyOverlays(doc);
    assert.strictEqual(overlays.length, 1, 'the removed diagram leaves no stale overlay');
    assert.strictEqual(
      overlays[0].getAttribute('href'),
      FRAGMENT_HREF,
      'the surviving overlay belongs to the still-present diagram'
    );
  });

  it('repositions overlays when a scroll event fires (event wiring)', async () => {
    // The 'repositions overlays on scroll and resize' spec drives
    // createOverlaysFor a second time; here the actual scroll-event listener
    // path (scheduleReposition → requestAnimationFrame → repositionAll) is
    // exercised so a regression that drops the listener registration is caught.
    const { win } = loadOverlay();
    const { svg, anchor } = mermaidSvg(win);
    win.document.body.appendChild(svg);
    stubRect(anchor, { left: 0, top: 0, width: 50, height: 30 });
    seam(win).createOverlaysFor(svg);
    assert.strictEqual(bodyOverlays(win.document)[0].style.top, '0px');

    // The target scrolls down; a real scroll event must reposition the overlay.
    stubRect(anchor, { left: 0, top: 100, width: 50, height: 30 });
    win.dispatchEvent(new win.Event('scroll'));

    // scheduleReposition runs through a rAF; await the next frame so the
    // reposition-all callback has executed before asserting.
    await new Promise<void>((resolve) => {
      (win as unknown as { requestAnimationFrame: (cb: () => void) => number }).requestAnimationFrame(
        () => resolve()
      );
    });

    const overlays = bodyOverlays(win.document);
    assert.strictEqual(overlays.length, 1, 'no duplicate overlay is created on scroll');
    assert.strictEqual(overlays[0].style.top, '100px', 'overlay tracks the target after a scroll event');
  });
});
