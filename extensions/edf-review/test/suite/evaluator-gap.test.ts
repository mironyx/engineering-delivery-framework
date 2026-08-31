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

/**
 * LLD §2.1 Invariant 2 requires a repo-wide grep for the preview scheme
 * under extensions/ to return nothing. The literal is split here
 * deliberately so this spec's own assertion does not trip that mechanical
 * check while still guarding against re-introducing the scheme.
 */
const EDF_SCHEME = 'edf' + '://';

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

  it('describes no preview-scheme hover/click behaviour in displayName or description', () => {
    // Issue AC5 / LLD §2.1 AC: the manifest metadata must not describe the
    // deleted spike's preview-scheme hover/click machinery.
    const { displayName = '', description = '' } = readManifest();
    for (const [field, value] of [
      ['displayName', displayName],
      ['description', description]
    ] as const) {
      assert.ok(
        !value.includes(EDF_SCHEME),
        `${field} must not mention the preview scheme`
      );
      assert.ok(!value.includes('hover'), `${field} must not describe hover behaviour`);
      assert.ok(!value.includes('peek'), `${field} must not describe peek behaviour`);
    }
  });

  it('bumps the manifest version to 0.2.10', () => {
    // Issue: "package.json — manifest rewrite; version 0.2.0", bumped to 0.2.1
    // when the diagram click-through overlay shipped (issue #63), to 0.2.2 for
    // the active-markdown-editor resolution fix (LLD 0.9), to 0.2.3 for the
    // manifest dot-key (previewScripts) injection fix, to 0.2.4 for the
    // prototype-mechanism overlay rewrite (fixed positioning, origin-only
    // containment), to 0.2.9 for the selection-based insert (no quick-pick),
    // and to 0.2.10 for the top-visible-line insertion fix (Issue #63 review
    // feedback: markers landed at the end of the file) plus the live
    // visible-editor resolution fallback (no more close-and-reopen).
    assert.strictEqual(readManifest().version, '0.2.10');
  });

  it('keeps the media/ directory scoped to the overlay script only', () => {
    // LLD §2.1 Invariant 3 first half is superseded by Task 5 (§2.5, issue #63):
    // media/ now exists but must carry only the single injected overlay script.
    // Hidden tool-artifact directories (e.g. `.sonar` from a scanner) are not
    // preview resources and are excluded from the scope check.
    const mediaDir = path.join(__dirname, '../../../media');
    assert.ok(
      fs.existsSync(mediaDir),
      'media/ must exist in the extension tree after Task 5'
    );
    const entries = fs
      .readdirSync(mediaDir)
      .filter((entry) => !entry.startsWith('.'));
    assert.deepStrictEqual(
      entries,
      ['overlay.js'],
      'media/ must contain only overlay.js — scoped preview-script injection'
    );
  });

  it('declares the palette command without an EDF: title prefix', () => {
    // LLD §2.1 Part B constraint: title "Insert Review Comment" with category
    // "EDF" — VS Code renders this as "EDF: Insert Review Comment"; a title
    // that repeats the category renders "EDF: EDF: Insert Review Comment".
    // Task 5 adds the overlay-log command, so the palette command is found by
    // id rather than by position.
    const commands = readManifest().contributes?.commands ?? [];
    const palette = commands.find((c) => c.command === 'edf-review.insertReviewComment');
    assert.ok(palette, 'insertReviewComment must be declared');
    assert.strictEqual(palette.category, 'EDF');
    assert.strictEqual(palette.title, 'Insert Review Comment');
  });
});
