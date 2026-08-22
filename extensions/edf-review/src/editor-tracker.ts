/**
 * Editor tracker and target resolution — extension host.
 *
 * LLD v1-e1-2 §2.3 (0.6, title-first + MRU): identifies which document the
 * reviewer meant when a webview holds focus and `activeTextEditor` is
 * `undefined`. The tracker keeps a bounded MRU stack of markdown editors
 * (deduped on focus, cap 5, closed documents pruned), and `resolveTarget`
 * resolves title-first from the focused preview's tab title before walking that
 * stack, then the single-visible-editor check, then an explicit, logged failure.
 */
import * as vscode from 'vscode';
import * as path from 'path';

/** Tracks markdown editors most-recently-focused first. */
export interface EditorTracker {
  /** Markdown editors most-recently-focused first, deduped, bounded. */
  recent(): readonly vscode.TextEditor[];
  /** Most recently focused markdown editor, or undefined. */
  last(): vscode.TextEditor | undefined;
}

/** Result of resolving the target document for a review comment. */
export type Resolution =
  | { kind: 'tracked'; editor: vscode.TextEditor }
  | { kind: 'visible'; editor: vscode.TextEditor }
  | { kind: 'none'; reason: string };

/**
 * Create an editor tracker. Maintains a bounded MRU stack of markdown editors:
 * on focus the editor moves to the front (deduped), the tail beyond `cap` is
 * evicted, and entries whose document closes are pruned. Both disposables are
 * pushed onto `context.subscriptions`.
 */
export function createEditorTracker(
  context: vscode.ExtensionContext,
  cap = 5
): EditorTracker {
  const recent: vscode.TextEditor[] = [];

  const focusDisposable = vscode.window.onDidChangeActiveTextEditor((editor) => {
    if (!editor || editor.document.languageId !== 'markdown') {
      return;
    }
    const existing = recent.indexOf(editor);
    if (existing !== -1) {
      recent.splice(existing, 1);
    }
    recent.unshift(editor);
    if (recent.length > cap) {
      recent.length = cap;
    }
  });
  context.subscriptions.push(focusDisposable);

  const closeDisposable = vscode.workspace.onDidCloseTextDocument((doc) => {
    for (let i = recent.length - 1; i >= 0; i -= 1) {
      if (recent[i].document === doc) {
        recent.splice(i, 1);
      }
    }
  });
  context.subscriptions.push(closeDisposable);

  return {
    recent: () => recent.slice(),
    last: () => recent[0]
  };
}

/**
 * The basename of the focused preview tab's title, when the active tab is the
 * built-in markdown preview; undefined otherwise. Basename comparison tolerates
 * the user-configurable tab labelFormat (short/medium/long) rendering the title
 * as e.g. "Preview sub/dir/foo.md".
 */
export function previewTitleName(activeTab: vscode.Tab | undefined): string | undefined {
  const viewType = (activeTab?.input as { viewType?: unknown } | undefined)?.viewType;
  if (viewType !== 'markdown.preview') {
    return undefined;
  }
  const name = path.basename((activeTab?.label ?? '').replace(/^Preview /, ''));
  return name === '' ? undefined : name;
}

/**
 * The unique open markdown text document whose basename equals `name`, or
 * undefined when zero or multiple match — never guess on ambiguity.
 */
export function uniqueDocumentForName(name: string): vscode.TextDocument | undefined {
  const matches = vscode.workspace.textDocuments.filter(
    (doc) => doc.languageId === 'markdown' && path.basename(doc.uri.fsPath) === name
  );
  return matches.length === 1 ? matches[0] : undefined;
}

/**
 * Resolve the target editor for a review comment.
 *
 * Title-first (strongest — the previewed document is what the reviewer means):
 *   1. previewTitleName(activeTab) → uniqueDocumentForName(name) → reveal via
 *      showTextDocument and re-target; an ambiguous (zero/multiple) basename logs
 *      the unresolved title and falls through.
 *   2. First entry of tracker.recent() whose document is still open → tracked.
 *   3. Exactly one visible markdown editor → visible.
 *   4. { kind: 'none', reason } naming which step failed.
 *
 * Justification: the `log` parameter diverges from the LLD decomposition signature
 * `resolveTarget(tracker, activeTab)` to implement the LLD §2.3 error-table row
 * "focused preview title does not uniquely match → log the unresolved title to
 * `EDF Review`".
 */
export async function resolveTarget(
  tracker: EditorTracker,
  activeTab: vscode.Tab | undefined,
  log: (message: string) => void
): Promise<Resolution> {
  const name = previewTitleName(activeTab);
  if (name) {
    const doc = uniqueDocumentForName(name);
    if (doc) {
      const editor = await vscode.window.showTextDocument(doc, {
        preview: true,
        preserveFocus: true
      });
      return { kind: 'tracked', editor };
    }
    log(`preview tab title did not uniquely match an open markdown document (${name})`);
  }

  for (const editor of tracker.recent()) {
    if (!editor.document.isClosed) {
      return { kind: 'tracked', editor };
    }
  }

  const visible = vscode.window.visibleTextEditors.filter(
    (editor) => editor.document.languageId === 'markdown'
  );
  if (visible.length === 1) {
    return { kind: 'visible', editor: visible[0] };
  }

  const closedCount = tracker.recent().filter((entry) => entry.document.isClosed).length;
  const reason =
    closedCount > 0
      ? `${closedCount} recent markdown editor${closedCount === 1 ? '' : 's'} closed; no single visible markdown editor resolves`
      : visible.length === 0
        ? 'no markdown editor matches the focused preview title, the recency stack, or the visible editors'
        : `${visible.length} visible markdown editors; cannot disambiguate`;
  return { kind: 'none', reason };
}
