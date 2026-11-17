#!/usr/bin/env python3
"""Epic progress reader: "1 of 3 done" and per-child statuses (ADR-0041).

Design reference: plugins/edf/docs/design/v3/lld-v3-e3-3-pipeline-call-sites.md §1.2

Usage:
  epic-progress.py REF              -> "<REF>: 1 of 3 done", then "  <child> <status>" per child
  epic-progress.py REF --remaining  -> children whose status is not done, one ref per line

Calls `tracker.py view` as a subprocess (the only route to credentials) and never writes.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

TRACKER = pathlib.Path(__file__).resolve().parent / "tracker.py"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="epic-progress.py")
    parser.add_argument("ref")
    parser.add_argument("--remaining", action="store_true")
    args = parser.parse_args(argv)

    result = subprocess.run([sys.executable, str(TRACKER), "view", args.ref], capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip() or "Error: tracker view failed", file=sys.stderr)
        return 1
    try:
        issue = json.loads(result.stdout)
        statuses = {child: issue["child_statuses"].get(child, "unknown") for child in issue["children"]}
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        print("Error: unexpected tracker view output", file=sys.stderr)
        return 1
    if args.remaining:
        for child, status in statuses.items():
            if status != "done":
                print(child)
        return 0
    done = sum(status == "done" for status in statuses.values())
    print(f"{args.ref}: {done} of {len(statuses)} done")
    for child, status in statuses.items():
        print(f"  {child} {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
