/**
 * Heading extraction — pure string module, no `vscode` import.
 *
 * LLD v1-e1-2 §2.2: the command's only real logic around *which* headings a
 * document has. Keeping this free of the VSCode API is what lets it be tested
 * without a host.
 */

/** A `##` or `###` heading found in a markdown document. */
export interface Heading {
  /** 0-based index into the document's line array. */
  line: number;
  /** Heading text: hashes stripped, ATX-close stripped, trimmed. */
  text: string;
  /** `##` or `###`. */
  level: 2 | 3;
}

/**
 * Extract `##`/`###` headings from a markdown document.
 *
 * Splits on `/\r?\n/`, tracks fenced-code state on ```` ``` ```` and `~~~` so
 * headings inside fences are skipped, and matches `##`/`###` headings (ATX-close
 * handled, text trimmed). `#`, `####` and deeper are excluded.
 *
 * Never throws — a malformed document yields fewer headings, not an exception.
 */
export function extractHeadings(text: string): Heading[] {
  const lines = text.split(/\r?\n/);
  const headings: Heading[] = [];
  let inFence = false;
  let fenceMarker = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Toggle fenced-code state on ``` and ~~~ markers. A fence of a different
    // marker char inside an open fence is content, not a close.
    const fenceMatch = line.match(/^\s*(```+|~~~+)/);
    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (!inFence) {
        inFence = true;
        fenceMarker = marker;
      } else if (marker[0] === fenceMarker[0]) {
        inFence = false;
        fenceMarker = '';
      }
      continue;
    }

    if (inFence) continue;

    // ## / ### only, with optional ATX-close; text between hashes and close.
    const headingMatch = line.match(/^(#{2,3})\s+(.*?)(?:\s+#+)?\s*$/);
    if (headingMatch) {
      headings.push({
        line: i,
        text: headingMatch[2].trim(),
        level: headingMatch[1].length === 2 ? 2 : 3
      });
    }
  }

  return headings;
}
