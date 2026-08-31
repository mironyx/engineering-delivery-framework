/**
 * EDF Review — VSCode Extension Host
 *
 * Registers `edf-review.insertReviewComment`. When a webview holds focus,
 * `activeTextEditor` is undefined, so the command resolves the intended markdown
 * document through the editor tracker (editor-tracker.ts), then picks the
 * insertion line from where the reviewer clicked (see `insertionLineFor`).
 */
import * as vscode from 'vscode';
import { EditorTracker, createEditorTracker, resolveTarget } from './editor-tracker';
import { createLog } from './log';
import { createOverlayLog } from './overlay-bridge';
import { REVIEW_MARKER, findReviewInsertLine } from './review-insert';

export function activate(context: vscode.ExtensionContext) {
  const tracker = createEditorTracker(context);
  const log = createLog(context);
  // §2.5: registers edf-review.overlayLog and reuses the same EDF Review channel.
  createOverlayLog(context);

  context.subscriptions.push(
    vscode.commands.registerCommand('edf-review.insertReviewComment', () =>
      insertReviewComment(tracker, log)
    )
  );
}

/**
 * Insert a `[Review]` marker on the line after `line` — a single edit, cursor
 * placement, then focus. The inserted newline honors the document's line endings
 * so CRLF files do not gain a mixed line-ending edit.
 */
export async function applyMarker(
  editor: vscode.TextEditor,
  line: number,
  log: (message: string) => void
): Promise<void> {
  const lines = editor.document.getText().split(/\r?\n/);
  const at = findReviewInsertLine(lines, line);
  const newline = editor.document.eol === vscode.EndOfLine.CRLF ? '\r\n' : '\n';
  // When the target line (or the last consecutive marker) is the document's final
  // line and the file has no trailing newline, `at + 1 === lines.length` and
  // Position(at + 1, 0) is end-of-document — prepend the newline so the marker
  // lands on its own line instead of being glued onto the text above it.
  const separator = at + 1 === lines.length ? newline : '';
  const ok = await editor.edit((edit) =>
    edit.insert(new vscode.Position(at + 1, 0), separator + REVIEW_MARKER + newline)
  );
  if (!ok) {
    log('failed to insert review marker');
    await vscode.window.showErrorMessage('Failed to insert review marker');
    return;
  }
  const pos = new vscode.Position(at + 1, REVIEW_MARKER.length);
  editor.selection = new vscode.Selection(pos, pos);
  await vscode.window.showTextDocument(editor.document, editor.viewColumn, false);
}

/**
 * The line below which a marker is inserted.
 *
 * Two flows, discriminated by which editor holds focus:
 *  - A text editor focused and it is the resolved source → the cursor line is
 *    authoritative (plain "insert below where my cursor is" flow).
 *  - No text editor focused (the markdown preview webview holds focus) → the
 *    reviewer just clicked a line in the preview. The built-in preview has
 *    already scrolled the source editor so the clicked line sits at the TOP of
 *    its viewport (`markdown.preview.scrollEditorWithPreview`, default on; the
 *    `revealLine` handler uses `TextEditorRevealType.AtTop`), so the top-visible
 *    line IS the clicked line. This deliberately does NOT read the source
 *    selection: a single preview click never moves the source cursor in this
 *    build (`markdown.preview.markEditorSelection` only adds a CSS class), so
 *    the selection would be a stale cursor — the bug that put markers at the
 *    end of the file.
 *
 * Falls back to the cursor line when the editor has no visible range.
 */
export function insertionLineFor(
  editor: vscode.TextEditor,
  focusedEditor: vscode.TextEditor | undefined
): number {
  if (focusedEditor && focusedEditor.document.uri.toString() === editor.document.uri.toString()) {
    return editor.selection.active.line;
  }
  const ranges = editor.visibleRanges;
  const top = ranges && ranges.length > 0 ? ranges[0].start.line : undefined;
  return typeof top === 'number' ? top : editor.selection.active.line;
}

/**
 * Insert a `[Review]` marker below the line the reviewer means — the clicked
 * preview line when the preview holds focus, else the source cursor line (no
 * quick-pick, per review feedback).
 */
export async function insertReviewComment(
  tracker: EditorTracker,
  log: (message: string) => void
): Promise<void> {
  const res = await resolveTarget(tracker, vscode.window.tabGroups.activeTabGroup?.activeTab);
  if (res.kind === 'none') {
    log(res.reason);
    await vscode.window.showWarningMessage(res.reason);
    return;
  }

  const line = insertionLineFor(res.editor, vscode.window.activeTextEditor);
  await applyMarker(res.editor, line, log);
}

export function deactivate() {}
