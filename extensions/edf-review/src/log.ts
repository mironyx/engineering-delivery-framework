/**
 * EDF Review output channel wrapper — extension host.
 *
 * LLD v1-e1-2 §2.3: resolution failures are logged to a dedicated output
 * channel so the reviewer can see *why* no document resolved, rather than
 * silently no-op'ing.
 */
import * as vscode from 'vscode';

/** One `EDF Review` channel per extension context, shared across consumers. */
const channelByContext = new WeakMap<
  vscode.ExtensionContext,
  vscode.OutputChannel
>();

/**
 * Create (or reuse) the `EDF Review` output channel and return an `appendLine`
 * wrapper. The channel is disposed via `context.subscriptions`. §2.5's overlay
 * relay reuses the same channel (§2.3's Logger) rather than opening a second.
 */
export function createLog(context: vscode.ExtensionContext): (message: string) => void {
  let channel = channelByContext.get(context);
  if (!channel) {
    channel = vscode.window.createOutputChannel('EDF Review');
    channelByContext.set(context, channel);
    context.subscriptions.push(channel);
  }
  return (message) => channel.appendLine(message);
}
