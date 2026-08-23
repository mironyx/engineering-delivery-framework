/**
 * Issue #50 (v1-e1-2): Insert Review Comment command wiring.
 *
 * Integration specs for src/extension.ts — insertReviewComment and
 * NO_HEADINGS_MSG — and the heading extraction it drives (src/headings.ts).
 * LLD §2.3 (Command wiring and target resolution, 0.7 never-guess) Invariants
 * 14-17 and the issue's quick-pick/insertion BDD blocks.
 *
 * The handler is called directly with an injected fake EditorTracker and a
 * capturing log (dependency injection) so every branch is deterministic in the
 * shared host. 0.7 makes the focused markdown preview the ONLY resolution
 * trigger, so tests that must reach the quick-pick stub the active tab to be a
 * markdown preview titled `Preview <basename>` whose basename matches the
 * injected editor's file, and the quick-pick is driven by monkey-patching
 * vscode.window.showQuickPick — the standard VS Code extension-testing pattern
 * for UI surfaces with no read-back API. No HTTP is involved, so the repo's
 * respx/MSW rule does not apply.
 */
import * as vscode from 'vscode';
import * as assert from 'assert';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { insertReviewComment, NO_HEADINGS_MSG } from '../../src/extension';
import { EditorTracker, NO_PREVIEW_MSG } from '../../src/editor-tracker';
import { extractHeadings } from '../../src/headings';
import { REVIEW_MARKER } from '../../src/review-insert';

/** A quick-pick item as toItems builds it: the display item plus the 0-based line. */
type HeadingPickItem = vscode.QuickPickItem & { line: number };

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
 * NO_PREVIEW_MSG before any quick-pick, so every insertion spec pins it.
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

/** Monkey-patch vscode.window.showQuickPick and capture the items offered. */
function stubQuickPick<T extends vscode.QuickPickItem>(
  pick: (items: T[]) => T | undefined
): { items: () => T[]; restore: () => void } {
  const original = vscode.window.showQuickPick;
  const testWindow = vscode.window as unknown as {
    showQuickPick: typeof vscode.window.showQuickPick;
  };
  const captured: { value: T[] } = { value: [] };
  testWindow.showQuickPick = ((
    items: readonly T[],
    _options?: vscode.QuickPickOptions,
    _token?: vscode.CancellationToken
  ) => {
    captured.value = items.slice();
    return Promise.resolve(pick(items.slice()));
  }) as unknown as typeof vscode.window.showQuickPick;
  return {
    items: () => captured.value,
    restore: () => {
      testWindow.showQuickPick = original;
    }
  };
}

