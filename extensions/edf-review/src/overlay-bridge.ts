/**
 * EDF Review — overlay error relay (extension host).
 *
 * LLD v1-e1-2 §2.5: relays `media/overlay.js` script errors to the `EDF Review`
 * output channel. The overlay posts `{ type: 'edf-overlay-error', message }`;
 * the bridge turns relayed errors into channel lines and never throws. The
 * `edf-review.overlayLog` command is the designed hook the preview webview's
 * postMessage triggers (declared in the manifest so it carries an auto-generated
 * activation event while `activationEvents` stays empty).
 */
import * as vscode from 'vscode';
import { createLog } from './log';

export interface OverlayLog {
  log(message: string): void;
  handleMessage(message: unknown): void;
}

export function createOverlayLog(context: vscode.ExtensionContext): OverlayLog {
  const log = createLog(context);
  const handleMessage = (message: unknown): void => {
    log(`[overlay] ${extractErrorText(message)}`);
  };
  context.subscriptions.push(
    vscode.commands.registerCommand('edf-review.overlayLog', handleMessage)
  );
  return { log: handleMessage, handleMessage };
}

/** Coerce a relayed value to a loggable line — never throws on malformed input. */
function extractErrorText(message: unknown): string {
  if (typeof message === 'string') {
    return message;
  }
  if (typeof message === 'number' || typeof message === 'boolean') {
    return String(message);
  }
  if (message && typeof message === 'object') {
    const nested = (message as { message?: unknown }).message;
    if (typeof nested === 'string') {
      return nested;
    }
    if (typeof nested === 'number' || typeof nested === 'boolean') {
      return String(nested);
    }
  }
  try {
    return JSON.stringify(message) ?? String(message);
  } catch {
    return String(message);
  }
}
