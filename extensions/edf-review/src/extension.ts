/**
 * EDF Review — VSCode Extension Host
 *
 * Reduced to the activation pair. The spike's `peek`/`open` handlers targeted
 * a preview-message API that does not exist in the public API surface, so they
 * were deleted; the spike's findings are preserved in ADR-0038's rejection note
 * and in git history. Command registration lands with the Insert Review Comment
 * command (issue #50).
 */
import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
  // No handlers yet — command registration arrives in #50.
}

export function deactivate() {}
