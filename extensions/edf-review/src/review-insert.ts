/**
 * Review insertion point — pure string module, no `vscode` import.
 *
 * LLD v1-e1-2 §2.2: where a new `[Review]` marker belongs relative to existing
 * markers under a heading. Keeping this free of the VSCode API is what lets it
 * be tested without a host.
 */

/** The marker inserted before a review comment. The trailing space is significant. */
export const REVIEW_MARKER = '> **[Review]:** ';

/**
 * Find the line at which a new review marker should be inserted after a heading.
 *
 * Walks forward from `headingLine + 1` while lines start with
 * `REVIEW_MARKER.trimEnd()` (a blank line or a prose line terminates the run),
 * returning the last marker line. When no marker follows, returns `headingLine`
 * unchanged.
 *
 * Never throws — an out-of-range `headingLine` returns `headingLine` unchanged.
 */
export function findReviewInsertLine(lines: string[], headingLine: number): number {
  // Out-of-range input returns unchanged — the walk below would otherwise read
  // from a negative index start (headingLine + 1) or start past the array end.
  if (headingLine < 0 || headingLine >= lines.length) {
    return headingLine;
  }

  let at = headingLine;
  const marker = REVIEW_MARKER.trimEnd();

  for (let i = headingLine + 1; i < lines.length; i++) {
    if (lines[i].startsWith(marker)) {
      at = i;
    } else {
      break;
    }
  }

  return at;
}
