#!/usr/bin/env node
/**
 * Renderer conformance harness — EDF issue #47.
 *
 * Productionises the prototype specified in
 * `plugins/edf/docs/design/v1/lld-v1-e1-1-template-vocabulary.md` §B.1.3, and adds the
 * render-level checks demanded by decisions D5 (a `click` emitted before the node it names is
 * silently dropped) and D6 (a `classDef` does not carry into the next fenced block).
 *
 * The central lesson both decisions encode: **parse success is not evidence of correctness.**
 * A diagram that has quietly lost every one of its links parses, renders, and looks exactly
 * like one that never had any. Every check below that matters therefore asserts on the
 * rendered SVG, not on the parse result.
 *
 * Usage:
 *   node check-diagrams.mjs [--design-root <dir>] [--template] [--json] <file.md> [<file.md>…]
 *
 * `--template` marks the inputs as illustrative templates. Their example paths and `#LLD-`
 * fragments are not required to resolve — `skills/lld/template.md` is instantiated into other
 * projects, so its `src/lib/…` examples deliberately name nothing in this repo (LLD Invariant
 * 4, "or is a documented placeholder"). Parse, render, anchor-form, D5 and D6 checks still
 * apply in full: those are the checks that catch a template shipping broken examples.
 *
 * Exit codes:
 *   0 — every check passed for every input file
 *   1 — at least one check failed
 *   2 — usage error (no input files, or an unreadable file)
 */

// TODO(#47): `npm audit` reports a high-severity advisory for `lodash-es`, reached
// transitively as mermaid 11.12.2 -> @mermaid-js/parser -> langium -> chevrotain. The
// advisories are prototype pollution and `_.template` code injection, neither reachable
// here: this harness runs offline over markdown files already in the repo, and is test
// tooling that is never shipped with the plugin. `npm audit fix --force` resolves it only
// by installing mermaid 11.16.1, which would break the version pin that this whole
// artefact exists to measure against. Revisit when the conformance report is
// re-measured against a newer pinned Mermaid — see renderer-conformance-report.md
// "Re-verification trigger".

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';
import { sanitizeUrl } from '@braintree/sanitize-url';

/** @typedef {{line:number,type:string|null,parsed:boolean,error?:string,src:string}} BlockResult */
/** @typedef {{url:string,gate1:boolean,gate2:boolean,gate3:boolean,gate3Error?:string,survives:boolean,expected:boolean,ok:boolean}} SanitizerResult */
/** @typedef {{href:string,resolved:string,inside:boolean,exists:boolean,ok:boolean,line:number}} PathResult */
/** @typedef {{fragment:string,wellFormed:boolean,matched:boolean,ok:boolean,line:number}} AnchorResult */
/** @typedef {{line:number,clicks:number,anchors:number,roles:string[],styledRoles:string[],ok:boolean,error?:string}} RenderResult */

/** ADR-0026 anchor form, including the epic id. */
const ANCHOR_RE = /^#LLD-v\d+-e[\d-]+-[a-z0-9-]+$/;

/**
 * URLs the harness always pushes through the sanitiser gates, whatever the input file
 * contains. These are properties of the pinned toolchain rather than of any one document, and
 * the negative controls are what make a positive result credible.
 */
const SANITIZER_CONTROLS = [
  '../../../skills/lld/template.md',
  '#LLD-v1-e1-1-fixture-report',
  'https://mermaid.js.org/config/usage.html',
  'edf://src/lib/example/service.ts',
  'javascript:alert(1)',
];

// ---------------------------------------------------------------------------
// jsdom host — mermaid.render needs a DOM, and jsdom has no SVG layout engine.
// ---------------------------------------------------------------------------

let domHandle = null;
let mermaidHandle = null;
let purifyHandle = null;

/**
 * Build the jsdom window mermaid renders into, stubbing the SVG measurement APIs jsdom does
 * not implement. Without these stubs `mermaid.render` throws `getBBox is not a function` and
 * every render-level check silently degrades to a parse-only check — which is the exact
 * failure mode D5 exists to prevent.
 */
