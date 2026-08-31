/**
 * Issue #50 (v1-e1-2): Insert Review Comment command wiring.
 *
 * Integration specs for src/extension.ts — insertReviewComment / insertionLineFor
 * — and the review-marker insertion it drives (src/review-insert.ts). LLD §2.3
 * (Command wiring and target resolution, 0.7 never-guess) Invariants 14-17,
 * reworked per review feedback: there is no heading quick-pick. The insertion
 * line comes from `insertionLineFor`, which discriminates two flows:
 *   - a text editor focused and it is the resolved source → the cursor line;
 *   - no text editor focused (the preview webview holds focus) → the
 *     top-visible source line, i.e. the line the preview click scrolled to the
 *     top of the source viewport. The source SELECTION is deliberately NOT used
 *     here — a single preview click never moves it in this VS Code build.
 *
 * The handler is called directly with an injected fake EditorTracker and a
 * capturing log (dependency injection) so every branch is deterministic in the
 * shared host. 0.7 makes the focused markdown preview the ONLY resolution
 * trigger, so tests that must reach insertion stub the active tab to be a
 * markdown preview titled `Preview <basename>` whose basename matches the
 * injected editor's file. No HTTP is involved, so the repo's respx/MSW rule
 * does not apply.
 */
import * as vscode from 'vscode';
import * as assert from 'assert';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { applyMarker, insertReviewComment, insertionLineFor } from '../../src/extension';
import { EditorTracker, NO_PREVIEW_MSG } from '../../src/editor-tracker';
import { REVIEW_MARKER } from '../../src/review-insert';

/** Shared fixture: a markdown document with one ## and one ### heading. */
const MARKDOWN_WITH_HEADINGS = [
  '# Title',
  '',
  '## Section One',
  'Some prose here.',
  '### Sub Section',
  'More prose.',
  ''
].join('\n');

// ---------------------------------------------------------------------------
// Test-host helpers
// ---------------------------------------------------------------------------

async function settle(ms = 150): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

/** A focused built-in markdown preview tab titled `label`. */
function previewTab(label: string): vscode.Tab {
  return { label, input: { viewType: 'markdown.preview' } } as unknown as vscode.Tab;
}

/**
 * Stub the window's active tab so insertReviewComment sees a focused markdown
 * preview. 0.7 never guesses — without a preview tab the handler stops with
 * NO_PREVIEW_MSG before any insertion, so every insertion spec pins it.
 * `vscode.window.tabGroups` is a getter-only accessor, so it is overridden with
 * `Object.defineProperty` and restored by re-applying the captured descriptor.
 */
function stubActiveTab(tab: vscode.Tab | undefined): { restore: () => void } {
  const descriptor = Object.getOwnPropertyDescriptor(vscode.window, 'tabGroups');
  Object.defineProperty(vscode.window, 'tabGroups', {
    value: { activeTabGroup: { activeTab: tab } },
    configurable: true,
    writable: true
  });
  return {
    restore: () => {
      if (descriptor) {
        Object.defineProperty(vscode.window, 'tabGroups', descriptor);
      }
    }
  };
}

/** Monkey-patch vscode.window.showErrorMessage and capture the messages. */
function stubErrorMessage(): { calls: string[]; restore: () => void } {
  const original = vscode.window.showErrorMessage;
  const testWindow = vscode.window as unknown as {
    showErrorMessage: typeof vscode.window.showErrorMessage;
  };
  const calls: string[] = [];
  testWindow.showErrorMessage = ((message: string) => {
    calls.push(message);
    return Promise.resolve(undefined);
  }) as unknown as typeof vscode.window.showErrorMessage;
  return {
    calls,
    restore: () => {
      testWindow.showErrorMessage = original;
    }
  };
}

