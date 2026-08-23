/**
 * Issue #50 (v1-e1-2): editor tracker, target resolution and output channel.
 *
 * Integration specs for src/editor-tracker.ts (createEditorTracker,
 * previewTitleName, mruMatchesForName, resolveTarget, NO_PREVIEW_MSG /
 * NO_DOCUMENT_MSG / AMBIGUOUS_MSG) and src/log.ts (createLog) — LLD §2.3
 * (Command wiring and target resolution, 0.7 never-guess), Invariants 12-13 and
 * the issue's target-resolution BDD block.
 *
 * These specs run inside the VS Code test host launched by @vscode/test-electron
 * (test/runTest.ts) and are discovered by the Mocha bootstrap's star-star glob
 * over '*.test.js' (test/suite/index.ts). They exercise the public surface only:
 * the tracker is driven by real showTextDocument focus events, and resolution is
 * driven by injecting a fake EditorTracker so every branch is deterministic.
 * createLog's spec monkey-patches vscode.window.createOutputChannel to capture
 * appendLine calls — the standard VS Code extension-testing pattern, since an
 * output channel has no public read-back API.
 */
import * as vscode from 'vscode';
import * as assert from 'assert';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import {
  createEditorTracker,
  previewTitleName,
  mruMatchesForName,
  resolveTarget,
  NO_PREVIEW_MSG,
  NO_DOCUMENT_MSG,
  AMBIGUOUS_MSG,
  EditorTracker
} from '../../src/editor-tracker';
import { createLog } from '../../src/log';
import { insertReviewComment } from '../../src/extension';

// ---------------------------------------------------------------------------
// Test-host helpers
// ---------------------------------------------------------------------------

/** Every subscriptions array handed to createEditorTracker/createLog this file. */
const fakeSubscriptionLists: vscode.Disposable[][] = [];

/** Minimal ExtensionContext stub — the modules under test only touch subscriptions. */
function freshContext(): vscode.ExtensionContext {
  const subscriptions: vscode.Disposable[] = [];
  fakeSubscriptionLists.push(subscriptions);
  return { subscriptions } as unknown as vscode.ExtensionContext;
}

/** Dispose every subscription registered via freshContext(). */
function disposeAll(subscriptions: readonly vscode.Disposable[]): void {
  for (const disposable of subscriptions) {
    disposable.dispose();
  }
}

/** Poll until a condition holds; fail the test on timeout. */
async function waitFor(
  predicate: () => boolean,
  what: string,
  timeoutMs = 3000
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  assert.fail(`timed out waiting for ${what}`);
}

/** Give event dispatch a moment to settle before asserting a negative. */
async function settle(ms = 150): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
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

/** A quick-pick item carrying the 0-based heading line. */
type HeadingPickItem = vscode.QuickPickItem & { line: number };

/**
 * Fail-guard for the EDF Review channel log spec: resolution-failure must stop
 * before the quick-pick, so a real showQuickPick would hang the shared host.
 */
function stubQuickPick(): { restore: () => void } {
  const original = vscode.window.showQuickPick;
  const testWindow = vscode.window as unknown as {
    showQuickPick: typeof vscode.window.showQuickPick;
  };
  testWindow.showQuickPick = ((_items: readonly HeadingPickItem[]) => {
    assert.fail('showQuickPick must not be called when resolution fails');
    return Promise.resolve(undefined);
  }) as unknown as typeof vscode.window.showQuickPick;
  return {
    restore: () => {
      testWindow.showQuickPick = original;
    }
  };
}

/** Open an untitled markdown document in a visible editor. */
async function openMarkdownEditor(content: string): Promise<{
  doc: vscode.TextDocument;
  editor: vscode.TextEditor;
}> {
  const doc = await vscode.workspace.openTextDocument({ content, language: 'markdown' });
  const editor = await vscode.window.showTextDocument(doc);
  return { doc, editor };
}

/** A fake closed TextEditor — resolution only reads document.isClosed on it. */
function closedEditor(): vscode.TextEditor {
  return { document: { isClosed: true } } as unknown as vscode.TextEditor;
}

/** A fake markdown TextDocument — the tracker only reads languageId and object identity. */
function markdownDoc(): vscode.TextDocument {
  return { languageId: 'markdown' } as unknown as vscode.TextDocument;
}

/** A fake TextEditor wrapping a markdown document. */
function markdownEditorFor(doc: vscode.TextDocument): vscode.TextEditor {
  return { document: doc } as unknown as vscode.TextEditor;
}

