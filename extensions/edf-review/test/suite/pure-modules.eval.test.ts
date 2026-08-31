/**
 * Issue #49 (v1-e1-2): evaluation specs for a pure-module contract property the
 * test-author's specs only mention in comments — LLD §2.2 Invariant 7 and issue
 * AC-8: neither src/headings.ts nor src/review-insert.ts imports `vscode`.
 *
 * That import-freedom is what lets both module specs run without the VS Code
 * host (the standalone `npx mocha` path). A regression that imports vscode into
 * a "pure" module would still pass every spec under the test host — vscode is
 * resolvable there — while silently breaking the host-free guarantee. The LLD's
 * own verification for the invariant is a grep (`grep -L "from 'vscode'"`), so
 * this spec reads the source .ts the same way, not the compiled .js.
 */
import * as fs from 'fs';
import * as path from 'path';
import * as assert from 'assert';

const PURE_MODULES = ['headings.ts', 'review-insert.ts'] as const;

describe('pure modules — host-freedom (LLD §2.2 Invariant 7)', () => {
  for (const file of PURE_MODULES) {
    it(`${file} imports nothing from vscode`, () => {
      const src = fs.readFileSync(
        path.join(__dirname, '../../../src', file),
        'utf8'
      );
      // Matches the LLD grep: an import/require of the vscode module by source
      // name. 'VSCode' (capitalised, in prose) is not an import and is not
      // matched; the backticked `vscode` in the modules' own comments is not
      // preceded by from/require(/import(.
      const vscodeImport =
        /(?:from\s+|require\(\s*|import\(\s*)['"]vscode['"]/.test(src);
      assert.ok(
        !vscodeImport,
        `${file} must not import the vscode module — pure modules stay host-free`
      );
    });
  }
});
