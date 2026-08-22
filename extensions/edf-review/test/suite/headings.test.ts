/**
 * Issue #49 (v1-e1-2): heading extraction and review insertion-point pure modules.
 *
 * Specs for src/headings.ts — extractHeadings. LLD §2.2 (Heading extraction and
 * insertion point) Invariants 8-9, the issue's extractHeadings BDD block, and the
 * "never throws" error-handling clause from the Part B implementation section.
 *
 * These specs follow the house style of scaffold.test.ts but deliberately import
 * no `vscode` module: headings.ts is a pure string function (LLD §2.2 Invariant 7),
 * so its contract is exercised without the VS Code host. The Mocha bootstrap in
 * test/suite/index.ts picks the compiled file up via its star-star glob over
 * the compiled '*.test.js' files.
 */
import * as assert from 'assert';
import { extractHeadings } from '../../src/headings';

describe('extractHeadings', () => {
  it('extracts ## and ### headings with 0-based line numbers', () => {
    const text = [
      '# Title',
      'Intro paragraph.',
      '',
      '## Section One',
      'Some prose here.',
      '### Sub Section',
      'More prose.',
      '## Section Two'
    ].join('\n');

    const headings = extractHeadings(text);

    assert.deepStrictEqual(headings, [
      { line: 3, text: 'Section One', level: 2 },
      { line: 5, text: 'Sub Section', level: 3 },
      { line: 7, text: 'Section Two', level: 2 }
    ]);

    // LLD §2.2 Invariant 9: line numbers are 0-based and index the source array —
    // the line each heading names must start with that heading's hashes.
    for (const h of headings) {
      const sourceLine = text.split(/\r?\n/)[h.line];
      assert.ok(
        sourceLine.startsWith('#'.repeat(h.level)),
        `line ${h.line} must start with ${'#'.repeat(h.level)} hashes`
      );
    }
  });

  it('ignores a single # title', () => {
    const text = ['# Only a title', '', '## A section'].join('\n');
    assert.deepStrictEqual(extractHeadings(text), [
      { line: 2, text: 'A section', level: 2 }
    ]);
  });

  it('ignores #### and deeper headings', () => {
    const text = [
      '## Section',
      '#### Deep',
      '##### Deeper',
      '###### Deepest',
      '### Sub'
    ].join('\n');

    assert.deepStrictEqual(extractHeadings(text), [
      { line: 0, text: 'Section', level: 2 },
      { line: 4, text: 'Sub', level: 3 }
    ]);
  });

  it('strips leading hashes and trims heading text', () => {
    const text = ['##   Spaced Heading   ', '###   Sub   '].join('\n');
    assert.deepStrictEqual(extractHeadings(text), [
      { line: 0, text: 'Spaced Heading', level: 2 },
      { line: 1, text: 'Sub', level: 3 }
    ]);
  });

  it('handles ATX-close headings', () => {
    const text = ['## Section ##', '### Sub ###', '## Mixed close #'].join('\n');
    assert.deepStrictEqual(extractHeadings(text), [
      { line: 0, text: 'Section', level: 2 },
      { line: 1, text: 'Sub', level: 3 },
      { line: 2, text: 'Mixed close', level: 2 }
    ]);
  });

  it('ignores headings inside fenced code blocks', () => {
    // LLD §2.2 Part B constraint: an LLD's Part B routinely contains ```markdown
    // blocks demonstrating heading syntax; both backtick and tilde fences must
    // suppress headings until the fence closes.
    const text = [
      '## Real Heading',
      '',
      '```markdown',
      '## Fake Heading Inside Fence',
      '### Another Fake',
      '```',
      '',
      '### Real Sub',
      '',
      '~~~',
      '## Fake Inside Tilde Fence',
      '~~~',
      '',
      '## Real After Both Fences'
    ].join('\n');

    assert.deepStrictEqual(extractHeadings(text), [
      { line: 0, text: 'Real Heading', level: 2 },
      { line: 7, text: 'Real Sub', level: 3 },
      { line: 13, text: 'Real After Both Fences', level: 2 }
    ]);
  });

  it('keeps suppressing headings under a nested fence of a different marker', () => {
    // LLD §2.2 Part B constraint: an LLD's Part B ```markdown block can itself
    // demonstrate a fence (e.g. a ~~~ example inside a backtick block). A fence
    // of a different marker char inside an open fence is content, not a close —
    // headings stay suppressed until the outer fence closes.
    const text = [
      '## Real Heading',
      '',
      '```markdown',
      '## Fake Heading',
      '~~~',
      '## Still Fake (inside the outer fence)',
      '~~~',
      '### Also Fake',
      '```',
      '',
      '## Real After Fence'
    ].join('\n');

    assert.deepStrictEqual(extractHeadings(text), [
      { line: 0, text: 'Real Heading', level: 2 },
      { line: 10, text: 'Real After Fence', level: 2 }
    ]);
  });

  it('returns an empty array for a document with no headings', () => {
    const prose = [
      'Just prose with no headings.',
      '',
      '- a list item',
      '- another',
      '',
      'plain text'
    ].join('\n');
    assert.deepStrictEqual(extractHeadings(prose), []);
    assert.deepStrictEqual(extractHeadings(''), []);
  });

  it('splits on CRLF line endings', () => {
    // The split is on /\r?\n/, so a Windows-ending document yields the same
    // headings and 0-based line numbers as an LF-ending one.
    const text = '## First\r\nprose\r\n### Second';
    assert.deepStrictEqual(extractHeadings(text), [
      { line: 0, text: 'First', level: 2 },
      { line: 2, text: 'Second', level: 3 }
    ]);
  });

  it('never throws on malformed heading syntax', () => {
    // LLD §2.2 error handling: a malformed document yields fewer headings, never
    // an exception. Bare hashes (no space after) match no heading level.
    assert.doesNotThrow(() => extractHeadings('###\n##\n#\n#######\n'));
  });
});
