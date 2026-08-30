/**
 * Editor tracker and target resolution — extension host.
 *
 * LLD v1-e1-2 §2.3 (0.8, never guess): the focused markdown preview is the ONLY
 * legitimate trigger — `activeTextEditor` is undefined while a webview holds
 * focus, which is the normal case here, not an error. The tracker keeps a
 * bounded MRU stack of markdown editors (seeded from `visibleTextEditors` at
 * activation, deduped on focus, cap 5, closed documents pruned), and
 * `resolveTarget` resolves the preview's tab title to the tracked editor whose
 * basename uniquely matches — stopping with guidance when there is no preview,
 * no match, or an ambiguous match.
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
  | { kind: 'resolved'; editor: vscode.TextEditor }
  | { kind: 'none'; reason: string };

/** Shown when the focused tab is not the built-in markdown preview. */
export const NO_PREVIEW_MSG = 'Run this command while the markdown preview is focused';
/**
 * Shown when the preview title matches zero tracked open editors — the source
 * editor was closed (with or without a restart) while the preview stayed open,
 * or it fell off the bounded stack. The user's action is to open the original
 * file and retry (LLD 0.8 — the old "no source document found" was a dead end).
 */
export const NO_DOCUMENT_MSG = 'Open the original markdown file in VS Code, then retry';
/** Shown when the preview title matches multiple tracked editors (same basename). */
export const AMBIGUOUS_MSG = (name: string): string =>
  `Two documents named ${name} are open — close the one you don't want, then retry`;

/**
 * Create an editor tracker. Maintains a bounded MRU stack of markdown editors:
 * seeded from the markdown editors already visible at activation, then on focus
 * the editor moves to the front (deduped), the tail beyond `cap` is evicted, and
 * entries whose document closes are pruned. All disposables are pushed onto
 * `context.subscriptions`.
 */
export function createEditorTracker(
  context: vscode.ExtensionContext,
  cap = 5
): EditorTracker {
  // Seed with what is already open at activation (LLD 0.8): activation is lazy
  // (empty activationEvents, fires on the first command run), so without this a
  // command run right after activation would find an empty stack even though the
  // markdown file is open and on screen. Cap applies to the seed.
  const recent: vscode.TextEditor[] = vscode.window.visibleTextEditors
    .filter((editor) => editor.document.languageId === 'markdown')
    .slice(0, cap);

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
 * The basename of a focused markdown source-editor tab, when the active tab is a
 * markdown file editor (TabInput.Text); undefined otherwise. In a real split
 * layout the active tab is usually the source editor while the preview sits
 * beside it — both legitimately name the target (LLD 0.9, maintainer's
 * "there is a name — find in MRU"). Returns undefined for non-markdown tabs.
 */
export function editorTabName(activeTab: vscode.Tab | undefined): string | undefined {
  const uri = (activeTab?.input as { uri?: vscode.Uri } | undefined)?.uri;
  if (!uri || path.extname(uri.fsPath).toLowerCase() !== '.md') {
    return undefined;
  }
  return path.basename(uri.fsPath);
}

/**
 * Still-open MRU entries whose document's basename equals `name`, in recency
 * order. A document evicted from the bounded stack (or closed) is not found.
 */
export function mruMatchesForName(
  tracker: EditorTracker,
  name: string
): readonly vscode.TextEditor[] {
  return tracker.recent().filter(
    (editor) => !editor.document.isClosed && path.basename(editor.document.uri.fsPath) === name
  );
}

/**
 * Resolve the target editor for a review comment — never guess (LLD 0.7).
 *
 * The active tab names the target: the focused markdown preview's title, or a
 * focused markdown source editor (the common split-layout case — the active
 * tab is the editor while the preview sits beside it). Either yields a name;
 * anything else stops:
 *   1. No name from the active tab → stop with NO_PREVIEW_MSG.
 *   2. Name → still-open tracked editors whose basename matches.
 *   3. Exactly one match → reveal via showTextDocument and resolve to it.
 *   4. Zero matches → stop with NO_DOCUMENT_MSG — the source editor was closed
 *      or evicted; tell the user to open the original file.
 *   5. More than one match (same basename) → warn to close the wrong one, then
 *      stop with AMBIGUOUS_MSG — never guess.
 */
export async function resolveTarget(
  tracker: EditorTracker,
  activeTab: vscode.Tab | undefined
): Promise<Resolution> {
  const name = previewTitleName(activeTab) ?? editorTabName(activeTab);
  if (!name) {
    return { kind: 'none', reason: NO_PREVIEW_MSG };
  }

  const matches = mruMatchesForName(tracker, name);
  if (matches.length === 1) {
    const editor = await vscode.window.showTextDocument(matches[0].document, {
      preview: true,
      preserveFocus: true
    });
    return { kind: 'resolved', editor };
  }
  if (matches.length === 0) {
    return { kind: 'none', reason: NO_DOCUMENT_MSG };
  }
  await vscode.window.showWarningMessage(AMBIGUOUS_MSG(name));
  return { kind: 'none', reason: AMBIGUOUS_MSG(name) };
}
