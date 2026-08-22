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
import { Heading, extractHeadings } from './headings';
import { REVIEW_MARKER, findReviewInsertLine } from './review-insert';

/** Shown when neither a tracked nor a single visible markdown editor resolves. */
export const NO_DOCUMENT_MSG = 'No source document found for this preview';
/** Shown when the resolved document has no `##`/`###` headings. */
export const NO_HEADINGS_MSG = 'No section headings found in this document';

export function activate(context: vscode.ExtensionContext) {
  const tracker = createEditorTracker(context);
  const log = createLog(context);

  context.subscriptions.push(
    vscode.commands.registerCommand('edf-review.insertReviewComment', () =>
      insertReviewComment(tracker, log)
    )
  );
}

/**
 * Insert a `[Review]` marker under a heading chosen from a quick-pick.
 *
 * Orchestration only (LLD §2.3 Part B): resolve the target, extract headings,
 * quick-pick, single-edit insertion, cursor placement, focus.
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

async function applyMarker(
  editor: vscode.TextEditor,
  headingLine: number,
  log: (message: string) => void
): Promise<void> {
  const lines = editor.document.getText().split(/\r?\n/);
  const at = findReviewInsertLine(lines, headingLine);
  const ok = await editor.edit((edit) =>
    edit.insert(new vscode.Position(at + 1, 0), REVIEW_MARKER + '\n')
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
  const res = resolveTarget(tracker);
  if (res.kind === 'none') {
    log(res.reason);
    await vscode.window.showInformationMessage(NO_DOCUMENT_MSG);
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
