/**
 * Issue #50 (v1-e1-2): evaluation specs for LLD §2.3 contract properties the
 * test-author's command.test.ts / resolution.test.ts do not assert.
 *
 * Four gaps are closed here, each a property the LLD states explicitly:
 *
 * 1. Runtime half of the palette AC — "EDF: Insert Review Comment appears in the
 *    command palette". evaluator-gap.test.ts pins the manifest half (title +
 *    category); scaffold.test.ts pins the "no undeclared command" direction.
 *    Neither asserts that activate() actually registers the declared command —
 *    the runtime half that makes the palette entry invocable.
 * 2. Invariant 18 — "The extension reads no file other than the resolved open
 *    document". The LLD's own verification is a grep for `workspace.fs`,
 *    `readFile`, `fetch`, `child_process` over the source tree. No spec asserts
 *    this, so a regression that adds e.g. a `workspace.fs` read into the command
 *    path would ship silently.
 * 3. LLD §2.3 error-handling table row: "Tracked editor's document has since
 *    closed → falls through to the visible-editor step". resolution.test.ts
 *    covers tracked-open and no-tracked, but not the tracked-but-closed branch.
 * 4. Same table, the failure half of that branch: a closed tracked editor with no
 *    visible markdown editor resolves to `none` with a reason that names the
 *    closed tracker — and the `editor.edit` returning `false` row: "Log the
 *    failure; show a message. Do not retry".
 *
 * The stubs (showQuickPick/showErrorMessage/showTextDocument and the fake
 * tracker/editor) match the dependency-injection pattern command.test.ts uses.
 */
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import * as assert from 'assert';
import { insertReviewComment } from '../../src/extension';
import { EditorTracker, resolveTarget } from '../../src/editor-tracker';

const EXTENSION_ID = 'mironyx.edf-review';
const COMMAND_ID = 'edf-review.insertReviewComment';

// ---------------------------------------------------------------------------
// Test-host helpers
// ---------------------------------------------------------------------------

async function settle(ms = 150): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

/** Minimal QuickPickItem-shaped item carrying the 0-based line. */
type HeadingPickItem = vscode.QuickPickItem & { line: number };

function stubQuickPick<T extends vscode.QuickPickItem>(
  pick: (items: T[]) => T | undefined
): { restore: () => void } {
  const original = vscode.window.showQuickPick;
  const testWindow = vscode.window as unknown as {
    showQuickPick: typeof vscode.window.showQuickPick;
  };
  testWindow.showQuickPick = ((
    items: readonly T[],
    _options?: vscode.QuickPickOptions,
    _token?: vscode.CancellationToken
  ) => Promise.resolve(pick(items.slice()))) as unknown as typeof vscode.window.showQuickPick;
  return {
    restore: () => {
      testWindow.showQuickPick = original;
    }
  };
}

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

function stubShowTextDocument(): { calls: () => number; restore: () => void } {
  const original = vscode.window.showTextDocument;
  const testWindow = vscode.window as unknown as {
    showTextDocument: typeof vscode.window.showTextDocument;
  };
  const state = { value: 0 };
  testWindow.showTextDocument = (() => {
    state.value += 1;
    return Promise.resolve(undefined);
  }) as unknown as typeof vscode.window.showTextDocument;
  return {
    calls: () => state.value,
    restore: () => {
      testWindow.showTextDocument = original;
    }
  };
}

/** A fake closed TextEditor — resolveTarget only reads document.isClosed on it. */
function closedEditor(): vscode.TextEditor {
  return { document: { isClosed: true } } as unknown as vscode.TextEditor;
}

// ---------------------------------------------------------------------------
// Specs
// ---------------------------------------------------------------------------

beforeEach(async () => {
  vscode.window.visibleTextEditors.forEach((editor) => editor.hide());
  await settle();
});

describe('activate (Issue #50, LLD §2.3 palette AC)', () => {
  it('registers edf-review.insertReviewComment so the palette entry is invocable', async () => {
    const extension = vscode.extensions.getExtension(EXTENSION_ID);
    assert.ok(extension, `extension ${EXTENSION_ID} must be loaded in the test host`);
    if (!extension.isActive) {
      await extension.activate();
    }

    const registered = await vscode.commands.getCommands();
    assert.ok(
      registered.includes(COMMAND_ID),
      `activate() must register ${COMMAND_ID}; getCommands() returned ${registered.filter(
        (id) => id.startsWith('edf-review.')
      ).join(', ') || '(no edf-review.* commands)'}`
    );
  });
});