function getDom() {
  if (domHandle) return domHandle;

  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    pretendToBeVisual: true,
    url: 'http://localhost/',
  });
  const { window } = dom;

  const matrix = {
    a: 1, b: 0, c: 0, d: 1, e: 0, f: 0,
    inverse() { return this; },
    multiply() { return this; },
    translate() { return this; },
    scale() { return this; },
  };
  window.SVGElement.prototype.getBBox = () => ({ x: 0, y: 0, width: 100, height: 20 });
  window.SVGElement.prototype.getComputedTextLength = () => 100;
  window.SVGElement.prototype.getScreenCTM = () => matrix;
  window.SVGSVGElement.prototype.createSVGMatrix = () => matrix;

  const globals = [
    'window', 'document', 'navigator', 'Element', 'SVGElement', 'HTMLElement',
    'DOMParser', 'Node', 'NodeFilter', 'getComputedStyle', 'requestAnimationFrame',
    'MutationObserver', 'DOMRect',
  ];
  for (const key of globals) {
    if (window[key] === undefined) continue;
    // Some of these (`navigator` on Node >= 21) are getter-only globals, so a plain
    // assignment throws. Define over them instead, and skip any that are truly locked.
    try {
      Object.defineProperty(globalThis, key, {
        value: window[key], writable: true, configurable: true, enumerable: false,
      });
    } catch {
      /* non-configurable global — mermaid falls back to its own lookup */
    }
  }

  domHandle = dom;
  return dom;
}

/**
 * Load DOMPurify once, bound to the jsdom window.
 *
 * This must be a *dynamic* import taken after `getDom()` has installed the globals. DOMPurify
 * captures `window` when its module is first evaluated and exports a bare factory when there
 * is none — and mermaid imports the same cached module instance. A static top-level import
 * here therefore poisons mermaid's own copy, which surfaces much later and very confusingly
 * as `DOMPurify.addHook is not a function` inside `mermaid.parse`.
 */
async function getPurify() {
  if (purifyHandle) return purifyHandle;
  const dom = getDom();
  const createDOMPurify = (await import('dompurify')).default;
  purifyHandle = typeof createDOMPurify === 'function'
    ? createDOMPurify(dom.window)
    : createDOMPurify;
  return purifyHandle;
}

/** Load mermaid once, initialised at securityLevel 'strict' — the level the hosts use. */
async function getMermaid() {
  if (mermaidHandle) return mermaidHandle;
  getDom();
  await getPurify();
  const mermaid = (await import('mermaid')).default;
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', deterministicIds: true });
  mermaidHandle = mermaid;
  return mermaid;
}

// ---------------------------------------------------------------------------
// Markdown scanning
// ---------------------------------------------------------------------------

const FENCE_RE = /^(\s*)(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$/;

/**
 * Single pass over the document's fenced-block structure. Both the href scanner and the
 * diagram extractor need exactly this, and keeping one implementation means a fix to fence
 * handling cannot land in one of them and silently miss the other.
 *
 * Returns the source lines, one classification per line, and every fenced block found —
 * including a block whose fence is never closed, which is reported rather than dropped.
 *
 * @param {string} markdown
 */
function scanFences(markdown) {
  const lines = markdown.split('\n');
  const state = new Array(lines.length).fill('outside');
  const blocks = [];
  let fence = null;
  let buffer = [];
  let startLine = 0;

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const open = line.match(FENCE_RE);

    if (fence) {
      const isClose = open
        && open[2][0] === fence.marker[0]
        && open[2].length >= fence.marker.length
        && open[3] === '';
      if (isClose) {
        state[i] = 'marker';
        blocks.push({
          line: startLine, endLine: i + 1, isMermaid: fence.isMermaid,
          src: buffer.join('\n'), terminated: true,
        });
        fence = null;
        buffer = [];
      } else {
        state[i] = fence.isMermaid ? 'mermaid-body' : 'other-body';
        buffer.push(line);
      }
      continue;
    }

    if (open) {
      state[i] = 'marker';
      fence = { marker: open[2], isMermaid: open[3].toLowerCase() === 'mermaid' };
      startLine = i + 1;
      buffer = [];
    }
  }

  // A fence left open at EOF. Reported, never dropped: a truncated diagram that vanishes
  // from the checker's view is precisely the silent no-op this harness exists to catch.
  if (fence) {
    blocks.push({
      line: startLine, endLine: null, isMermaid: fence.isMermaid,
      src: buffer.join('\n'), terminated: false,
    });
  }

  return { lines, state, blocks };
}

