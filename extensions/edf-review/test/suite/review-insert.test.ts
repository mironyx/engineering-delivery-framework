/**
 * Issue #49 (v1-e1-2): heading extraction and review insertion-point pure modules.
 *
 * Specs for src/review-insert.ts — REVIEW_MARKER and findReviewInsertLine.
 * LLD §2.2 (Heading extraction and insertion point) Invariants 10-11, the issue's
 * findReviewInsertLine BDD block, and the "out-of-range headingLine returns
 * headingLine unchanged" error-handling clause from the Part B implementation
 * section.
 *
 * These specs follow the house style of scaffold.test.ts but deliberately import
 * no `vscode` module: review-insert.ts is a pure string function (LLD §2.2
 * Invariant 7), so its contract is exercised without the VS Code host. The Mocha
 * bootstrap in test/suite/index.ts picks the compiled file up via its star-star
 * glob over the compiled '*.test.js' files.
 */
import * as assert from 'assert';
import { REVIEW_MARKER, findReviewInsertLine } from '../../src/review-insert';

describe('findReviewInsertLine', () => {
  it('returns the heading line when no marker follows', () => {
    const lines = ['## Section', 'Some prose', '## Next Section'];
    assert.strictEqual(findReviewInsertLine(lines, 0), 0);
  });

  it('returns the single marker line when one follows', () => {
    const lines = [
      '## Section',
      '> **[Review]:** note about the auth boundary',
      'More prose'
    ];
    assert.strictEqual(findReviewInsertLine(lines, 0), 1);
  });

  it('returns the last marker when several are consecutive', () => {
    const lines = [
      '## Section',
      '> **[Review]:** first',
      '> **[Review]:** second',
      '> **[Review]:** third',
      'Follow-up prose'
    ];
    // Story 2.1 AC9: a new marker is inserted after the existing markers,
    // preserving their order — so the insert line is the LAST marker's line.
    assert.strictEqual(findReviewInsertLine(lines, 0), 3);
  });

  it('stops the run at a blank line', () => {
    const lines = [
      '## Section',
      '> **[Review]:** first',
      '> **[Review]:** second',
      '',
      '> **[Review]:** third'
    ];
    assert.strictEqual(findReviewInsertLine(lines, 0), 2);
  });

  it('stops the run at a prose line', () => {
    const lines = [
      '## Section',
      '> **[Review]:** first',
      'Some prose interrupts the run',
      '> **[Review]:** second'
    ];
    assert.strictEqual(findReviewInsertLine(lines, 0), 1);
  });

  it('handles a heading as the last line of the document', () => {
    const lines = ['## Section'];
    // Walking forward must not read past the end of the array; with no marker
    // following, the heading line is the insert line.
    assert.strictEqual(findReviewInsertLine(lines, 0), 0);
  });

  it('returns the heading line unchanged for an out-of-range headingLine', () => {
    // LLD §2.2 error handling: an out-of-range headingLine returns headingLine
    // unchanged and never throws.
    const lines = ['## Section', '> **[Review]:** note'];
    assert.doesNotThrow(() => findReviewInsertLine(lines, 99));
    assert.strictEqual(findReviewInsertLine(lines, 99), 99);
    assert.strictEqual(findReviewInsertLine(lines, -1), -1);
  });

  it('returns a negative headingLine unchanged even when a marker follows line 0', () => {
    // LLD §2.2 error handling: an out-of-range headingLine returns headingLine
    // unchanged. A negative headingLine is out of range — walking forward must
    // not treat line 0's marker as a valid run start and advance past it.
    const lines = ['> **[Review]:** note', '## Section'];
    assert.strictEqual(findReviewInsertLine(lines, -1), -1);
  });
});

describe('REVIEW_MARKER', () => {
  it('is exactly the blockquote literal including the trailing space', () => {
    // LLD §2.2 Invariant 10: the trailing space is significant — insertion relies
    // on it separating the marker from the reviewer's comment text.
    assert.strictEqual(REVIEW_MARKER, '> **[Review]:** ');
    assert.strictEqual(REVIEW_MARKER.length, 16);
  });
});
