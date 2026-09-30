"""List new functions the LLD does not name that lack a `Justification:` comment.

This is the mechanical half of pr-review Agent C's `[unspecified-function]` rule
(prompts/agent-c.md): a function the LLD does not specify needs a `Justification:`
comment, or the review blocks. Running it before the PR turns a recurring review
blocker into a local fix.

Usage:
  py bin/check-justification.py --lld <path|none> [--base <ref>]

A function counts as new when its declaration line was added on this branch and
no function of that name existed in the file before (diff against the merge-base with --base, default origin's default branch, else
main; untracked files count too). Test files are excluded. A function passes when
its name appears anywhere in the LLD, or when a `Justification:` appears in the
comment block directly above it (or, for Python, in its docstring).

Exit 0 when nothing is flagged (or --lld none), 1 otherwise.
"""

import argparse
import os
import pathlib
import re
import sys

import _git_changes as gc

SOURCE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".py"}
TEST_PATH = re.compile(r"(^|/)(tests?|spec|__tests__)/|\.(test|spec)\.|_test\.py$|(^|/)test_[^/]*\.py$")
DECLARATIONS = [
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*[<(]"),
    re.compile(r"^\s*(?:export\s+)?(?:const|let)\s+(\w+)\s*(?::[^=]+)?=\s*(?:async\s+)?(?:\([^)]*\)|\w+)\s*(?::[^=]+)?=>"),
    re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\("),
]
COMMENT_LINE = re.compile(r"^\s*(//|/\*|\*|#|@)")


def declared_name(line: str) -> str | None:
    for pattern in DECLARATIONS:
        m = pattern.match(line)
        if m:
            return m.group(1)
    return None


def has_justification(lines: list[str], idx: int, is_python: bool) -> bool:
    j = idx - 1
    while j >= 0 and COMMENT_LINE.match(lines[j]):
        if "Justification:" in lines[j]:
            return True
        j -= 1
    if is_python:
        return any("Justification:" in ln for ln in lines[idx + 1: idx + 16])
    return False


def find_unjustified(files: list[str], lld_text: str, base: str, untracked: set[str]) -> list[tuple[str, int, str]]:
    flagged = []
    for path in files:
        p = pathlib.Path(path)
        if p.suffix not in SOURCE_EXT or TEST_PATH.search(path) or not p.exists():
            continue
        new = gc.added_lines(path, base, untracked)
        if not new:
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        existing = {declared_name(ln) for ln in gc.git("show", f"{base}:{path}").splitlines()} - {None}
        for n in sorted(new):
            if n > len(lines):
                continue
            name = declared_name(lines[n - 1])
            if not name or name in existing or re.search(rf"\b{re.escape(name)}\b", lld_text):
                continue
            if not has_justification(lines, n - 1, p.suffix == ".py"):
                flagged.append((path, n, name))
    return flagged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lld", required=True, help="LLD path, or 'none'")
    parser.add_argument("--base", help="base ref (default: origin's default branch, else main)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.lld == "none":
        print("justification: skipped — no LLD for this issue")
        return 0
    lld = pathlib.Path(args.lld)
    if not lld.exists():
        print(f"justification: LLD not found: {args.lld}", file=sys.stderr)
        return 2

    lld = lld.resolve()
    os.chdir(gc.git("rev-parse", "--show-toplevel").strip() or ".")
    base = gc.merge_base(args.base)
    untracked = gc.untracked_files()
    files = gc.changed_files(base)
    flagged = find_unjustified(files, lld.read_text(encoding="utf-8", errors="replace"), base, untracked)

    if not flagged:
        print("justification: ok — every new function is named in the LLD or justified")
        return 0
    print(f"justification: {len(flagged)} new function(s) not named in the LLD lack a `Justification:` comment")
    for path, line, name in flagged:
        print(f"  {path}:{line} {name}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