/**
 * Replace inline code spans and every fenced block that is *not* a mermaid block with blank
 * space, preserving line numbering so that findings still cite the right line.
 *
 * This is not a nicety. A prototype that skipped it reported a finding against a
 * `click … href "edf://…"` string quoted inside a table cell as documentation *about* the
 * retired scheme. A checker that cries wolf on its own migration notes gets switched off.
 *
 * @param {string} markdown
 * @returns {string}
 */
function stripNonMermaidContext(markdown) {
  const { lines, state } = scanFences(markdown);

  return lines.map((line, i) => {
    if (state[i] === 'other-body') return '';
    if (state[i] === 'mermaid-body' || state[i] === 'marker') return line;
    // Outside any fence: blank out inline code spans, keeping length so columns still line up.
    return line.replace(/`[^`]*`/g, (m) => ' '.repeat(m.length));
  }).join('\n');
}

/**
 * Every fenced mermaid block, with the 1-based line number of its opening fence. An
 * unterminated block is included and carries `terminated: false`.
 *
 * @param {string} markdown
 * @returns {{line:number,endLine:number|null,src:string,terminated:boolean}[]}
 */
function extractMermaidBlocks(markdown) {
  return scanFences(markdown).blocks.filter((b) => b.isMermaid);
}

// ---------------------------------------------------------------------------
// Check 1 — parse
// ---------------------------------------------------------------------------

/**
 * Parse every fenced mermaid block under securityLevel 'strict'.
 * @param {string} markdown
 * @returns {Promise<BlockResult[]>}
 */
export async function parseBlocks(markdown) {
  const mermaid = await getMermaid();
  const results = [];

  for (const block of extractMermaidBlocks(markdown)) {
    try {
      const parsed = await mermaid.parse(block.src);
      results.push({
        line: block.line,
        type: (parsed && parsed.diagramType) || null,
        parsed: true,
        src: block.src,
      });
    } catch (err) {
      results.push({
        line: block.line,
        type: null,
        parsed: false,
        error: String(err && err.message ? err.message : err).split('\n')[0],
        src: block.src,
      });
    }
  }

  return results;
}

// ---------------------------------------------------------------------------
// Check 2 — sanitiser
// ---------------------------------------------------------------------------

/**
 * A URL is expected to survive sanitisation when it carries no scheme (a relative path or a
 * fragment) or carries http/https. Anything else — `edf://`, `javascript:`, `vscode:`,
 * `file:` — must be stripped before it reaches the DOM.
 * @param {string} url
 */
function expectedToSurvive(url) {
  if (!/^[a-z][a-z0-9+.-]*:/i.test(url)) return true;
  return /^https?:/i.test(url);
}

/**
 * Push each URL through the three gates that stand between an authored href and a clickable
 * anchor: `@braintree/sanitize-url`, DOMPurify's SVG profile, and mermaid's own render.
 *
 * Gate 3 is the one that matters — the first two are the libraries mermaid uses internally,
 * but only a render proves what actually reaches the DOM.
 *
 * @param {string[]} urls
 * @returns {Promise<SanitizerResult[]>}
 */
export async function checkSanitizer(urls) {
  const dom = getDom();
  const purify = await getPurify();
  const results = [];

  for (const url of urls) {
    const gate1 = sanitizeUrl(url) === url;

    const cleaned = purify.sanitize(`<svg><a href="${url}"><text>x</text></a></svg>`, {
      USE_PROFILES: { svg: true },
    });
    const gate2 = cleaned.includes(`href="${url}"`);

    // A render crash is NOT evidence that the sanitiser stripped the URL — it is a missing
    // measurement. Recording it as `gate3 = false` would make the negative controls pass for
    // the wrong reason, and those rows are exactly what makes the positive rows credible.
    let gate3 = false;
    let gate3Error;
    try {
      const svg = await renderSource(`flowchart TD\n    N["node"]\n    click N href "${url}" _self\n`);
      gate3 = countAnchors(svg, dom) > 0;
    } catch (err) {
      gate3Error = String(err && err.message ? err.message : err).split('\n')[0];
    }

    const survives = gate1 && gate2 && gate3;
    const expected = expectedToSurvive(url);
    // Unmeasured is never OK, however the expectation happens to line up.
    const ok = gate3Error === undefined && survives === expected;
    results.push({ url, gate1, gate2, gate3, gate3Error, survives, expected, ok });
  }

  return results;
}

// ---------------------------------------------------------------------------
// Check 3 — path resolution
// ---------------------------------------------------------------------------

const CLICK_HREF_RE = /^\s*click\s+\S+\s+href\s+"([^"]+)"/gm;
const MD_LINK_RE = /\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;

/** Line number (1-based) of a character offset in `text`. */
function lineOf(text, index) {
  return text.slice(0, index).split('\n').length;
}

/**
 * Resolve every click href and markdown link target against the *document's own directory* —
 * the base both GitHub and VS Code use, and the one ADR-0039's superseded repo-root form got
 * wrong.
 *
 * @param {string} markdown
 * @param {string} docPath
 * @param {string} designRoot
 * @returns {PathResult[]}
 */
export function checkPaths(markdown, docPath, designRoot, isTemplate = false) {
  const scanned = stripNonMermaidContext(markdown);
  const docDir = path.dirname(path.resolve(docPath));
  const root = path.resolve(designRoot);
  const results = [];
  const seen = new Set();

  const candidates = [];
  for (const m of scanned.matchAll(CLICK_HREF_RE)) candidates.push([m[1], m.index]);
  for (const m of scanned.matchAll(MD_LINK_RE)) candidates.push([m[1], m.index]);

  for (const [raw, index] of candidates) {
    const href = raw.trim();
    if (!href) continue;
    if (href.startsWith('#')) continue;            // fragments — checkAnchors owns these
    if (/^[a-z][a-z0-9+.-]*:/i.test(href)) continue; // absolute URLs and other schemes

    const line = lineOf(scanned, index);
    const key = `${href}@${line}`;
    if (seen.has(key)) continue;
    seen.add(key);

    if (href.startsWith('/')) {
      results.push({ href, resolved: href, inside: false, exists: false, ok: false, line });
      continue;
    }

    const target = href.split('#')[0];
    const resolved = path.resolve(docDir, target);
    const inside = resolved === root || resolved.startsWith(root + path.sep);
    const exists = fs.existsSync(resolved);

    // A `<…>` marker is the documented placeholder convention, and every path in a template is
    // illustrative by definition. Containment is still enforced in both cases: an escaping
    // path is a defect wherever it appears.
    const placeholder = /[<>]/.test(href) || isTemplate;
    const ok = inside && (exists || placeholder);
    results.push({ href, resolved, inside, exists, placeholder, ok, line });
  }

  return results;
}

// ---------------------------------------------------------------------------
// Check 4 — anchors
// ---------------------------------------------------------------------------

/**
 * Every `#LLD-` fragment must be well-formed per ADR-0026 and must match an `<a id="…">` in
 * the same file, case-sensitively. A fragment with no target is a silent no-op — no scroll,
 * no error, nothing to notice.
 *
 * @param {string} markdown
 * @returns {AnchorResult[]}
 */
export function checkAnchors(markdown, isTemplate = false) {
  const scanned = stripNonMermaidContext(markdown);
  const ids = new Set(
    [...markdown.matchAll(/<a\s+id="([^"]+)"\s*>/g)].map((m) => m[1]),
  );

  const results = [];
  const seen = new Set();
  const candidates = [];
  for (const m of scanned.matchAll(CLICK_HREF_RE)) candidates.push([m[1], m.index]);
  for (const m of scanned.matchAll(MD_LINK_RE)) candidates.push([m[1], m.index]);

  for (const [raw, index] of candidates) {
    const href = raw.trim();
    if (!href.startsWith('#LLD-')) continue;

    const line = lineOf(scanned, index);
    const key = `${href}@${line}`;
    if (seen.has(key)) continue;
    seen.add(key);

    const wellFormed = ANCHOR_RE.test(href);
    const matched = ids.has(href.slice(1));
    // A template's example fragments point at sections that only exist once it is
    // instantiated. The *form* is still enforced — a malformed anchor is a defect anywhere.
    results.push({
      fragment: href,
      wellFormed,
      matched,
      ok: wellFormed && (matched || isTemplate),
      line,
    });
  }

  return results;
}

// ---------------------------------------------------------------------------
// Check 5 — render (D5 anchors, D6 palette) — one render pass, two assertions
// ---------------------------------------------------------------------------

let renderSeq = 0;

/** Render one diagram source and return the SVG string. */
async function renderSource(src) {
  const mermaid = await getMermaid();
  renderSeq += 1;
  const { svg } = await mermaid.render(`edfConformance${renderSeq}`, src);
  return svg;
}

/**
 * Count anchor elements carrying an href in a rendered SVG.
 *
 * Parsed as `text/html`, deliberately, **not** as `image/svg+xml`. When a node label contains
 * `<br/>`, mermaid emits it into a `foreignObject` as unclosed `<br>` — valid HTML, invalid
 * XML. An XML parse of that SVG returns a `parsererror` document and therefore *zero* anchors,
 * which reads exactly like the D5 defect this function exists to detect.
 *
 * The harness's own first implementation did that, and reported two clean diagrams as having
 * silently lost every link. Same failure class the epic exists to remove, one level up: the
 * checker parsed successfully and was measuring the wrong thing.
 */
function countAnchors(svg, dom) {
  const doc = new dom.window.DOMParser().parseFromString(svg, 'text/html');
  return doc.querySelectorAll('a[href], a[xlink\\:href]').length;
}

/**
 * Does the emitted SVG carry a CSS rule produced by a `classDef` for this role?
 *
 * Measured on 11.12.2: an applied `classDef` emits selectors of the form `.role>*{`,
 * `.role span{`, `.role tspan{`. The `>` rule is the reliable one to probe for.
 *
 * A loose `\.role\b` test is NOT safe, and was the original implementation's bug: mermaid
 * always emits a built-in `.error-icon{…}` and `.error-text{…}` into every stylesheet, which
 * that pattern matches. The `error` role could therefore never fail the D6 check — the one
 * palette role whose name collides with mermaid's own, silently exempted from the check
 * written to catch it.
 *
 * @param {string} svg
 * @param {string} role
 */
function rolePaletteApplied(svg, role) {
  const escaped = role.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  // The serialised SVG encodes the child combinator as `&gt;`, so accept either form.
  return new RegExp(`\\.${escaped}\\s*(?:>|&gt;)\\s*\\*`).test(svg);
}

/** `click X href "…"` directives declared in a block's source. */
function countClickDirectives(src) {
  return (src.match(/^\s*click\s+\S+\s+href\s+"/gm) || []).length;
}

/**
 * Palette roles a block *references* via a `class` assignment.
 *
 * Only two-token statements are role assignments (`class A,B new`). A `classDiagram`
 * declaration — `class Foo`, `class Foo["a/b"]`, `class Foo {` — is not one, and must not be
 * mistaken for a reference to a role named after the class.
 */
function referencedRoles(src) {
  const roles = new Set();
  for (const line of src.split('\n')) {
    const m = line.match(/^\s*class\s+([A-Za-z0-9_][A-Za-z0-9_,\s-]*?)\s+([A-Za-z][A-Za-z0-9_-]*)\s*$/);
    if (m) roles.add(m[2]);
  }
  // The `A:::role` shorthand assigns a class too, and is easy to write by accident when
  // copying flowchart examples. Without this the same D6 violation goes unchecked.
  for (const m of src.matchAll(/:::([A-Za-z][A-Za-z0-9_-]*)/g)) roles.add(m[1]);
  return [...roles];
}

/**
 * Render every block that declares a `click` or references a palette role, then assert on the
 * emitted SVG:
 *
 *   D5 — rendered anchor count must equal declared click count. A `click` naming a node that
 *        has not been declared yet is silently dropped: parses, renders, yields no anchor.
 *   D6 — every referenced role must have a CSS rule in the SVG this block produced. A
 *        `classDef` does not carry across fenced blocks, so a `class X role` whose `classDef`
 *        lives in an earlier block parses, renders, and applies no styling whatsoever.
 *
 * Both are invisible to `mermaid.parse`, which is why one render pass serves both.
 *
 * @param {string} markdown
 * @returns {Promise<RenderResult[]>}
 */
export async function checkAnchorsRendered(markdown) {
  const dom = getDom();
  const results = [];

  for (const block of extractMermaidBlocks(markdown)) {
    const clicks = countClickDirectives(block.src);
    const roles = referencedRoles(block.src);
    if (clicks === 0 && roles.length === 0) continue;

    let svg;
    try {
      svg = await renderSource(block.src);
    } catch (err) {
      results.push({
        line: block.line,
        clicks,
        anchors: 0,
        roles,
        styledRoles: [],
        ok: false,
        error: String(err && err.message ? err.message : err).split('\n')[0],
      });
      continue;
    }

    const anchors = countAnchors(svg, dom);
    const styledRoles = roles.filter((role) => rolePaletteApplied(svg, role));
    const ok = anchors === clicks && styledRoles.length === roles.length;

    results.push({ line: block.line, clicks, anchors, roles, styledRoles, ok });
  }

  return results;
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

/** Walk up from `start` looking for a `.git` entry — the single-module `design-root` default. */
function findRepoRoot(start) {
  let dir = path.resolve(start);
  for (;;) {
    if (fs.existsSync(path.join(dir, '.git'))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return path.resolve(start);
    dir = parent;
  }
}

function parseArgv(argv) {
  const files = [];
  let designRoot = null;
  let json = false;
  let template = false;

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--json') json = true;
    else if (arg === '--template') template = true;
    else if (arg === '--design-root') { designRoot = argv[i + 1]; i += 1; }
    else if (arg.startsWith('--design-root=')) designRoot = arg.slice('--design-root='.length);
    else files.push(arg);
  }

  return { files, designRoot, json, template };
}

/**
 * Run every check over every named file.
 * @param {string[]} argv
 * @returns {Promise<number>} process exit code
 */
export async function main(argv) {
  const { files, designRoot, json, template } = parseArgv(argv);

  if (files.length === 0) {
    process.stderr.write('Usage: node check-diagrams.mjs [--design-root <dir>] [--template] [--json] <file.md>…\n');
    return 2;
  }

  for (const file of files) {
    if (!fs.existsSync(file)) {
      process.stderr.write(`No such file: ${file}\n`);
      return 2;
    }
  }

  const root = designRoot ? path.resolve(designRoot) : findRepoRoot(path.dirname(path.resolve(files[0])));
  const report = { ok: true, designRoot: root, template, files: [] };
  const lines = [];

  // Toolchain-level, file-independent: does the sanitiser behave as ADR-0039 recorded?
  const sanitizer = await checkSanitizer(SANITIZER_CONTROLS);
  const sanitizerOk = sanitizer.every((r) => r.ok);
  if (!sanitizerOk) report.ok = false;

  for (const file of files) {
    const markdown = fs.readFileSync(file, 'utf8');
    const blocks = await parseBlocks(markdown);
    const unterminated = extractMermaidBlocks(markdown).filter((b) => !b.terminated);
    const anyParseFailure = blocks.some((b) => !b.parsed) || unterminated.length > 0;

    // Parse gates the rest: navigability findings about a diagram that does not render are
    // noise, not evidence.
    const rendered = anyParseFailure ? [] : await checkAnchorsRendered(markdown);
    const paths = anyParseFailure ? [] : checkPaths(markdown, file, root, template);
    const anchors = anyParseFailure ? [] : checkAnchors(markdown, template);

    const entry = {
      path: file,
      unterminatedBlocks: unterminated.map((b) => ({ line: b.line })),
      blocks: blocks.map(({ src, ...rest }) => rest),
      paths,
      anchors,
      rendered,
      sanitizer,
    };
    report.files.push(entry);

    lines.push(`\n${file}`);
    for (const b of blocks) {
      lines.push(b.parsed
        ? `  ok    parse   line ${b.line}  ${b.type}`
        : `  FAIL  parse   line ${b.line}  ${b.error}`);
    }
    for (const b of unterminated) {
      lines.push(`  FAIL  fence   line ${b.line}  mermaid block is never closed — truncated diagram`);
    }
    if (anyParseFailure) {
      lines.push('  ----  navigability checks skipped: a block in this file does not parse');
      report.ok = false;
      continue;
    }
    for (const r of rendered) {
      const detail = `clicks=${r.clicks} anchors=${r.anchors} roles=[${r.roles}] styled=[${r.styledRoles}]`;
      lines.push(r.ok
        ? `  ok    render  line ${r.line}  ${detail}`
        : `  FAIL  render  line ${r.line}  ${detail}${r.error ? ` ${r.error}` : ''}`);
      if (!r.ok) report.ok = false;
    }
    for (const p of paths) {
      const pathLabel = p.ok && !p.exists ? 'plchldr' : (p.ok ? 'ok     ' : 'FAIL   ');
      lines.push(p.ok
        ? `  ${pathLabel} path   line ${p.line}  ${p.href}`
        : `  FAIL    path   line ${p.line}  ${p.href} (inside=${p.inside} exists=${p.exists})`);
      if (!p.ok) report.ok = false;
    }
    for (const a of anchors) {
      lines.push(a.ok
        ? `  ok    anchor  line ${a.line}  ${a.fragment}`
        : `  FAIL  anchor  line ${a.line}  ${a.fragment} (wellFormed=${a.wellFormed} matched=${a.matched})`);
      if (!a.ok) report.ok = false;
    }
  }

  if (json) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  } else {
    process.stdout.write(`design-root: ${root}\n`);
    for (const s of sanitizer) {
      const verdict = s.ok ? 'ok   ' : 'FAIL ';
      const detail = s.gate3Error ? ` RENDER-ERROR: ${s.gate3Error}` : '';
      process.stdout.write(`  ${verdict} sanitize  survives=${s.survives} expected=${s.expected}  ${s.url}${detail}\n`);
    }
    process.stdout.write(`${lines.join('\n')}\n\n${report.ok ? 'PASS' : 'FAIL'}\n`);
  }

  return report.ok ? 0 : 1;
}

const invokedDirectly = process.argv[1]
  && path.resolve(process.argv[1]) === path.resolve(fileURLToPath(import.meta.url));

if (invokedDirectly) {
  process.exit(await main(process.argv.slice(2)));
}