/**
 * Stub the tracker's two event sources so a spec can drive the dedupe/prune
 * branches deterministically. The test host never fires onDidChangeActiveTextEditor
 * with an already-known editor (showTextDocument mints a new TextEditor per call and
 * editor.show() fires with undefined) and never fires onDidCloseTextDocument (no close
 * command closes an API-opened document), so the tracker's own handler logic is
 * exercised by invoking the captured handlers directly — the same monkey-patch pattern
 * the createLog spec uses for createOutputChannel.
 */
function stubTrackerEvents(): {
  focus: (editor: vscode.TextEditor | undefined) => void;
  close: (doc: vscode.TextDocument) => void;
  restore: () => void;
} {
  const originalFocus = vscode.window.onDidChangeActiveTextEditor;
  const originalClose = vscode.workspace.onDidCloseTextDocument;
  const focusHandlers: ((editor: vscode.TextEditor | undefined) => void)[] = [];
  const closeHandlers: ((doc: vscode.TextDocument) => void)[] = [];
  const testWindow = vscode.window as unknown as {
    onDidChangeActiveTextEditor: typeof vscode.window.onDidChangeActiveTextEditor;
  };
  const testWorkspace = vscode.workspace as unknown as {
    onDidCloseTextDocument: typeof vscode.workspace.onDidCloseTextDocument;
  };
  testWindow.onDidChangeActiveTextEditor = ((
    handler: (editor: vscode.TextEditor | undefined) => void
  ) => {
    focusHandlers.push(handler);
    return { dispose() {} };
  }) as unknown as typeof vscode.window.onDidChangeActiveTextEditor;
  testWorkspace.onDidCloseTextDocument = ((handler: (doc: vscode.TextDocument) => void) => {
    closeHandlers.push(handler);
    return { dispose() {} };
  }) as unknown as typeof vscode.workspace.onDidCloseTextDocument;
  return {
    focus: (editor) => focusHandlers.forEach((handler) => handler(editor)),
    close: (doc) => closeHandlers.forEach((handler) => handler(doc)),
    restore: () => {
      testWindow.onDidChangeActiveTextEditor = originalFocus;
      testWorkspace.onDidCloseTextDocument = originalClose;
    }
  };
}

/**
 * Reveal every opened doc in an editor, then close all editors. The VS Code API
 * has no `workspace.closeTextDocument` — closing the owning editor is the only
 * way to close a document, which is what fires `onDidCloseTextDocument`.
 * `closeAllEditors` is used because per-editor close commands do not reliably
 * close API-opened documents in the test host.
 */
async function closeOpenedDocuments(opened: readonly vscode.TextDocument[]): Promise<void> {
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
}

/** A basename unique to this test run — a leaked doc can never make matching ambiguous. */
let uniqueCounter = 0;
function uniqueMarkdownBase(): string {
  uniqueCounter += 1;
  return `doc-${process.pid}-${uniqueCounter}.md`;
}

/** A focused built-in markdown preview tab titled `label`. */
function previewTab(label: string): vscode.Tab {
  return { label, input: { viewType: 'markdown.preview' } } as unknown as vscode.Tab;
}

/** Create a throwaway dir for file-backed markdown documents. */
function makeTempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'edf-review-mru-'));
}

/** Write a markdown file (creating parent dirs) so it can be opened by URI. */
function writeMarkdownFile(filePath: string): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, '# Title\n## Section One\n', 'utf8');
}

/**
 * Close every opened doc (releasing the file handles VS Code holds) and remove
 * the temp dir. Closing first avoids Windows EPERM on rmSync of a dir whose
 * files are still open in the host.
 */
async function cleanupTempDir(
  dir: string,
  opened: readonly vscode.TextDocument[]
): Promise<void> {
  await closeOpenedDocuments(opened);
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {
    // The docs are closed, so a leftover temp dir cannot affect resolution
    // (workspace.textDocuments only lists open documents); os.tmpdir cleanup
    // handles the rest. Never fail a spec on best-effort cleanup.
  }
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
  while (fakeSubscriptionLists.length > 0) {
    disposeAll(fakeSubscriptionLists.pop()!);
  }
  vscode.window.visibleTextEditors.forEach((editor) => editor.hide());
});

