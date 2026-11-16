#!/usr/bin/env python3
"""Tick a closed issue's checkbox in its parent epic body (shim over the GitHub backend).

Reads the issue body from stdin; the parent lookup, epic read and epic patch live in
_tracker_github.tick_parent_checkbox (ADR-0041).

Usage:
  gh issue view <N> --json body --jq .body | check-epic-checkbox.py --issue <N>
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _tracker_github  # noqa: E402
from _tracker_contract import TrackerError  # noqa: E402


def _extract_parent_epic(body: str) -> str:
    parent = _tracker_github.parent_from_body(body)
    return parent[1:] if parent else ""


def _tick_checkbox(body: str, issue: str) -> str:
    return _tracker_github.tick_checkbox(body, issue)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tick parent epic checkbox for a closed issue")
    parser.add_argument("--issue", required=True, help="Issue number")
    args = parser.parse_args()

    try:
        outcome, message = _tracker_github.tick_parent_checkbox(int(args.issue), sys.stdin.read())
    except TrackerError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(message, file=sys.stderr if outcome == "no-parent" else sys.stdout)


if __name__ == "__main__":
    main()
