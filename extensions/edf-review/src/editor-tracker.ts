/**
 * Editor tracker and target resolution — extension host.
 *
 * LLD v1-e1-2 §2.3: identifies which document the reviewer meant when a
 * webview holds focus and `activeTextEditor` is `undefined`. The tracker
 * records the last focused markdown editor *continuously*, and `resolveTarget`
 * walks a three-way chain: tracked → single visible markdown editor → explicit,
 * logged failure.
 */
import * as vscode from 'vscode';

/** Tracks the most recently focused markdown editor. */
export interface EditorTracker {
  /** Most recently focused markdown editor, or undefined if none was ever focused. */
  last(): vscode.TextEditor | undefined;
}

/** Result of resolving the target document for a review comment. */
export type Resolution =
  | { kind: 'tracked'; editor: vscode.TextEditor }
  | { kind: 'visible'; editor: vscode.TextEditor }
  | { kind: 'none'; reason: string };

/**
 * Create an editor tracker. Subscribes to `onDidChangeActiveTextEditor` and
 * stores the editor when its document is markdown. The disposable is pushed
 * onto `context.subscriptions`.
 */
export function createEditorTracker(context: vscode.ExtensionContext): EditorTracker {
  let last: vscode.TextEditor | undefined;

  const disposable = vscode.window.onDidChangeActiveTextEditor((editor) => {
    if (editor && editor.document.languageId === 'markdown') {
      last = editor;
    }
  });
  context.subscriptions.push(disposable);

  return { last: () => last };
}

/**
 * Resolve the target editor for a review comment.
 *
 * 1. `tracker.last()` — if set AND its document is still open, return `tracked`.
 * 2. `window.visibleTextEditors` filtered to markdown — if exactly one, return `visible`.
 * 3. Return `none` with a reason naming which step failed.
 */
export function resolveTarget(tracker: EditorTracker): Resolution {
  const tracked = tracker.last();
  if (tracked && !tracked.document.isClosed) {
    return { kind: 'tracked', editor: tracked };
  }

  const visible = vscode.window.visibleTextEditors.filter(
    (editor) => editor.document.languageId === 'markdown'
  );
  if (visible.length === 1) {
    return { kind: 'visible', editor: visible[0] };
  }

  const reason = tracked
    ? 'tracked markdown editor is closed'
    : visible.length === 0
      ? 'no markdown editor is focused or visible'
      : `${visible.length} visible markdown editors; cannot disambiguate`;
  return { kind: 'none', reason };
}