/** Monkey-patch vscode.window.showWarningMessage and capture the messages. */
function stubWarningMessage(): { calls: string[]; restore: () => void } {
  const original = vscode.window.showWarningMessage;
  const testWindow = vscode.window as unknown as {
    showWarningMessage: typeof vscode.window.showWarningMessage;
  };
  const calls: string[] = [];
  testWindow.showWarningMessage = ((message: string) => {
    calls.push(message);
    return Promise.resolve(undefined);
  }) as unknown as typeof vscode.window.showWarningMessage;
  return {
    calls,
    restore: () => {
      testWindow.showWarningMessage = original;
    }
  };
}

/** Create a throwaway dir for file-backed markdown documents. */
function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'edf-review-cmd-'));
}

/** Write a markdown file (creating parent dirs) so it can be opened by URI. */
function writeMarkdownFile(filePath: string, content: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

/** A basename unique to this test run — a leaked doc can never make matching ambiguous. */
let uniqueCounter = 0;
function uniqueMarkdownBase(): string {
  uniqueCounter += 1;
  return `doc-${process.pid}-${uniqueCounter}.md`;
}

/** Close every opened doc then remove the temp dir (releases Windows file handles). */
async function cleanupTempDir(
  dir: string,
  opened: readonly vscode.TextDocument[]
): Promise<void> {
  for (const doc of opened) {
    if (!doc.isClosed) {
      try {
        await vscode.window.showTextDocument(doc, { preview: false, preserveFocus: false });
      } catch {
        // The document may already have been closed by a previous step.
      }
    }
  }
  await vscode.commands.executeCommand('workbench.action.closeAllEditors');
  await settle();
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {
    // Best-effort cleanup; a leftover temp dir cannot affect resolution.
  }
}

/**
 * Fixture: a file-backed markdown editor with a unique basename, plus cleanup.
 * 0.7 resolution matches the preview title against the editor's file basename,
 * so every insertion spec needs a real file path it controls.
 */
async function fileMarkdownFixture(content: string): Promise<{
  base: string;
  doc: vscode.TextDocument;
  editor: vscode.TextEditor;
  cleanup: () => Promise<void>;
}> {
  const dir = makeTempDir();
  const opened: vscode.TextDocument[] = [];
  const base = uniqueMarkdownBase();
  const filePath = path.join(dir, base);
  writeMarkdownFile(filePath, content);
  const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(filePath));
  opened.push(doc);
  const editor = await vscode.window.showTextDocument(doc);
  return {
    base,
    doc,
    editor,
    cleanup: () => cleanupTempDir(dir, opened)
  };
}

/**
 * Move the fixture editor's selection onto `line`. Used to stand in for a cursor
 * the user actually placed in the source editor — the source-focused flow
 * (`insertionLineFor` uses the cursor line when a text editor holds focus).
 */
function selectLine(editor: vscode.TextEditor, line: number): void {
  const pos = new vscode.Position(line, 0);
  editor.selection = new vscode.Selection(pos, pos);
}

/**
 * Stub vscode.window.activeTextEditor so the insertion-line discriminator sees
 * a chosen focused editor (undefined = the preview webview holds focus).
 */
function stubActiveTextEditor(editor: vscode.TextEditor | undefined): { restore: () => void } {
  const descriptor = Object.getOwnPropertyDescriptor(vscode.window, 'activeTextEditor');
  Object.defineProperty(vscode.window, 'activeTextEditor', {
    value: editor,
    configurable: true,
    writable: true
  });
  return {
    restore: () => {
      if (descriptor) {
        Object.defineProperty(vscode.window, 'activeTextEditor', descriptor);
      }
    }
  };
}

/** Index of the `## Section One` heading in every insertion fixture below. */
const SECTION_ONE_LINE = 2;

// ---------------------------------------------------------------------------
// Specs
// ---------------------------------------------------------------------------

beforeEach(async () => {
  // Start each test with no open editors. Hide rather than close so an untitled
  // document can never trigger a save prompt that hangs the host (Issue #50).
  vscode.window.visibleTextEditors.forEach((editor) => editor.hide());
  await settle();
});

afterEach(() => {
  vscode.window.visibleTextEditors.forEach((editor) => editor.hide());
});