/** Monkey-patch vscode.window.showInformationMessage and capture the messages. */
function stubInformationMessage(): { messages: () => string[]; restore: () => void } {
  const original = vscode.window.showInformationMessage;
  const testWindow = vscode.window as unknown as {
    showInformationMessage: typeof vscode.window.showInformationMessage;
  };
  const captured: { value: string[] } = { value: [] };
  testWindow.showInformationMessage = ((
    message: string,
    ..._rest: unknown[]
  ) => {
    captured.value.push(message);
    return Promise.resolve(undefined);
  }) as unknown as typeof vscode.window.showInformationMessage;
  return {
    messages: () => captured.value,
    restore: () => {
      testWindow.showInformationMessage = original;
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

/**
 * Monkey-patch vscode.window.showTextDocument and count calls. `result` is what
 * resolution's reveal returns — the stale-heading spec's fake editor is not on
 * disk, so the real showTextDocument would try to open a nonexistent file.
 */
function stubShowTextDocument(result: unknown): { calls: () => number; restore: () => void } {
  const original = vscode.window.showTextDocument;
  const testWindow = vscode.window as unknown as {
    showTextDocument: typeof vscode.window.showTextDocument;
  };
  const state = { value: 0 };
  testWindow.showTextDocument = (() => {
    state.value += 1;
    return Promise.resolve(result);
  }) as unknown as typeof vscode.window.showTextDocument;
  return {
    calls: () => state.value,
    restore: () => {
      testWindow.showTextDocument = original;
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

describe('insertReviewComment — quick-pick (Issue #50, LLD §2.3)', () => {
  it('lists ## and ### headings with 1-based line numbers', async () => {
    const fixture = await fileMarkdownFixture(MARKDOWN_WITH_HEADINGS);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };
    const logCalls: string[] = [];

    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    const quickPick = stubQuickPick<HeadingPickItem>(() => undefined);
    try {
      await insertReviewComment(tracker, (m) => logCalls.push(m));

      const items = quickPick.items();
      assert.strictEqual(items.length, 2, 'only ## and ### headings are offered');

      // LLD §2.3: labels carry the level prefix; description is the 1-based
      // line number (heading.line + 1) that the editor gutter shows.
      assert.strictEqual(items[0].label, '## Section One', 'label carries the ## level prefix');
      assert.strictEqual(items[0].description, 'line 3', 'line number is 1-based');
      assert.strictEqual(items[1].label, '### Sub Section', 'label carries the ### level prefix');
      assert.strictEqual(items[1].description, 'line 5', 'line number is 1-based');

      // Cross-check against the pure extractor: every heading it finds is offered.
      assert.strictEqual(
        items.length,
        extractHeadings(fixture.editor.document.getText()).length
      );
      assert.strictEqual(logCalls.length, 0, 'listing headings is not a failure');
    } finally {
      tab.restore();
      quickPick.restore();
      await fixture.cleanup();
    }
  });

  it('shows the no-headings message and makes no edit for a document without headings', async () => {
    const content = 'Just prose with no headings.\n- a list item\n';
    const fixture = await fileMarkdownFixture(content);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };
    const logCalls: string[] = [];

    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    const info = stubInformationMessage();
    const quickPick = stubQuickPick<HeadingPickItem>(() => {
      assert.fail('showQuickPick must not be called when there are no headings');
      return undefined;
    });
    try {
      const beforeText = fixture.doc.getText();
      const beforeVersion = fixture.doc.version;

      await insertReviewComment(tracker, (m) => logCalls.push(m));

      assert.ok(
        info.messages().includes(NO_HEADINGS_MSG),
        `expected the no-headings message, got: ${JSON.stringify(info.messages())}`
      );
      assert.strictEqual(fixture.doc.getText(), beforeText, 'document must be byte-identical');
      assert.strictEqual(fixture.doc.version, beforeVersion, 'document must not be edited');
      assert.strictEqual(logCalls.length, 0, 'a no-headings document is not a resolution failure');
    } finally {
      tab.restore();
      info.restore();
      quickPick.restore();
      await fixture.cleanup();
    }
  });

  it('leaves the document byte-identical and unedited when the quick-pick is dismissed', async () => {
    const fixture = await fileMarkdownFixture(MARKDOWN_WITH_HEADINGS);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };
    const logCalls: string[] = [];

    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    const info = stubInformationMessage();
    const quickPick = stubQuickPick<HeadingPickItem>(() => undefined); // Escape
    try {
      const beforeText = fixture.doc.getText();
      const beforeVersion = fixture.doc.version;

      await insertReviewComment(tracker, (m) => logCalls.push(m));

      // LLD §2.3 Invariant 14: Escape leaves the document byte-identical — the
      // command must return before applying any edit, never edit-then-undo.
      assert.strictEqual(fixture.doc.getText(), beforeText, 'Escape must leave the document byte-identical');
      assert.strictEqual(fixture.doc.version, beforeVersion, 'Escape must not apply an edit');
      assert.strictEqual(logCalls.length, 0, 'Escape must not log (silent no-op)');
      assert.strictEqual(info.messages().length, 0, 'Escape must not show a message');
    } finally {
      tab.restore();
      info.restore();
      quickPick.restore();
      await fixture.cleanup();
    }
  });
});

describe('insertReviewComment — insertion (Issue #50, LLD §2.3)', () => {
  it('inserts the marker on a new line after the selected heading', async () => {
    const content = ['# Title', '', '## Section One', 'Some prose here.', ''].join('\n');
    const fixture = await fileMarkdownFixture(content);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };
    const logCalls: string[] = [];

    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    const quickPick = stubQuickPick<HeadingPickItem>((items) =>
      items.find((item) => item.label.includes('Section One'))
    );
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
      assert.strictEqual(fixture.doc.getText(), expected, 'marker goes on the line after the heading');
      assert.strictEqual(logCalls.length, 0, 'a successful insertion is not a failure');
    } finally {
      tab.restore();
      quickPick.restore();
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

    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    const quickPick = stubQuickPick<HeadingPickItem>((items) =>
      items.find((item) => item.label.includes('Section One'))
    );
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
      quickPick.restore();
      await fixture.cleanup();
    }
  });

  it('applies the insertion as a single edit (document.version increases by exactly 1)', async () => {
    const fixture = await fileMarkdownFixture(MARKDOWN_WITH_HEADINGS);
    const tracker: EditorTracker = {
      recent: () => [fixture.editor],
      last: () => fixture.editor
    };

    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    const quickPick = stubQuickPick<HeadingPickItem>((items) =>
      items.find((item) => item.label.includes('Section One'))
    );
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
      quickPick.restore();
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

    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    const quickPick = stubQuickPick<HeadingPickItem>((items) =>
      items.find((item) => item.label.includes('Section One'))
    );
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
      quickPick.restore();
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

    const tab = stubActiveTab(previewTab(`Preview ${fixture.base}`));
    const quickPick = stubQuickPick<HeadingPickItem>((items) =>
      items.find((item) => item.label.includes('Section One'))
    );
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
      quickPick.restore();
      await fixture.cleanup();
    }
  });

  it('fails explicitly instead of throwing when the heading is deleted while the quick-pick is open (review finding #73)', async () => {
    // Stale-index guard: extractHeadings captures a line, the document shrinks
    // before applyMarker re-reads it, and findReviewInsertLine returns the stale
    // index unchanged. The command must log + show a message, never throw.
    let reads = 0;
    const fakeEditor = {
      document: {
        // mruMatchesForName reads the basename to match the stubbed preview title.
        uri: vscode.Uri.file(path.join('C:/__edf_fixture__', 'fake-heading.md')),
        isClosed: false,
        getText: () => {
          reads += 1;
          // First read (extractHeadings) still has the heading; the re-read in
          // applyMarker sees the document after the heading was deleted.
          return reads === 1
            ? ['# Title', '', '## Section One', ''].join('\n')
            : ['# Title'].join('\n');
        },
        eol: vscode.EndOfLine.LF
      },
      edit: async () => {
        assert.fail('editor.edit must not be called when the heading is gone');
        return true;
      },
      selection: {
        anchor: { line: 0, character: 0 },
        active: { line: 0, character: 0 }
      },
      viewColumn: 1
    } as unknown as vscode.TextEditor;

    const tracker: EditorTracker = { recent: () => [fakeEditor], last: () => fakeEditor };
    const logCalls: string[] = [];
    const tab = stubActiveTab(previewTab('Preview fake-heading.md'));
    const quickPick = stubQuickPick<HeadingPickItem>((items) => items[0]);
    const errorStub = stubErrorMessage();
    const textDocStub = stubShowTextDocument(fakeEditor);
    try {
      await insertReviewComment(tracker, (m) => logCalls.push(m));

      assert.deepStrictEqual(
        logCalls,
        ['selected heading no longer exists in the document'],
        'the stale heading must be logged exactly once'
      );
      assert.deepStrictEqual(
        errorStub.calls,
        ['Selected heading no longer exists'],
        `expected one error message, got ${JSON.stringify(errorStub.calls)}`
      );
    } finally {
      tab.restore();
      quickPick.restore();
      errorStub.restore();
      textDocStub.restore();
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
    const quickPick = stubQuickPick<HeadingPickItem>(() => {
      assert.fail('showQuickPick must not be called when no document resolves');
      return undefined;
    });
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
      quickPick.restore();
    }
  });
});