describe('extension — no reads beyond the open document (LLD §2.3 Invariant 18)', () => {
  it('source tree contains no workspace.fs/readFile/fetch/child_process', () => {
    // Mirrors the LLD's verification: grep the source tree for the four
    // read/network/process tokens; assert none. Read the source .ts files the
    // same way pure-modules.eval.test.ts does (not the compiled .js).
    const srcDir = path.join(__dirname, '../../../src');
    const srcFiles = fs
      .readdirSync(srcDir)
      .filter((file) => file.endsWith('.ts'))
      .sort();

    assert.ok(srcFiles.length > 0, `expected source files under ${srcDir}`);

    const forbidden = [
      /workspace\.fs/,
      /readFile/,
      /fetch/,
      /child_process/
    ] as const;

    for (const file of srcFiles) {
      const src = fs.readFileSync(path.join(srcDir, file), 'utf8');
      for (const pattern of forbidden) {
        assert.ok(
          !pattern.test(src),
          `${file} must not contain ${pattern} — the extension reads no file ` +
            'beyond the resolved open document (LLD §2.3 Invariant 18)'
        );
      }
    }
  });
});

describe('resolveTarget — tracked editor closed (Issue #50, LLD §2.3 error table)', () => {
  it('falls through to the single visible markdown editor when the tracked editor is closed', async () => {
    // LLD error-handling row: "Tracked editor's document has since closed →
    // falls through to the visible-editor step". The tracked editor is fake and
    // closed; the one real visible markdown editor must resolve.
    const doc = await vscode.workspace.openTextDocument({
      content: '# Title\n## Section One\n',
      language: 'markdown'
    });
    const editor = await vscode.window.showTextDocument(doc);

    const tracker: EditorTracker = { last: () => closedEditor() };
    const resolution = resolveTarget(tracker);

    assert.strictEqual(resolution.kind, 'visible');
    if (resolution.kind === 'visible') {
      assert.strictEqual(resolution.editor, editor);
    }
  });

  it("returns { kind: 'none' } naming the closed tracker when no visible editor resolves", () => {
    // beforeEach hid every visible editor; the tracked editor is closed, so the
    // failure reason must name the closed tracker rather than claim no editor
    // was ever focused (LLD §2.3: reason names which step failed).
    const tracker: EditorTracker = { last: () => closedEditor() };
    const resolution = resolveTarget(tracker);

    assert.strictEqual(resolution.kind, 'none');
    if (resolution.kind === 'none') {
      assert.ok(
        /closed/.test(resolution.reason),
        `reason must name the closed tracked editor, got: ${resolution.reason}`
      );
    }
  });
});

describe('insertReviewComment — editor.edit returns false (Issue #50, LLD §2.3 error table)', () => {
  it('logs the failure, shows an error message and does not move the cursor or refocus', async () => {
    // LLD error-handling row: "editor.edit returns false → Log the failure; show
    // a message. Do not retry". A fake editor whose edit() returns false is
    // injected through the tracker; the command must fail explicitly rather than
    // silently treating the failed edit as a success.
    const fakeEditor = {
      document: {
        getText: () => ['# Title', '', '## Section One', ''].join('\n')
      },
      edit: async () => false,
      selection: {
        anchor: { line: 0, character: 0 },
        active: { line: 0, character: 0 }
      },
      viewColumn: 1
    } as unknown as vscode.TextEditor;

    const tracker: EditorTracker = { last: () => fakeEditor };
    const logCalls: string[] = [];

    const quickPick = stubQuickPick<HeadingPickItem>((items) => items[0]);
    const errorStub = stubErrorMessage();
    const textDocStub = stubShowTextDocument();
    try {
      await insertReviewComment(tracker, (m) => logCalls.push(m));

      assert.deepStrictEqual(
        logCalls,
        ['failed to insert review marker'],
        'a failed edit must be logged exactly once'
      );
      assert.deepStrictEqual(
        errorStub.calls,
        ['Failed to insert review marker'],
        `expected one error message, got ${JSON.stringify(errorStub.calls)}`
      );
      assert.strictEqual(
        (fakeEditor.selection as { active: { line: number } }).active.line,
        0,
        'the cursor must not move when the edit fails'
      );
      assert.strictEqual(
        textDocStub.calls(),
        0,
        'the editor must not be refocused when the edit fails'
      );
    } finally {
      quickPick.restore();
      errorStub.restore();
      textDocStub.restore();
    }
  });
});
