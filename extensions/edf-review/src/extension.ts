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
import { EditorTracker } from './editor-tracker';
import { createEditorTracker, resolveTarget } from './editor-tracker';
import { createLog } from './log';

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
export async function insertReviewComment(
  tracker: EditorTracker,
  log: (message: string) => void
): Promise<void> {
  throw new Error('not implemented');
}

export function deactivate() {}