describe('createEditorTracker (Issue #50, LLD §2.3)', () => {
  it('tracks the most recently focused markdown editor at the front of the MRU stack', async () => {
    const context = freshContext();
    const tracker = createEditorTracker(context);

    // LLD §2.3 Part B: the disposables are pushed onto context.subscriptions so
    // the listeners are torn down when the extension deactivates.
    assert.ok(
      context.subscriptions.length >= 1,
      'createEditorTracker must push the event disposables onto context.subscriptions'
    );

    const doc = await vscode.workspace.openTextDocument({
      content: '# Title\n## Section One\n',
      language: 'markdown'
    });
    const editor = await vscode.window.showTextDocument(doc);

    // showTextDocument triggers onDidChangeActiveTextEditor; the tracker must
    // record the editor that now holds focus.
    await waitFor(
      () => tracker.last() === editor,
      'tracker.last() to be the focused markdown editor'
    );

    assert.strictEqual(tracker.last(), editor);
    assert.deepStrictEqual(tracker.recent(), [editor]);
  });

  it('does not track non-markdown editors', async () => {
    const context = freshContext();
    const tracker = createEditorTracker(context);
    assert.strictEqual(tracker.last(), undefined, 'a fresh tracker has no recorded editor');

    // Seed the tracker with a markdown editor, then focus a plaintext one: the
    // plaintext focus must NOT overwrite the tracked markdown editor (LLD §2.3:
    // "stores the editor when editor?.document.languageId === 'markdown'").
    const mdDoc = await vscode.workspace.openTextDocument({
      content: '# Title\n## Section One\n',
      language: 'markdown'
    });
    const mdEditor = await vscode.window.showTextDocument(mdDoc);
    await waitFor(
      () => tracker.last() === mdEditor,
      'tracker.last() to record the markdown editor'
    );

    const plainDoc = await vscode.workspace.openTextDocument({
      content: 'plain text only',
      language: 'plaintext'
    });
    const plainEditor = await vscode.window.showTextDocument(plainDoc);

    // Give the plaintext focus event a moment to fire; the tracker must ignore it.
    await settle();
    assert.strictEqual(
      tracker.last(),
      mdEditor,
      'focusing a plaintext editor must not overwrite the tracked markdown editor'
    );
    assert.ok(
      !tracker.recent().includes(plainEditor),
      'a plaintext editor must not enter the MRU stack'
    );
  });

  it('dedupes on refocus, moving the editor to the front', async () => {
    const events = stubTrackerEvents();
    const context = freshContext();
    const tracker = createEditorTracker(context);
    try {
      const editorA = markdownEditorFor(markdownDoc());
      const editorB = markdownEditorFor(markdownDoc());

      events.focus(editorA);
      events.focus(editorB);
      assert.strictEqual(tracker.last(), editorB, 'newest focus sits at the front');

      // Re-focus A (as a tab switch does in real VS Code) — it must move to the
      // front of the stack without duplicating (LLD §2.3: dedupe on focus).
      events.focus(editorA);
      assert.strictEqual(
        tracker.recent().length,
        2,
        're-focusing an editor already in the stack must not duplicate it'
      );
      assert.strictEqual(tracker.last(), editorA, 're-focused editor moves to the front');
      assert.deepStrictEqual(tracker.recent(), [editorA, editorB]);
    } finally {
      events.restore();
    }
  });

  it('evicts a closed-document entry from the MRU stack', async () => {
    const events = stubTrackerEvents();
    const context = freshContext();
    const tracker = createEditorTracker(context);
    try {
      const docA = markdownDoc();
      const docB = markdownDoc();
      const editorA = markdownEditorFor(docA);
      const editorB = markdownEditorFor(docB);

      events.focus(editorA);
      events.focus(editorB);
      assert.strictEqual(tracker.recent().length, 2, 'both focused editors are tracked');

      // docA's editor closes → onDidCloseTextDocument fires; the tracker must
      // prune the entry, leaving the next-most-recent open editor (LLD §2.3:
      // "Subscribe to onDidCloseTextDocument to prune closed-document entries").
      events.close(docA);
      assert.strictEqual(
        tracker.recent().length,
        1,
        'the closed-document entry is pruned from the MRU stack'
      );
      assert.strictEqual(tracker.last(), editorB, 'the next-most-recent entry survives');
    } finally {
      events.restore();
    }
  });
});