describe('insertReviewComment — insertion below the selected line (Issue #50, LLD §2.3)', () => {
  it('inserts the marker on a new line after the selected line', async () => {
    const content = ['# Title', '', '## Section One', 'Some prose here.', ''].join('\n');
    const fixture = await fileMarkdownFixture(content);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };
    const logCalls: string[] = [];

    selectLine(fixture.editor, SECTION_ONE_LINE);
    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    try {
      await insertReviewComment(tracker, (m) => logCalls.push(m));

      const expected = [
        '# Title',
        '',
        '## Section One',
        REVIEW_MARKER,
        'Some prose here.',
        ''
      ].join('\n');
      assert.strictEqual(fixture.doc.getText(), expected, 'marker goes on the line after the selected line');
      assert.strictEqual(logCalls.length, 0, 'a successful insertion is not a failure');
    } finally {
      tab.restore();
      await fixture.cleanup();
    }
  });

  it('inserts after existing consecutive review markers, preserving their order', async () => {
    const content = [
      '# Title',
      '',
      '## Section One',
      '> **[Review]:** first note',
      '> **[Review]:** second note',
      ''
    ].join('\n');
    const fixture = await fileMarkdownFixture(content);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };

    selectLine(fixture.editor, SECTION_ONE_LINE);
    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    try {
      await insertReviewComment(tracker, () => {});

      // Story 2.1 AC9: the new marker goes after the existing consecutive
      // markers, preserving their order — never before them.
      const expected = [
        '# Title',
        '',
        '## Section One',
        '> **[Review]:** first note',
        '> **[Review]:** second note',
        REVIEW_MARKER,
        ''
      ].join('\n');
      assert.strictEqual(
        fixture.doc.getText(),
        expected,
        'new marker must follow existing markers in order'
      );
    } finally {
      tab.restore();
      await fixture.cleanup();
    }
  });

  it('applies the insertion as a single edit (document.version increases by exactly 1)', async () => {
    const fixture = await fileMarkdownFixture(MARKDOWN_WITH_HEADINGS);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };

    selectLine(fixture.editor, SECTION_ONE_LINE);
    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    try {
      const versionBefore = fixture.doc.version;

      await insertReviewComment(tracker, () => {});

      // LLD §2.3 Invariant 16 + constraint: exactly one editor.edit call. Two
      // edits would give correct text but a two-step undo stack.
      assert.strictEqual(
        fixture.doc.version,
        versionBefore + 1,
        'insertion must be exactly one editor.edit call'
      );
    } finally {
      tab.restore();
      await fixture.cleanup();
    }
  });

  it('focuses the editor with the cursor immediately after the marker text', async () => {
    const content = ['# Title', '', '## Section One', 'Some prose here.', ''].join('\n');
    const fixture = await fileMarkdownFixture(content);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };

    selectLine(fixture.editor, SECTION_ONE_LINE);
    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    try {
      await insertReviewComment(tracker, () => {});

      // '## Section One' is line index 2 in the fixture and no marker follows, so
      // the marker is inserted on the new line immediately after it (line 3).
      const insertedLine = 3;
      assert.strictEqual(
        vscode.window.activeTextEditor,
        fixture.editor,
        'the resolved source editor must be focused after insertion'
      );
      assert.strictEqual(fixture.editor.selection.active.line, insertedLine, 'cursor is on the inserted line');
      assert.strictEqual(
        fixture.editor.selection.active.character,
        REVIEW_MARKER.length,
        'cursor sits immediately after the marker text'
      );
    } finally {
      tab.restore();
      await fixture.cleanup();
    }
  });

  it('honors CRLF line endings when inserting the marker (review finding #73)', async () => {
    // The marker line must match the document's line endings — a hard-coded LF
    // insert into a CRLF file produces a mixed line-ending edit.
    const content = ['# Title', '', '## Section One', 'Some prose here.', ''].join('\r\n');
    const fixture = await fileMarkdownFixture(content);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };

    selectLine(fixture.editor, SECTION_ONE_LINE);
    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    try {
      await insertReviewComment(tracker, () => {});

      const expected = [
        '# Title',
        '',
        '## Section One',
        REVIEW_MARKER,
        'Some prose here.',
        ''
      ].join('\r\n');
      assert.strictEqual(
        fixture.doc.getText(),
        expected,
        'marker line must use the document\'s CRLF line endings'
      );
    } finally {
      tab.restore();
      await fixture.cleanup();
    }
  });

  it('places the marker on its own line when the selected line is the final line without a trailing newline (review finding #73 re-review)', async () => {
    // A file that ends with the selected line and no trailing newline: `at + 1 ===
    // lines.length`, so Position(at + 1, 0) is end-of-document and a bare insert
    // would glue the marker onto it. The separator must keep it on its own line.
    const content = ['# Title', '', '## Section One'].join('\n');
    const fixture = await fileMarkdownFixture(content);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };

    selectLine(fixture.editor, SECTION_ONE_LINE);
    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    try {
      await insertReviewComment(tracker, () => {});

      const expected = ['# Title', '', '## Section One', REVIEW_MARKER, ''].join('\n');
      assert.strictEqual(
        fixture.doc.getText(),
        expected,
        'marker must land on its own line, never glued onto the line above'
      );
    } finally {
      tab.restore();
      await fixture.cleanup();
    }
  });

  it('logs and shows a message when editor.edit returns false (LLD §2.3 error table)', async () => {
    // The failure path is tested against applyMarker directly: routing through
    // resolveTarget's showTextDocument would need a registered document, and its
    // fresh editor instance would carry a working edit — the stub would never run.
    const logCalls: string[] = [];
    const fakeEditor = {
      document: {
        uri: vscode.Uri.file(path.join('C:/__edf_fixture__', 'fake-fail.md')),
        isClosed: false,
        getText: () => ['# Title', '', '## Section One', ''].join('\n'),
        eol: vscode.EndOfLine.LF
      },
      edit: async () => false,
      selection: {
        anchor: { line: 2, character: 0 },
        active: { line: 2, character: 0 }
      },
      viewColumn: 1
    } as unknown as vscode.TextEditor;

    const errorStub = stubErrorMessage();
    try {
      await applyMarker(fakeEditor, SECTION_ONE_LINE, (m) => logCalls.push(m));

      assert.deepStrictEqual(
        logCalls,
        ['failed to insert review marker'],
        'an edit failure must be logged exactly once'
      );
      assert.deepStrictEqual(
        errorStub.calls,
        ['Failed to insert review marker'],
        `expected one error message, got ${JSON.stringify(errorStub.calls)}`
      );
    } finally {
      errorStub.restore();
    }
  });
});

