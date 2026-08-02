/**
 * EDF Review — VSCode Extension Host
 *
 * Handles messages from the injected preview script:
 *   `peek`  — read the first ~40 lines of a source file, post result back
 *   `open`  — open the file in the right editor column, preview stays open
 *
 * The markdown preview webview is received as the second argument to
 * onDidReceivePreviewMessage (available since VSCode 1.82).
 */
import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {

  context.subscriptions.push(
    vscode.window.onDidReceivePreviewMessage(
      (msg: { command: string; path: string; nonce?: string },
       panel: vscode.WebviewPanel) => {

        if (msg.command === 'peek') {
          handlePeek(msg.path, panel);
        } else if (msg.command === 'open') {
          handleOpen(msg.path);
        }
      }
    )
  );
}

async function handlePeek(filePath: string, panel: vscode.WebviewPanel) {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders || workspaceFolders.length === 0) {
    panel.webview.postMessage({ command: 'peekResult', text: null });
    return;
  }

  const root = workspaceFolders[0].uri;
  const fileUri = vscode.Uri.joinPath(root, filePath);

  try {
    const contents = await vscode.workspace.fs.readFile(fileUri);
    const text = new TextDecoder().decode(contents);
    const lines = text.split('\n');
    const snippet = lines.slice(0, 40).join('\n');
    const tail = lines.length > 40
      ? `\n\n… (${lines.length - 40} more lines)`
      : '';

    panel.webview.postMessage({
      command: 'peekResult',
      text: snippet + tail,
      path: filePath
    });
  } catch {
    // File missing or unreadable — silent
    panel.webview.postMessage({ command: 'peekResult', text: null });
  }
}

async function handleOpen(filePath: string) {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders || workspaceFolders.length === 0) {
    return;
  }

  const root = workspaceFolders[0].uri;
  const fileUri = vscode.Uri.joinPath(root, filePath);

  try {
    await vscode.workspace.fs.stat(fileUri);
    await vscode.window.showTextDocument(fileUri, {
      viewColumn: vscode.ViewColumn.Beside,
      preserveFocus: false
    });
  } catch {
    // File doesn't exist — silent no-op
  }
}

export function deactivate() {}
