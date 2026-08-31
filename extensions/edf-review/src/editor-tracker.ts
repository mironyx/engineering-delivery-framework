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
 * Shown when the preview title matches zero tracked AND zero visible open
 * editors — the source editor is genuinely closed. The user's action is to open
 * the original file and retry (LLD 0.8 — the old "no source document found" was
 * a dead end). resolveTarget first consults the tracker, then the live visible
 * editor set, so a merely-unfocused editor never reaches this message.
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
  // Seed dedupes by document URI: the same markdown file open in two groups
  // appears as two editors in visibleTextEditors, but names the preview once —
  // a false ambiguity otherwise (review finding: "two documents named X" for
  // one file).
  const recent: vscode.TextEditor[] = [];
  const seeded = new Set<string>();
  for (const editor of vscode.window.visibleTextEditors) {
    if (editor.document.languageId !== 'markdown') {
      continue;
    }
    const uri = editor.document.uri.toString();
    if (seeded.has(uri)) {
      continue;
    }
    seeded.add(uri);
    recent.push(editor);
    if (recent.length >= cap) {
      break;
    }
  }

  const focusDisposable = vscode.window.onDidChangeActiveTextEditor((editor) => {
    if (!editor || editor.document.languageId !== 'markdown') {
      return;
    }
    // Dedupe by document identity, not editor object: showTextDocument mints a
    // fresh TextEditor per view, so two views of one file would otherwise stack.
    const existing = recent.findIndex((e) => e.document === editor.document);
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
  if (typeof viewType !== 'string') {
    return undefined;
  }
  // This VS Code build reports the webview tab's viewType with a
  // `mainThreadWebview-` prefix (observed: `mainThreadWebview-markdown.preview`);
  // strip it so the match survives builds that omit the prefix.
  if (viewType.replace(/^mainThreadWebview-/, '') !== 'markdown.preview') {
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
 * Visible markdown editors whose document's basename equals `name`, deduped by
 * document URI (the same file open in two groups appears once).
 */
export function visibleMarkdownEditorsNamed(name: string): readonly vscode.TextEditor[] {
  const seen = new Set<string>();
  const result: vscode.TextEditor[] = [];
  for (const editor of vscode.window.visibleTextEditors) {
    if (editor.document.isClosed || editor.document.languageId !== 'markdown') {
      continue;
    }
    if (path.basename(editor.document.uri.fsPath) !== name) {
      continue;
    }
    const uri = editor.document.uri.toString();
    if (seen.has(uri)) {
      continue;
    }
    seen.add(uri);
    result.push(editor);
  }
  return result;
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
 *   4. Zero tracked matches → fall back to the visible editor set (an editor
 *      opened without gaining focus is tracked by no one); exactly one visible
 *      match resolves, else NO_DOCUMENT_MSG / AMBIGUOUS_MSG as appropriate.
 *   5. More than one tracked match (same basename) → warn to close the wrong
 *      one, then stop with AMBIGUOUS_MSG — never guess.
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
    // Fallback over the live editor set: an editor opened without ever gaining
    // focus (e.g. a diagram click-link that opens with preserveFocus) never
    // entered the tracker, and the reviewer must not be told to close and
    // reopen the file to "refresh" it (review feedback #63). If exactly one
    // VISIBLE markdown editor matches the name, resolve to it.
    const live = visibleMarkdownEditorsNamed(name);
    if (live.length === 1) {
      const editor = await vscode.window.showTextDocument(live[0].document, {
        preview: true,
        preserveFocus: true
      });
      return { kind: 'resolved', editor };
    }
    if (live.length > 1) {
      await vscode.window.showWarningMessage(AMBIGUOUS_MSG(name));
      return { kind: 'none', reason: AMBIGUOUS_MSG(name) };
    }
    return { kind: 'none', reason: NO_DOCUMENT_MSG };
  }
  await vscode.window.showWarningMessage(AMBIGUOUS_MSG(name));
  return { kind: 'none', reason: AMBIGUOUS_MSG(name) };
}
