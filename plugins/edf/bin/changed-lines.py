"""Print the lines this branch added or modified, per changed file.

Lets a caller tell an issue this change introduced (on a changed line) from one
that was already in the file, without parsing diff hunks by hand.

Usage:
  py bin/changed-lines.py [--base <ref>] [file ...]

Output, one file per line:  src/foo.ts: 12-18,40
Files with no added lines (pure deletions) are omitted.
"""

import argparse
import os
import sys

import _git_changes as gc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", help="base ref (default: origin's default branch, else main)")
    parser.add_argument("files", nargs="*", help="limit to these repo-relative files")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    os.chdir(gc.git("rev-parse", "--show-toplevel").strip() or ".")
    base = gc.merge_base(args.base)
    untracked = gc.untracked_files()
    files = [f.replace("\\", "/") for f in args.files] or gc.changed_files(base)
    for path in files:
        if not os.path.exists(path):
            continue
        lines = gc.added_lines(path, base, untracked)
        if lines:
            print(f"{path}: {gc.to_ranges(lines)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