describe('resolveTarget — issue #50 BDD (LLD §2.3 0.7, never guess)', () => {
  it('resolves to the document named by the focused preview tab title when it uniquely matches a tracked editor', async () => {
    const dir = makeTempDir();
    const opened: vscode.TextDocument[] = [];
    try {
      // The source behind the preview lives under a subdir — a medium/long tab
      // labelFormat renders "Preview sub/dir/<base>", so the match is on the
      // basename, not the full stripped label.
      const base = uniqueMarkdownBase();
      const targetPath = path.join(dir, 'sub', 'dir', base);
      writeMarkdownFile(targetPath);
      opened.push(await vscode.workspace.openTextDocument(vscode.Uri.file(targetPath)));
      const editor = await vscode.window.showTextDocument(opened[0]);

      const tracker: EditorTracker = { recent: () => [editor], last: () => editor };
      const resolution = await resolveTarget(tracker, previewTab(`Preview sub/dir/${base}`));

      assert.strictEqual(resolution.kind, 'resolved');
      if (resolution.kind === 'resolved') {
        assert.strictEqual(
          resolution.editor.document.uri.fsPath.toLowerCase(),
          targetPath.toLowerCase(),
          'the command must re-target to the document the preview title names'
        );
      }
    } finally {
      await cleanupTempDir(dir, opened);
    }
  });

  it('stops with guidance when the focused tab is not a markdown preview', async () => {
    // No preview focused → stop with NO_PREVIEW_MSG. Resolution never guesses,
    // so an empty tracker must NOT fall back to anything else (LLD §2.3 0.7).
    const tracker: EditorTracker = { recent: () => [], last: () => undefined };

    const noTab = await resolveTarget(tracker, undefined);
    assert.strictEqual(noTab.kind, 'none');
    if (noTab.kind === 'none') {
      assert.strictEqual(noTab.reason, NO_PREVIEW_MSG);
    }

    const textTab = { label: 'foo.md', input: {} } as unknown as vscode.Tab;
    const notPreview = await resolveTarget(tracker, textTab);
    assert.strictEqual(notPreview.kind, 'none');
    if (notPreview.kind === 'none') {
      assert.strictEqual(notPreview.reason, NO_PREVIEW_MSG);
    }
  });

  it('warns to close the wrong document when two tracked editors share the basename, then stops', async () => {
    const dir = makeTempDir();
    const opened: vscode.TextDocument[] = [];
    const warning = stubWarningMessage();
    try {
      // Two tracked open documents share the basename the preview title names —
      // never guess on ambiguity (LLD §2.3 0.7 step 5).
      writeMarkdownFile(path.join(dir, 'one', 'foo.md'));
      writeMarkdownFile(path.join(dir, 'two', 'foo.md'));
      opened.push(
        await vscode.workspace.openTextDocument(vscode.Uri.file(path.join(dir, 'one', 'foo.md')))
      );
      opened.push(
        await vscode.workspace.openTextDocument(vscode.Uri.file(path.join(dir, 'two', 'foo.md')))
      );
      const editorA = await vscode.window.showTextDocument(opened[0]);
      const editorB = await vscode.window.showTextDocument(opened[1]);

      const tracker: EditorTracker = {
        recent: () => [editorA, editorB],
        last: () => editorA
      };
      const resolution = await resolveTarget(tracker, previewTab('Preview foo.md'));

      assert.strictEqual(resolution.kind, 'none', 'an ambiguous match must stop, never guess');
      if (resolution.kind === 'none') {
        assert.strictEqual(resolution.reason, AMBIGUOUS_MSG('foo.md'));
      }
      assert.ok(
        warning.calls.includes(AMBIGUOUS_MSG('foo.md')),
        `must warn the user to close the wrong document, got: ${JSON.stringify(warning.calls)}`
      );
    } finally {
      warning.restore();
      await cleanupTempDir(dir, opened);
    }
  });

  it('stops with the no-source-document message when no tracked editor matches', async () => {
    // Zero matches — the document was never tracked or was evicted from the
    // bounded stack → NO_DOCUMENT_MSG, never guess (LLD §2.3 0.7 step 4).
    const empty: EditorTracker = { recent: () => [], last: () => undefined };
    const emptyResolution = await resolveTarget(empty, previewTab('Preview foo.md'));
    assert.strictEqual(emptyResolution.kind, 'none');
    if (emptyResolution.kind === 'none') {
      assert.strictEqual(emptyResolution.reason, NO_DOCUMENT_MSG);
    }

    // A tracked open editor with a different basename is equally a zero match.
    const { editor } = await openMarkdownEditor('# Title\n## Section One\n');
    const other: EditorTracker = { recent: () => [editor], last: () => editor };
    const otherResolution = await resolveTarget(other, previewTab('Preview bar.md'));
    assert.strictEqual(otherResolution.kind, 'none');
    if (otherResolution.kind === 'none') {
      assert.strictEqual(otherResolution.reason, NO_DOCUMENT_MSG);
    }
  });

  it('logs the reason to the EDF Review channel when resolution fails', async () => {
    // Resolution failure is surfaced by the command handler: the reason is both
    // logged to `EDF Review` and shown to the user. In the shared host the
    // active tab is never a markdown preview, so resolution stops with
    // NO_PREVIEW_MSG before any quick-pick (never guesses).
    const tracker: EditorTracker = { recent: () => [], last: () => undefined };
    const logCalls: string[] = [];
    const warning = stubWarningMessage();
    const quickPick = stubQuickPick();
    try {
      await insertReviewComment(tracker, (m) => logCalls.push(m));

      assert.deepStrictEqual(
        logCalls,
        [NO_PREVIEW_MSG],
        'the failing resolution reason must be logged to the EDF Review channel'
      );
      assert.deepStrictEqual(
        warning.calls,
        [NO_PREVIEW_MSG],
        'the user must see the same reason as a warning'
      );
    } finally {
      warning.restore();
      quickPick.restore();
    }
  });
});