describe('insertionLineFor — which line gets the marker (Issue #63, review feedback)', () => {
  const uri = vscode.Uri.file(path.join('C:/__edf_fixture__', 'flow.md'));
  const target = (
    visibleTop: number | undefined,
    cursorLine: number
  ): vscode.TextEditor =>
    ({
      document: { uri },
      selection: {
        anchor: { line: cursorLine, character: 0 },
        active: { line: cursorLine, character: 0 }
      },
      visibleRanges:
        typeof visibleTop === 'number'
          ? [
              {
                start: { line: visibleTop, character: 0 },
                end: { line: visibleTop + 20, character: 0 }
              }
            ]
          : undefined
    }) as unknown as vscode.TextEditor;

  it('uses the top-visible line when no text editor holds focus (preview focused) — NOT the stale cursor', () => {
    // The reviewer clicked a line that scrolled the source so its top is line 40;
    // the cursor is stale at line 90 (the old bug put the marker at the end).
    const editor = target(40, 90);
    assert.strictEqual(insertionLineFor(editor, undefined), 40);
  });

  it('uses the cursor line when the focused editor is the resolved source', () => {
    const editor = target(0, 3);
    const focused = { document: { uri } } as unknown as vscode.TextEditor;
    assert.strictEqual(insertionLineFor(editor, focused), 3);
  });

  it('ignores a focused editor that is a different document (preview path still applies)', () => {
    const editor = target(7, 50);
    const other = {
      document: { uri: vscode.Uri.file(path.join('C:/__edf_fixture__', 'other.md')) }
    } as unknown as vscode.TextEditor;
    assert.strictEqual(insertionLineFor(editor, other), 7);
  });

  it('falls back to the cursor line when the editor has no visible range', () => {
    const editor = target(undefined, 12);
    assert.strictEqual(insertionLineFor(editor, undefined), 12);
  });
});

