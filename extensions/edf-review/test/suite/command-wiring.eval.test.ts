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
 * 3. LLD §2.3 0.7 error-handling row: a closed tracked editor is not a
 *    candidate — "never targets an editor that does not match the preview
 *    title". resolution.test.ts covers open-matches, zero-matches and
 *    ambiguous-matches, but not the closed-entry-shadows-open-entry branch.
 * 4. Same table, the failure half: when the only basename-matching tracked
 *    entry is closed, resolution stops with NO_DOCUMENT_MSG — it does not
 *    target a closed document. And the `editor.edit` returning `false` row:
 *    "Log the failure; show a message. Do not retry" — no cursor move, no
 *    refocus.
 *
 * The stubs (showErrorMessage/showTextDocument, the active-tab stub and the
 * fake tracker/editor) match the dependency-injection pattern command.test.ts
 * uses.
 */
import * as vscode from 'vscode';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as assert from 'assert';
import { insertReviewComment } from '../../src/extension';
import {
  EditorTracker,
  resolveTarget,
  NO_DOCUMENT_MSG
} from '../../src/editor-tracker';

const EXTENSION_ID = 'mironyx.edf-review';
const COMMAND_ID = 'edf-review.insertReviewComment';

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
 * Stub the window's active tab so insertReviewComment sees a focused preview.
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

/**
 * Monkey-patch vscode.window.showTextDocument and count calls. `result` is what
 * resolution's reveal returns — 0.7 always reveals via showTextDocument on the
 * resolved branch, so the stub must hand back a usable editor rather than
 * undefined.
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

/** A fake closed TextEditor — resolution only reads document.isClosed on it. */
function closedEditor(): vscode.TextEditor {
  return { document: { isClosed: true } } as unknown as vscode.TextEditor;
}

/** Create a throwaway dir for file-backed markdown documents. */
function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'edf-review-eval-'));
}

/** Write a markdown file (creating parent dirs) so it can be opened by URI. */
function writeMarkdownFile(filePath: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, '# Title\n## Section One\n', 'utf8');
}

/** A basename unique to this test run — a leaked doc can never make matching ambiguous. */
let uniqueCounter = 0;
function uniqueMarkdownBase(): string {
  uniqueCounter += 1;
  return `doc-${process.pid}-${uniqueCounter}.md`;
}

/** Close every opened doc (releasing the file handles VS Code holds) and remove the temp dir. */
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

describe('resolveTarget — closed tracked entry (Issue #50, LLD §2.3 0.7)', () => {
  it('resolves the still-open tracked editor when an older closed entry shares the basename', async () => {
    // A closed entry must never win: mruMatchesForName skips closed documents
    // before its URI is read, so an older closed entry sharing the preview
    // title's basename cannot shadow the real open editor (0.7, never guess).
    const dir = makeTempDir();
    const opened: vscode.TextDocument[] = [];
    try {
      const base = uniqueMarkdownBase();
      const filePath = path.join(dir, base);
      writeMarkdownFile(filePath);
      opened.push(await vscode.workspace.openTextDocument(vscode.Uri.file(filePath)));
      const editor = await vscode.window.showTextDocument(opened[0]);

      const tracker: EditorTracker = {
        recent: () => [closedEditor(), editor],
        last: () => closedEditor()
      };
      const resolution = await resolveTarget(tracker, previewTab(`Preview ${base}`));

      assert.strictEqual(resolution.kind, 'resolved');
      if (resolution.kind === 'resolved') {
        assert.strictEqual(
          resolution.editor.document.uri.fsPath.toLowerCase(),
          filePath.toLowerCase(),
          'the closed entry must not shadow the open editor that matches the preview title'
        );
      }
    } finally {
      await cleanupTempDir(dir, opened);
    }
  });

  it('tells the user to open the original markdown file when the only matching tracked entry is closed (never targets a closed document)', async () => {
    // LLD §2.3 0.7 error-table row (0.8 message): a closed/evicted tracked editor
    // is not a candidate — zero matches → NO_DOCUMENT_MSG telling the user to
    // open the original file, never a stale-target guess.
    const tracker: EditorTracker = {
      recent: () => [closedEditor()],
      last: () => closedEditor()
    };
    const resolution = await resolveTarget(tracker, previewTab('Preview foo.md'));

    assert.strictEqual(resolution.kind, 'none');
    if (resolution.kind === 'none') {
      assert.strictEqual(resolution.reason, NO_DOCUMENT_MSG);
    }
  });
});

describe('insertReviewComment — editor.edit returns false (Issue #50, LLD §2.3 error table)', () => {
  it('logs the failure, shows an error message and does not refocus when editor.edit returns false', async () => {
    // LLD error-handling row: "editor.edit returns false → Log the failure; show
    // a message. Do not retry". A fake editor whose edit() returns false is
    // injected through the tracker; the command must fail explicitly rather than
    // silently treating the failed edit as a success. The fake's document URI
    // matches the stubbed preview title so the 0.7 chain resolves to it first.
    const fakeEditor = {
      document: {
        uri: vscode.Uri.file(path.join('C:/__edf_fixture__', 'fake-eval-edit.md')),
        isClosed: false,
        getText: () => ['# Title', '', '## Section One', ''].join('\n')
      },
      edit: async () => false,
      selection: {
        anchor: { line: 0, character: 0 },
        active: { line: 0, character: 0 }
      },
      viewColumn: 1
    } as unknown as vscode.TextEditor;

    const tracker: EditorTracker = {
      recent: () => [fakeEditor],
      last: () => fakeEditor
    };
    const logCalls: string[] = [];

    const tab = stubActiveTab(previewTab('Preview fake-eval-edit.md'));
    const errorStub = stubErrorMessage();
    const textDocStub = stubShowTextDocument(fakeEditor);
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
        1,
        'the only showTextDocument call is resolution\'s reveal — applyMarker must not refocus on a failed edit'
      );
    } finally {
      tab.restore();
      errorStub.restore();
      textDocStub.restore();
    }
  });
});
