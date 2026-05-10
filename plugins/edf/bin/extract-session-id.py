#!/usr/bin/env python3
"""Extract session ID for a feature issue.

Tries PR body first (claude-session-id: <uuid> comment), then falls back
to the Prometheus textfile session_feature.prom.

Usage:
  extract-session-id.py --issue <N> [--pr-body <text>]
  gh pr view <N> --json body --jq .body | extract-session-id.py --issue <N>

Output: session ID UUID, or empty string if not found.
"""

import argparse
import os
import pathlib
import re
import subprocess
import sys


def _git_root() -> pathlib.Path:
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True,
    )
    return pathlib.Path(result.stdout.strip()).parent.resolve()


def _extract_from_pr_body(body: str) -> str:
    m = re.search(r"claude-session-id: ([a-f0-9-]+)", body)
    return m.group(1) if m else ""


def _extract_from_prom(issue: str, root: pathlib.Path) -> str:
    prom_dir = pathlib.Path(
        os.environ.get("EDF_FEATURE_PROM_DIR")
        or root / "monitoring" / "textfile_collector"
    )
    prom = prom_dir / "session_feature.prom"
    if not prom.exists():
        return ""
    m = re.search(
        r'session_id="([^"]+)",feature_id="[^"]+-' + re.escape(issue) + r'"',
        prom.read_text(),
    )
    return m.group(1) if m else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract session ID for a feature issue")
    parser.add_argument("--issue", required=True, help="Issue number")
    parser.add_argument("--pr-body", default=None, help="PR body text (reads stdin if omitted)")
    args = parser.parse_args()

    body = args.pr_body
    if body is None:
        body = sys.stdin.read()

    session_id = _extract_from_pr_body(body)
    if not session_id:
        session_id = _extract_from_prom(args.issue, _git_root())

    print(session_id)


if __name__ == "__main__":
    main()
