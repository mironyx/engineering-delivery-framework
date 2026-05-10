#!/usr/bin/env python3
"""Tick a closed issue's checkbox in its parent epic body.

Reads the issue body from stdin, extracts the parent epic number, reads the epic
body via gh, ticks the checkbox for this issue, and patches the epic via gh api.

Usage:
  gh issue view <N> --json body --jq .body | check-epic-checkbox.py --issue <N>
"""

import argparse
import re
import subprocess
import sys


def _extract_parent_epic(body: str) -> str:
    m = re.search(r"## Parent epic\s*\n+#(\d+)", body)
    return m.group(1) if m else ""


def _tick_checkbox(body: str, issue: str) -> str:
    return re.sub(
        r"- \[ \] (#" + re.escape(issue) + r"\b)",
        r"- [x] \1",
        body,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Tick parent epic checkbox for a closed issue")
    parser.add_argument("--issue", required=True, help="Issue number")
    args = parser.parse_args()

    body = sys.stdin.read()
    epic = _extract_parent_epic(body)

    if not epic:
        print(f"No parent epic found for issue #{args.issue}", file=sys.stderr)
        return

    result = subprocess.run(
        ["gh", "issue", "view", epic, "--json", "body", "--jq", ".body"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Failed to read epic #{epic}", file=sys.stderr)
        sys.exit(1)

    epic_body = result.stdout
    updated = _tick_checkbox(epic_body, args.issue)

    if updated == epic_body:
        print(f"Epic #{epic}: checkbox for #{args.issue} already ticked or not found")
        return

    proc = subprocess.run(
        ["gh", "api", f"repos/{{owner}}/{{repo}}/issues/{epic}",
         "--method", "PATCH", "-f", f"body={updated}"],
        capture_output=True, text=True,
    )
    if proc.returncode == 0:
        print(f"Epic #{epic}: checked off #{args.issue}")
    else:
        print(f"Failed to update epic #{epic}: {proc.stderr}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
