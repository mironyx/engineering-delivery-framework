/**
 * Issue #48 (v1-e1-2): extension scaffold BDD specs — LLD §2.1.
 *
 * These specs run inside the VS Code test host launched by @vscode/test-electron
 * (see test/runTest.ts) and are discovered by the Mocha bootstrap's star-star
 * glob over '*.test.js' in out/test/ (test/suite/index.ts). They assert the
 * scaffold contract through the public surface only: the VS Code extension API
 * and the packaged manifest — never extension internals.
 *
 * The manifest is read from the compiled location: out/test/suite/, so
 * path.join(__dirname, '../../../package.json') resolves to
 * extensions/edf-review/package.json.
 */
import * as vscode from 'vscode';
import * as assert from 'assert';
import { readManifest } from './manifest';

const EXTENSION_ID = 'mironyx.edf-review';

describe('extension scaffold', () => {
  it('activates without error in a test host', async () => {
    const extension = vscode.extensions.getExtension(EXTENSION_ID);

    // A dev extension (extensionDevelopmentPath) must be loaded in the host;
    // if it is not, fail loudly rather than silently passing.
    assert.ok(
      extension,
      `extension ${EXTENSION_ID} must be loaded in the test host (extensionDevelopmentPath)`
    );

    if (!extension.isActive) {
      // Dev extensions are usually already active; activate() makes the
      // assertion robust when the host activates on demand instead.
      await extension.activate();
    }

    assert.strictEqual(
      extension.isActive,
      true,
      `extension ${EXTENSION_ID} must be active after activation`
    );
  });

  it('exposes no command other than those declared in the manifest', async () => {
    const manifest = readManifest();
    const declaredCommands = (manifest.contributes?.commands ?? []).map(
      (command) => command.command
    );

    // getCommands() returns every command registered by all extensions in the
    // host; filter to this extension's namespace.
    const registeredCommands = await vscode.commands.getCommands();
    const registeredOurs = registeredCommands.filter((id) =>
      id.startsWith('edf-review.')
    );

    // Registered must be a subset of declared: any edf-review.* command not
    // declared in the manifest is an undeclared command. An empty registered
    // set (the reduced scaffold registers nothing until #50) is a PASS.
    const undeclared = registeredOurs.filter(
      (id) => !declaredCommands.includes(id)
    );
    assert.deepStrictEqual(
      undeclared,
      [],
      `commands registered under edf-review.* but not declared in the manifest: ${undeclared.join(', ')}`
    );
  });

  it('declares the overlay preview script and the overlay-log command (LLD §2.5)', () => {
    const manifest = readManifest();
    const contributes = manifest.contributes ?? {};

    // Task 5 (§2.5, issue #63) supersedes LLD §2.1 Invariants 3/6: the manifest
    // now contributes markdown.previewScripts (the diagram overlay) alongside
    // the commands. The overlay-log command is hidden from the palette.
    assert.ok(
      Array.isArray(contributes.commands),
      'contributes.commands must remain an array'
    );
    const commandIds = (contributes.commands as Array<{ command: string }>).map(
      (c) => c.command
    );
    assert.ok(
      commandIds.includes('edf-review.overlayLog'),
      'contributes.commands must declare edf-review.overlayLog'
    );

    const markdown = (contributes['markdown'] ?? {}) as { previewScripts?: unknown };
    assert.deepStrictEqual(
      markdown.previewScripts,
      ['./media/overlay.js'],
      'contributes.markdown.previewScripts must declare the overlay script'
    );

    // The overlay-log command is a relay hook, not a user-facing palette action.
    const palette = (contributes['commandPalette'] ?? []) as Array<{
      command: string;
      when?: string;
    }>;
    const hidden = palette.find((entry) => entry.command === 'edf-review.overlayLog');
    assert.strictEqual(hidden?.when, 'false', 'edf-review.overlayLog must be hidden from the palette');
  });
});
