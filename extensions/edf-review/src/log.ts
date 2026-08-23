/**
 * EDF Review output channel wrapper — extension host.
 *
 * LLD v1-e1-2 §2.3: resolution failures are logged to a dedicated output
 * channel so the reviewer can see *why* no document resolved, rather than
 * silently no-op'ing.
 */
import * as vscode from 'vscode';

/**
 * Create the `EDF Review` output channel and return an `appendLine` wrapper.
 * The channel is disposed via `context.subscriptions`.
 */
export function createLog(context: vscode.ExtensionContext): (message: string) => void {
  const channel = vscode.window.createOutputChannel('EDF Review');
  context.subscriptions.push(channel);
  return (message) => channel.appendLine(message);
}
