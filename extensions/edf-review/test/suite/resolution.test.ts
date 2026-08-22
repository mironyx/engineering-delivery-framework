/**
 * Issue #50 (v1-e1-2): editor tracker, target resolution and output channel.
 *
 * Integration specs for src/editor-tracker.ts (createEditorTracker, resolveTarget)
 * and src/log.ts (createLog) — LLD §2.3 (Command wiring and target resolution),
 * Invariants 12-13 and the issue's target-resolution BDD block.
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
import {
  createEditorTracker,
  resolveTarget,
  EditorTracker
} from '../../src/editor-tracker';
import { createLog } from '../../src/log';

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
  it('tracks the most recently focused markdown editor', async () => {
    const context = freshContext();
    const tracker = createEditorTracker(context);

    // LLD §2.3 Part B: the disposable is pushed onto context.subscriptions so
    // the listener is torn down when the extension deactivates.
    assert.ok(
      context.subscriptions.length >= 1,
      'createEditorTracker must push the event disposable onto context.subscriptions'
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
    await vscode.window.showTextDocument(plainDoc);

    // Give the plaintext focus event a moment to fire; the tracker must ignore it.
    await settle();
    assert.strictEqual(
      tracker.last(),
      mdEditor,
      'focusing a plaintext editor must not overwrite the tracked markdown editor'
    );
  });
});

describe('resolveTarget (Issue #50, LLD §2.3)', () => {
  it("returns { kind: 'tracked' } when the tracker has an open markdown editor", async () => {
    const doc = await vscode.workspace.openTextDocument({
      content: '# Title\n## Section One\n',
      language: 'markdown'
    });
    const editor = await vscode.window.showTextDocument(doc);

    const tracker: EditorTracker = { last: () => editor };
    const resolution = resolveTarget(tracker);

    assert.strictEqual(resolution.kind, 'tracked');
    if (resolution.kind === 'tracked') {
      assert.strictEqual(resolution.editor, editor);
    }
  });

  it("falls back to { kind: 'visible' } when last() is undefined and exactly one markdown editor is visible", async () => {
    const doc = await vscode.workspace.openTextDocument({
      content: '# Title\n## Section One\n',
      language: 'markdown'
    });
    const editor = await vscode.window.showTextDocument(doc);

    // last() is undefined (e.g. the preview holds focus before any markdown
    // editor was ever focused); the single visible markdown editor must resolve.
    const tracker: EditorTracker = { last: () => undefined };
    const resolution = resolveTarget(tracker);

    assert.strictEqual(resolution.kind, 'visible');
    if (resolution.kind === 'visible') {
      assert.strictEqual(resolution.editor, editor);
    }
  });

  it("returns { kind: 'none' } with a non-empty reason when neither resolves", () => {
    // beforeEach hid every visible editor; with no tracked reference and no
    // visible markdown editor, resolution must fail explicitly — never throw
    // (LLD §2.3 Invariant 12).
    const tracker: EditorTracker = { last: () => undefined };
    const resolution = resolveTarget(tracker);

    assert.strictEqual(resolution.kind, 'none');
    if (resolution.kind === 'none') {
      assert.ok(
        resolution.reason.length > 0,
        'reason must name which resolution step failed'
      );
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
