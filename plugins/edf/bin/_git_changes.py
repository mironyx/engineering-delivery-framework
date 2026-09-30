"""Shared helpers: what this branch changed, relative to its merge-base."""

import pathlib
import re
import subprocess


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def merge_base(base: str | None = None) -> str:
    """Merge-base of HEAD with base (default: origin's default branch, else main)."""
    if not base:
        base = git("symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD").strip() or "main"
    return git("merge-base", "HEAD", base).strip() or base


def untracked_files() -> set[str]:
    return set(git("ls-files", "--others", "--exclude-standard").splitlines())


def changed_files(base: str) -> list[str]:
    """Committed, staged, unstaged and untracked changes since base."""
    return sorted(set(git("diff", "--name-only", base).splitlines()) | untracked_files())


def added_lines(path: str, base: str, untracked: set[str]) -> set[int]:
    """1-based line numbers added or modified since base (all lines for an untracked file)."""
    if path in untracked:
        text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
        return set(range(1, len(text.splitlines()) + 1))
    added: set[int] = set()
    for line in git("diff", "-U0", base, "--", path).splitlines():
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if m:
            start, count = int(m.group(1)), int(m.group(2) or "1")
            added.update(range(start, start + count))
    return added


def to_ranges(lines: set[int]) -> str:
    """{1,2,3,7} -> '1-3,7'."""
    out, nums = [], sorted(lines)
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ",".join(out)
