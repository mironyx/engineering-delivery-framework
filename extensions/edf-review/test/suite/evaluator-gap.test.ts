/**
 * Issue #48 (v1-e1-2): evaluation specs for scaffold manifest invariants not
 * asserted by scaffold.test.ts — the emptied activationEvents, the
 * displayName/description wording, the version bump, the absent media/
 * directory, and the palette command's title/category.
 *
 * Each is an LLD §2.1 acceptance criterion or Part B constraint that would
 * otherwise be verified only by a reviewer reading package.json by hand; a
 * regression (re-adding onMarkdownPreview, an "EDF: EDF:" double-prefix title,
 * a resurrected media/) would ship silently without these specs. They run in
 * the same test host as scaffold.test.ts and read the manifest from the same
 * shared helper (./manifest).
 */
import * as path from 'path';
import * as fs from 'fs';
import * as assert from 'assert';
import { readManifest } from './manifest';

describe('extension scaffold — manifest invariants (evaluator)', () => {
  it('declares an empty activationEvents array', () => {
    // Issue AC4 / LLD §2.1 AC: activationEvents emptied, activation left to the
    // auto-generated onCommand: from contributes.commands (OQ2 consequence).
    assert.deepStrictEqual(
      readManifest().activationEvents,
      [],
      'activationEvents must be empty — onMarkdownPreview died with the preview script'
    );
  });

  it('describes no edf:// hover/click behaviour in displayName or description', () => {
    // Issue AC5 / LLD §2.1 AC: the manifest metadata must not describe the
    // deleted spike's edf:// hover/click machinery.
    const { displayName = '', description = '' } = readManifest();
    for (const [field, value] of [
      ['displayName', displayName],
      ['description', description]
    ] as const) {
      assert.ok(
        !value.includes('edf://'),
        `${field} must not mention the edf:// scheme`
      );
      assert.ok(!value.includes('hover'), `${field} must not describe hover behaviour`);
      assert.ok(!value.includes('peek'), `${field} must not describe peek behaviour`);
    }
  });

  it('bumps the manifest version to 0.2.0', () => {
    // Issue: "package.json — manifest rewrite; version 0.2.0".
    assert.strictEqual(readManifest().version, '0.2.0');
  });

  it('leaves no media/ directory in the extension tree', () => {
    // LLD §2.1 Invariant 3 first half: media/ does not exist. Its absence is
    // what lets a reader of the shipped .vsix confirm nothing is injected.
    const mediaDir = path.join(__dirname, '../../../media');
    assert.ok(
      !fs.existsSync(mediaDir),
      'media/ must not exist in the extension tree'
    );
  });

  it('declares the palette command without an EDF: title prefix', () => {
    // LLD §2.1 Part B constraint: title "Insert Review Comment" with category
    // "EDF" — VS Code renders this as "EDF: Insert Review Comment"; a title
    // that repeats the category renders "EDF: EDF: Insert Review Comment".
    const commands = readManifest().contributes?.commands ?? [];
    assert.strictEqual(commands.length, 1, 'exactly one command must be declared');
    assert.strictEqual(commands[0].category, 'EDF');
    assert.strictEqual(commands[0].title, 'Insert Review Comment');
  });
});