describe('previewTitleName (Issue #50, LLD §2.3 0.7 helper)', () => {
  it('previewTitleName strips the "Preview " prefix and returns the basename for the markdown preview tab', () => {
    assert.strictEqual(previewTitleName(previewTab('Preview foo.md')), 'foo.md');
    assert.strictEqual(previewTitleName(previewTab('Preview sub/dir/foo.md')), 'foo.md');
  });

  it('previewTitleName returns undefined for a non-preview tab', () => {
    const textTab = { label: 'foo.md', input: {} } as unknown as vscode.Tab;
    assert.strictEqual(previewTitleName(textTab), undefined);
    assert.strictEqual(previewTitleName(undefined), undefined);
  });
});

describe('mruMatchesForName (Issue #50, LLD §2.3 0.7 helper)', () => {
  it('returns still-open tracked editors whose basename matches, in recency order', async () => {
    const dir = makeTempDir();
    const opened: vscode.TextDocument[] = [];
    try {
      const base = uniqueMarkdownBase();
      writeMarkdownFile(path.join(dir, 'one', base));
      writeMarkdownFile(path.join(dir, 'two', base));
      opened.push(
        await vscode.workspace.openTextDocument(vscode.Uri.file(path.join(dir, 'one', base)))
      );
      opened.push(
        await vscode.workspace.openTextDocument(vscode.Uri.file(path.join(dir, 'two', base)))
      );
      const editorA = await vscode.window.showTextDocument(opened[0]);
      const editorB = await vscode.window.showTextDocument(opened[1]);

      const tracker: EditorTracker = { recent: () => [editorB, editorA], last: () => editorB };
      const matches = mruMatchesForName(tracker, base);

      assert.deepStrictEqual(matches, [editorB, editorA], 'matches keep MRU recency order');
    } finally {
      await cleanupTempDir(dir, opened);
    }
  });

  it('excludes closed entries and non-matching basenames', async () => {
    const dir = makeTempDir();
    const opened: vscode.TextDocument[] = [];
    try {
      const base = uniqueMarkdownBase();
      writeMarkdownFile(path.join(dir, base));
      opened.push(await vscode.workspace.openTextDocument(vscode.Uri.file(path.join(dir, base))));
      const editorA = await vscode.window.showTextDocument(opened[0]);

      // A closed entry shares the basename but isClosed short-circuits before its
      // URI is read — the closed editor must never be offered as a match.
      const tracker: EditorTracker = {
        recent: () => [closedEditor(), editorA],
        last: () => closedEditor()
      };
      assert.deepStrictEqual(mruMatchesForName(tracker, base), [editorA]);
      assert.deepStrictEqual(mruMatchesForName(tracker, 'bar.md'), []);
    } finally {
      await cleanupTempDir(dir, opened);
    }
  });
});

describe('createLog (Issue #50, LLD §2.3)', () => {
  it('returns a function that appends to an output channel named "EDF Review"', () => {
    const stub = stubOutputChannel();
    try {
      const context = freshContext();
      const log = createLog(context);

      log('no source document resolved');

      const captured = stub.captured();
      assert.strictEqual(captured.name, 'EDF Review');
      assert.deepStrictEqual(captured.appendLineCalls, ['no source document resolved']);
      assert.ok(captured.channel, 'createLog must create an output channel');
      assert.ok(
        context.subscriptions.includes(captured.channel as vscode.Disposable),
        'the channel must be pushed onto context.subscriptions so it is disposed'
      );
    } finally {
      stub.restore();
    }
  });
});
