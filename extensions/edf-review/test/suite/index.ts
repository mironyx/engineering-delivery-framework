/**
 * Mocha bootstrap for the extension test host.
 *
 * Must REJECT when failures > 0: a bootstrap that resolves unconditionally
 * reports a green run for a red suite, which is worse than no harness at all.
 *
 * TODO(#48): the reject-on-failure path has no automated coverage — a future
 * refactor could regress it to resolve unconditionally and no test would
 * catch it. Deferred: asserting it needs a second host launch whose suite is
 * deliberately failing, which @vscode/test-electron does not model cleanly.
 * Verified empirically during #48 (red suite exits 1 with
 * "Error: 1 tests failed.") — PR #68.
 */
import * as path from 'path';
import Mocha from 'mocha';
import { glob } from 'glob';

export function run(): Promise<void> {
  const mocha = new Mocha({
    ui: 'bdd',
    color: true
  });

  const testsRoot = path.resolve(__dirname, '..');

  return new Promise((resolve, reject) => {
    glob('**/*.test.js', { cwd: testsRoot })
      .then((files) => {
        files.forEach((f) => mocha.addFile(path.resolve(testsRoot, f)));

        try {
          mocha.run((failures) => {
            if (failures > 0) {
              reject(new Error(`${failures} tests failed.`));
            } else {
              resolve();
            }
          });
        } catch (err) {
          reject(err);
        }
      })
      .catch((err) => {
        reject(err);
      });
  });
}
