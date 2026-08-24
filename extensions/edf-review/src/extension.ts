/**
 * EDF Review — VSCode Extension Host
 *
 * LLD v1-e1-2 §2.3: registers `edf-review.insertReviewComment` and solves the
 * command's one hard problem — identifying which document the reviewer meant
 * when a webview holds focus and `activeTextEditor` is `undefined`. Target
 * resolution goes through the editor tracker (§2.3); heading extraction and
 * the insertion point come from the pure modules built in #49.
 */
import * as vscode from 'vscode';
import { EditorTracker, createEditorTracker, resolveTarget } from './editor-tracker';
import { createLog } from './log';
import { createOverlayLog } from './overlay-bridge';
import { Heading, extractHeadings } from './headings';
import { REVIEW_MARKER, findReviewInsertLine } from './review-insert';

/** Shown when the resolved document has no `##`/`###` headings. */
export const NO_HEADINGS_MSG = 'No section headings found in this document';

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
 * Insert a `[Review]` marker under a heading chosen from a quick-pick.
 *
 * Orchestration only (LLD §2.3 Part B): resolve the target (0.7, never guess —
 * the focused markdown preview must uniquely name a tracked editor), extract
 * headings, quick-pick, single-edit insertion, cursor placement, focus.
 */
/** A quick-pick item carrying the 0-based heading line the marker is inserted under. */
type HeadingPickItem = vscode.QuickPickItem & { line: number };

function toItems(headings: Heading[]): HeadingPickItem[] {
  return headings.map((heading) => ({
    label: '#'.repeat(heading.level) + ' ' + heading.text,
    description: `line ${heading.line + 1}`, // 1-based — what the editor gutter shows
    line: heading.line
  }));
}

/**
 * Insert a `[Review]` marker on the line after a heading — a single edit, cursor
 * placement, then focus. The inserted newline honors the document's line endings
 * so CRLF files do not gain a mixed line-ending edit.
 *
 * Justification: diverges from the LLD decomposition signature
 * `applyMarker(editor, headingLine)` in three ways, all documented:
 *  - a `log` parameter to implement the LLD §2.3 error-table row "editor.edit
 *    returns false → log the failure; show a message";
 *  - a stale-heading guard (review finding #73): if the selected heading was
 *    deleted while the quick-pick was open, fail explicitly rather than throw;
 *  - an EOL-honouring newline (review finding #73): CRLF documents must not gain
 *    a mixed line-ending edit.
 */
async function applyMarker(
  editor: vscode.TextEditor,
  headingLine: number,
  log: (message: string) => void
): Promise<void> {
  const lines = editor.document.getText().split(/\r?\n/);
  const at = findReviewInsertLine(lines, headingLine);
  if (at + 1 > lines.length) {
    // The selected heading was deleted while the quick-pick was open.
    // findReviewInsertLine returns an out-of-range headingLine unchanged, so
    // inserting at `at + 1` would throw an unhandled RangeError. Fail explicitly.
    log('selected heading no longer exists in the document');
    await vscode.window.showErrorMessage('Selected heading no longer exists');
    return;
  }
  const newline = editor.document.eol === vscode.EndOfLine.CRLF ? '\r\n' : '\n';
  // When the heading (or last consecutive marker) is the document's final line and
  // the file has no trailing newline, `at + 1 === lines.length` and Position(at + 1, 0)
  // is end-of-document — prepend the newline so the marker lands on its own line
  // instead of being glued onto the heading text (review finding #73 re-review).
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

  const headings = extractHeadings(res.editor.document.getText());
  if (headings.length === 0) {
    await vscode.window.showInformationMessage(NO_HEADINGS_MSG);
    return;
  }

  const picked = await vscode.window.showQuickPick(toItems(headings), {
    placeHolder: 'Select the section to insert a review comment under',
    matchOnDetail: false
  });
  if (!picked) {
    return; // Escape — true no-op, no edit applied
  }

  await applyMarker(res.editor, picked.line, log);
}

export function deactivate() {}
