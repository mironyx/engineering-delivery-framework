/**
 * Issue #51 (v1-e1-2): packaging invariants — LLD §2.4.
 *
 * These specs guard the packaging contract from regressing: the `.vsix` must
 * carry the compiled `out/` (the `main` entry point) but never sources, tests,
 * config, sourcemaps, or the `.vscodeignore` itself; the manifest must declare
 * no marketplace-listing metadata; and the `package` script must be present.
 * The two specs that read the extension tree run in the same test host as the
 * rest of the suite — `__dirname` is the compiled `out/test/suite/`, so
 * `path.join(__dirname, '../../../.vscodeignore')` resolves to
 * extensions/edf-review/.vscodeignore.
 *
 * TODO(#51): these specs assert the .vscodeignore contract text, not the emitted
 * .vsix — the LLD §2.4 BDD spec "emits a vsix with no packaging errors" has no
 * automated counterpart. That AC, and shipped-content drift (e.g. a map emitted
 * outside out/, or vsce's default-ignore list growing), rests on the recorded
 * manual `unzip -l` / install run in the EDF-51 session log. Consider running
 * `vsce package` in-suite and inspecting the artefact when the test host can
 * tolerate the build cost. (pr-review #74 warn — deferred, non-blocking.)
 */
import * as path from 'path';
import * as fs from 'fs';
import * as assert from 'assert';
import { readManifest } from './manifest';

/** The ignore patterns declared in .vscodeignore, one per non-blank line. */
function readVscodeIgnore(): string[] {
  const ignorePath = path.join(__dirname, '../../../.vscodeignore');
  return fs
    .readFileSync(ignorePath, 'utf8')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line !== '' && !line.startsWith('#'));
}

describe('packaging', () => {
  it('excludes sources, tests, config and sourcemaps from the artefact', () => {
    // LLD §2.4 Invariant 21 / AC5: the .vsix must not carry src/, test/,
    // tsconfig.json, or *.map — but must ship out/ (the compiled main entry).
    const ignore = readVscodeIgnore();
    const has = (pattern: string) =>
      ignore.some((entry) => entry === pattern || entry.startsWith(pattern + '/'));

    assert.ok(has('src'), '.vscodeignore must exclude src/');
    // Deferred from #48 to this task (LLD §2.1 Implementation note): confirmed —
    // the shipped artefact must exclude test sources. tsconfig (rootDir ".")
    // compiles the tests into out/test/, so the compiled test output is excluded
    // too (design deviation — the LLD's literal .vscodeignore block omitted it).
    assert.ok(has('test'), '.vscodeignore must exclude test/');
    assert.ok(has('out/test'), '.vscodeignore must exclude compiled test output out/test/');
    assert.ok(ignore.includes('tsconfig.json'), '.vscodeignore must exclude tsconfig.json');
    assert.ok(
      ignore.some((entry) => entry.endsWith('*.map')),
      '.vscodeignore must exclude *.map sourcemaps'
    );
  });

  it('ships the compiled out/ directory (main entry point)', () => {
    // LLD §2.4 Constraint: out/** must NOT be excluded. Excluding it produces a
    // .vsix that installs and then fails to activate — the packaging-only
    // regression Story 2.2 AC4 exists to catch.
    const ignore = readVscodeIgnore();
    const excludesOut = ignore.some(
      (entry) => entry === 'out' || entry === 'out/' || entry === 'out/**'
    );
    assert.ok(
      !excludesOut,
      '.vscodeignore must not exclude out/ — it holds the compiled main entry point'
    );
  });

  it('declares no marketplace listing metadata', () => {
    // LLD §2.4 Invariant 20: the manifest carries only publisher, name, version,
    // engines.vscode beyond contributes.commands — no icon, galleryBanner or
    // categories. Equivalent to `jq -e '.icon // .galleryBanner // .categories'`
    // failing on the packaged manifest.
    const manifest = readManifest();
    for (const key of ['icon', 'galleryBanner', 'categories'] as const) {
      assert.ok(
        !(key in manifest),
        `package.json must not declare a ${key} marketplace-listing field`
      );
    }
  });

  it('declares a package script that emits the vsix via vsce', () => {
    // LLD §2.4 Scripts block: `vsce package` is the packaging command.
    assert.strictEqual(
      readManifest().scripts?.package,
      'vsce package',
      'scripts.package must invoke vsce package'
    );
  });
});
