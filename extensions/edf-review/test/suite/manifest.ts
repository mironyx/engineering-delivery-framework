/**
 * Shared manifest-reading helper for the scaffold specs (issue #48).
 *
 * Both scaffold.test.ts and evaluator-gap.test.ts assert against the packaged
 * manifest; keeping the read + typing in one module prevents the two specs'
 * views of what the manifest promises from drifting.
 *
 * The manifest is read from the compiled location: out/test/suite/, so
 * path.join(__dirname, '../../../package.json') resolves to
 * extensions/edf-review/package.json.
 */
import * as path from 'path';
import * as fs from 'fs';

/** Parsed view of the manifest fields the scaffold specs assert. */
export interface Manifest {
  displayName?: string;
  description?: string;
  version?: string;
  activationEvents?: string[];
  contributes?: {
    commands?: Array<{ command: string; title?: string; category?: string }>;
    [key: string]: unknown;
  };
}

export function readManifest(): Manifest {
  const manifestPath = path.join(__dirname, '../../../package.json');
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8')) as Manifest;
}