describe('insertReviewComment — preview holds focus (Issue #63: marker below the clicked line, not the stale cursor)', () => {
  it('inserts below the top-visible source line, never below a stale end-of-file cursor', async () => {
    // Long document so the source can actually scroll. The test host's editor
    // has a tall viewport and its revealRange(AtTop) settles a few lines short
    // of the target (observed: 40→35, 200→195), so the top-visible line is read
    // at runtime rather than pinned to the reveal target — the discriminator the
    // spec guards is "marker below the line the click scrolled to the top of the
    // viewport, NOT below a stale cursor". The reviewer's cursor is left stale
    // at line 350 (the original bug put the marker at the end of the file).
    const lines = Array.from({ length: 400 }, (_, i) =>
      i === 0 ? '# Title' : i === 399 ? '' : `Line ${i}`
    );
    const fixture = await fileMarkdownFixture(lines.join('\n'));
    selectLine(fixture.editor, 350);
    fixture.editor.revealRange(new vscode.Range(200, 0, 200, 0), vscode.TextEditorRevealType.AtTop);
    await settle();
    const top = fixture.editor.visibleRanges[0]?.start.line;
    assert.ok(
      typeof top === 'number' && top >= 100 && top < 300,
      `revealRange(200) must scroll the source near line 200, got top-visible ${top}`
    );

    const tracker: EditorTracker = { recent: () => [fixture.editor], last: () => fixture.editor };
    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    const noEditor = stubActiveTextEditor(undefined);
    try {
      await insertReviewComment(tracker, () => {});

      const after = fixture.doc.getText().split(/\r?\n/);
      assert.strictEqual(
        after[top + 1],
        REVIEW_MARKER,
        `marker goes below the top-visible (clicked) line ${top}, never the stale cursor`
      );
      assert.strictEqual(
        after[top + 2],
        `Line ${top + 1}`,
        'the source line below the marker is intact'
      );
      assert.strictEqual(
        fixture.editor.visibleRanges[0]?.start.line,
        top,
        'insertion must not scroll the source (the top read is the line the marker used)'
      );
      assert.strictEqual(after[351], 'Line 350', 'the stale-cursor line is left untouched');
      assert.strictEqual(
        after.length,
        lines.length + 1,
        'exactly one line (the marker) is inserted'
      );
    } finally {
      tab.restore();
      noEditor.restore();
      await fixture.cleanup();
    }
  });
});

describe('insertReviewComment — target resolution failure (Issue #50, LLD §2.3 0.7)', () => {
  it('stops with guidance and logs the reason once when no markdown preview is focused (never guesses)', async () => {
    // The shared host's active tab is never a markdown preview, so the 0.7 chain
    // stops with NO_PREVIEW_MSG before consulting the tracker at all — no
    // MRU-stack or visible-editor fallback exists to guess for us.
    const tracker: EditorTracker = { recent: () => [], last: () => undefined };
    const logCalls: string[] = [];

    const warning = stubWarningMessage();
    try {
      await insertReviewComment(tracker, (m) => logCalls.push(m));

      assert.deepStrictEqual(
        warning.calls,
        [NO_PREVIEW_MSG],
        `expected the no-preview warning, got: ${JSON.stringify(warning.calls)}`
      );
      assert.deepStrictEqual(
        logCalls,
        [NO_PREVIEW_MSG],
        'every resolution failure produces exactly one log entry naming the reason (LLD §2.3 Invariant 13)'
      );
    } finally {
      warning.restore();
    }
  });
});
