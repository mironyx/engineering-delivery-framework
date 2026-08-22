/**
 * Issue #50 (v1-e1-2): Insert Review Comment command wiring.
 *
 * Integration specs for src/extension.ts — insertReviewComment, NO_DOCUMENT_MSG,
 * NO_HEADINGS_MSG — and the heading extraction it drives (src/headings.ts).
 * LLD §2.3 (Command wiring and target resolution) Invariants 14-17 and the
 * issue's quick-pick/insertion BDD blocks.
 *
 * The handler is called directly with an injected fake EditorTracker and a
 * capturing log (dependency injection) so every branch is deterministic in the
 * shared host: resolveTarget is driven by the fake tracker's last(), and the
 * quick-pick is driven by monkey-patching vscode.window.showQuickPick — the
 * standard VS Code extension-testing pattern for UI surfaces with no read-back
 * API. No HTTP is involved, so the repo's respx/MSW rule does not apply.
 */
import * as vscode from 'vscode';
import * as assert from 'assert';
import {
  insertReviewComment,
  NO_DOCUMENT_MSG,
  NO_HEADINGS_MSG
} from '../../src/extension';
import { EditorTracker } from '../../src/editor-tracker';
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

async function openMarkdownEditor(content: string): Promise<{
  doc: vscode.TextDocument;
  editor: vscode.TextEditor;
}> {
  const doc = await vscode.workspace.openTextDocument({ content, language: 'markdown' });
  const editor = await vscode.window.showTextDocument(doc);
  return { doc, editor };
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
    const { editor } = await openMarkdownEditor(MARKDOWN_WITH_HEADINGS);
    const tracker: EditorTracker = { last: () => editor };
    const logCalls: string[] = [];

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
        extractHeadings(editor.document.getText()).length
      );
      assert.strictEqual(logCalls.length, 0, 'listing headings is not a failure');
    } finally {
      quickPick.restore();
    }
  });

  it('shows the no-headings message and makes no edit for a document without headings', async () => {
    const content = 'Just prose with no headings.\n- a list item\n';
    const { doc, editor } = await openMarkdownEditor(content);
    const tracker: EditorTracker = { last: () => editor };
    const logCalls: string[] = [];

    const info = stubInformationMessage();
    const quickPick = stubQuickPick<HeadingPickItem>(() => {
      assert.fail('showQuickPick must not be called when there are no headings');
      return undefined;
    });
    try {
      const beforeText = doc.getText();
      const beforeVersion = doc.version;

      await insertReviewComment(tracker, (m) => logCalls.push(m));

      assert.ok(
        info.messages().includes(NO_HEADINGS_MSG),
        `expected the no-headings message, got: ${JSON.stringify(info.messages())}`
      );
      assert.strictEqual(doc.getText(), beforeText, 'document must be byte-identical');
      assert.strictEqual(doc.version, beforeVersion, 'document must not be edited');
      assert.strictEqual(logCalls.length, 0, 'a no-headings document is not a resolution failure');
    } finally {
      info.restore();
      quickPick.restore();
    }
  });

  it('leaves the document byte-identical and unedited when the quick-pick is dismissed', async () => {
    const { doc, editor } = await openMarkdownEditor(MARKDOWN_WITH_HEADINGS);
    const tracker: EditorTracker = { last: () => editor };
    const logCalls: string[] = [];

    const info = stubInformationMessage();
    const quickPick = stubQuickPick<HeadingPickItem>(() => undefined); // Escape
    try {
      const beforeText = doc.getText();
      const beforeVersion = doc.version;

      await insertReviewComment(tracker, (m) => logCalls.push(m));

      // LLD §2.3 Invariant 14: Escape leaves the document byte-identical — the
      // command must return before applying any edit, never edit-then-undo.
      assert.strictEqual(doc.getText(), beforeText, 'Escape must leave the document byte-identical');
      assert.strictEqual(doc.version, beforeVersion, 'Escape must not apply an edit');
      assert.strictEqual(logCalls.length, 0, 'Escape must not log (silent no-op)');
      assert.strictEqual(info.messages().length, 0, 'Escape must not show a message');
    } finally {
      info.restore();
      quickPick.restore();
    }
  });
});

describe('insertReviewComment — insertion (Issue #50, LLD §2.3)', () => {
  it('inserts the marker on a new line after the selected heading', async () => {
    const content = ['# Title', '', '## Section One', 'Some prose here.', ''].join('\n');
    const { doc, editor } = await openMarkdownEditor(content);
    const tracker: EditorTracker = { last: () => editor };
    const logCalls: string[] = [];

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
      assert.strictEqual(doc.getText(), expected, 'marker goes on the line after the heading');
      assert.strictEqual(logCalls.length, 0, 'a successful insertion is not a failure');
    } finally {
      quickPick.restore();
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
    const { doc, editor } = await openMarkdownEditor(content);
    const tracker: EditorTracker = { last: () => editor };

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
        doc.getText(),
        expected,
        'new marker must follow existing markers in order'
      );
    } finally {
      quickPick.restore();
    }
  });

  it('applies the insertion as a single edit (document.version increases by exactly 1)', async () => {
    const { doc, editor } = await openMarkdownEditor(MARKDOWN_WITH_HEADINGS);
    const tracker: EditorTracker = { last: () => editor };

    const quickPick = stubQuickPick<HeadingPickItem>((items) =>
      items.find((item) => item.label.includes('Section One'))
    );
    try {
      const versionBefore = doc.version;

      await insertReviewComment(tracker, () => {});

      // LLD §2.3 Invariant 16 + constraint: exactly one editor.edit call. Two
      // edits would give correct text but a two-step undo stack.
      assert.strictEqual(
        doc.version,
        versionBefore + 1,
        'insertion must be exactly one editor.edit call'
      );
    } finally {
      quickPick.restore();
    }
  });

  it('focuses the editor with the cursor immediately after the marker text', async () => {
    const content = ['# Title', '', '## Section One', 'Some prose here.', ''].join('\n');
    const { editor } = await openMarkdownEditor(content);
    const tracker: EditorTracker = { last: () => editor };

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
        editor,
        'the resolved source editor must be focused after insertion'
      );
      assert.strictEqual(editor.selection.active.line, insertedLine, 'cursor is on the inserted line');
      assert.strictEqual(
        editor.selection.active.character,
        REVIEW_MARKER.length,
        'cursor sits immediately after the marker text'
      );
    } finally {
      quickPick.restore();
    }
  });
});

describe('insertReviewComment — target resolution failure (Issue #50, LLD §2.3)', () => {
  it('shows the no-source-document message and logs the reason once when neither resolves', async () => {
    // beforeEach hid every visible editor, and the fake tracker has no last()
    // reference — neither the tracked nor the visible fallback can resolve.
    const tracker: EditorTracker = { last: () => undefined };
    const logCalls: string[] = [];

    const info = stubInformationMessage();
    const quickPick = stubQuickPick<HeadingPickItem>(() => {
      assert.fail('showQuickPick must not be called when no document resolves');
      return undefined;
    });
    try {
      await insertReviewComment(tracker, (m) => logCalls.push(m));

      assert.ok(
        info.messages().includes(NO_DOCUMENT_MSG),
        `expected ${NO_DOCUMENT_MSG}, got: ${JSON.stringify(info.messages())}`
      );
      assert.strictEqual(
        logCalls.length,
        1,
        'every resolution failure produces exactly one log entry (LLD §2.3 Invariant 13)'
      );
      assert.ok(logCalls[0].length > 0, 'the logged reason must be non-empty');
    } finally {
      info.restore();
      quickPick.restore();
    }
  });
});
